# ComfyUI-ScriptFlow
# Copyright (C) 2026 kantan-kanto (https://github.com/kantan-kanto)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The decision readout is adapted from SemIf (formerly OpenJev),
# Copyright (c) 2026 TheoLeeCJ, MIT License: https://github.com/TheoLeeCJ/SemIf-OpenJev

from __future__ import annotations

import ctypes
import gc
import json
import logging
import os
import struct
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import comfy.model_management
import folder_paths
import numpy as np

try:
    # The Clef path reads its newer functions from this module at call time,
    # so llama-cpp-python builds without them still serve the other local models.
    import llama_cpp.llama_cpp as llama_lib
    from llama_cpp import (
        Llama,
        llama_batch_free,
        llama_batch_init,
        llama_decode,
        llama_get_logits_ith,
        llama_get_memory,
        llama_memory_clear,
    )
    from llama_cpp.llama_chat_format import Jinja2ChatFormatter
except ImportError:
    Llama = None

try:
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
    # One INFO line pair per request floods the console; the run summary is printed instead.
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("typesafe_sdk").setLevel(logging.WARNING)
except ImportError:
    TypeSafeClient = None


_LETTERS = "ABCDEFGHIJKLMNOP"
_DIRECT_SYSTEM = (
    "Apply the supplied criterion to the supplied evidence. Choose exactly one listed option. "
    "Respond with only its uppercase letter, with no explanation or reasoning."
)
_N_CTX = 8192

# Clef (Cloudflare's decision model) prompt, as in joint_schema_model.py of Cloudflare/clef-flash (Apache-2.0)
# and the "systemone" template of its GGUF.
_CLEF_SYSTEM = (
    "Read the complete state and schema. Decide every field jointly. "
    "Each answer must be exactly one of that field's allowed options."
)
_CLEF_NOUL_OPTIONS = [
    ("true", "The proposition is true or the answer is yes."),
    ("false", "The proposition is false or the answer is no."),
]
# enum llama_decision_order: which tokens the decision head reads as a question of each type, or as an option
_CLEF_ORDER_QUESTION = {"noul": 1, "choice": 2, "score": 3}
_CLEF_ORDER_OPTION = 4
# llama_batch_ext_set_decision_order is exported with C++ linkage: MSVC name, then Itanium (macOS, Linux)
_CLEF_SET_ORDER_SYMBOLS = (
    "?llama_batch_ext_set_decision_order@@YA_NPEAUllama_batch_ext@@HW4llama_decision_order@@@Z",
    "__Z34llama_batch_ext_set_decision_orderP15llama_batch_exti20llama_decision_order",
    "_Z34llama_batch_ext_set_decision_orderP15llama_batch_exti20llama_decision_order",
)
_LLAMA_PROCESS_TYPE_DECODE = 1
_GGUF_TYPE_STRING = 8

# d1 (Liquid AI's decision model) prompt and answer words, as in prompt.py of LiquidAI/d1-3B
# and the "systemone" template of its GGUF.
_D1_CODES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_D1_NOUL_FORMS = [("yes", "Yes", "YES"), ("no", "No", "NO")]

_loaded_model: tuple[str, Any, Any] | None = None


class NeedAnswers(Exception):
    """Raised when a script uses an answer that is still queued."""


class _Unanswered:
    """Stands in for a queued answer. Storing or passing it is fine; using its value raises NeedAnswers."""

    def _need(self, *args: Any) -> Any:
        raise NeedAnswers()

    __bool__ = __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = __hash__ = _need
    __str__ = __repr__ = __format__ = __float__ = __int__ = __index__ = _need
    __len__ = __iter__ = __contains__ = __getitem__ = _need


UNANSWERED = _Unanswered()


def _json_default(value: Any) -> Any:
    if value is UNANSWERED:
        raise NeedAnswers()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class JevBackend:
    """Queues questions during a script run and asks them in batches, one request per state.

    The caller reruns the script after each flush(); answered questions then return their values from the cache.
    max_calls limits the number of requests.
    """

    def __init__(self, engine: Any, max_calls: int, parallel: bool):
        self.engine = engine
        self.max_calls = max_calls
        self.parallel = parallel
        self.requests = 0
        self.responses = 0
        self.questions = 0
        self.states: set[str] = set()
        self.cache: dict[str, list[float]] = {}
        self.pending: dict[str, tuple] = {}

    def noul(self, state: Any, question: Any) -> Any:
        probabilities = self._ask(state, "noul", question, None)
        return UNANSWERED if probabilities is None else probabilities[0]

    def choice(self, state: Any, question: Any, options: list | dict) -> Any:
        probabilities = self.probabilities(state, question, options)
        return UNANSWERED if probabilities is UNANSWERED else max(probabilities, key=probabilities.get)

    def probabilities(self, state: Any, question: Any, options: list | dict) -> Any:
        if isinstance(options, list):
            options = {str(option): None for option in options}
        probabilities = self._ask(state, "choice", question, options)
        return UNANSWERED if probabilities is None else dict(zip(options, probabilities))

    def score(self, state: Any, question: Any, levels: list) -> Any:
        probabilities = self._ask(state, "score", question, list(levels))
        return UNANSWERED if probabilities is None else sum(level * p for level, p in enumerate(probabilities))

    def _ask(self, state: Any, kind: str, question: Any, criteria: Any) -> list[float] | None:
        key = json.dumps([state, kind, question, criteria], sort_keys=True, ensure_ascii=False, default=_json_default)
        if key in self.cache:
            return self.cache[key]
        self.pending[key] = (state, kind, question, criteria)
        return None

    def flush(self) -> None:
        groups: dict[str, list[str]] = {}
        for key, (state, *_) in self.pending.items():
            groups.setdefault(json.dumps(state, sort_keys=True, ensure_ascii=False), []).append(key)
        if self.requests + len(groups) > self.max_calls:
            raise RuntimeError(
                f"Script needs more than max_jev_calls ({self.max_calls}) requests: "
                f"{self.requests} sent, {len(groups)} more needed"
            )
        self.requests += len(groups)
        self.questions += len(self.pending)
        self.states.update(groups)
        batches = list(groups.values())
        self.pending, pending = {}, self.pending
        if self.parallel and len(batches) > 1:
            with ThreadPoolExecutor(max_workers=len(batches)) as pool:
                futures = [pool.submit(self._send, pending, keys) for keys in batches]
            errors = [future.exception() for future in futures]
            self.responses += errors.count(None)
            for error in errors:
                if error is not None:
                    raise error
            return
        for keys in batches:
            self._send(pending, keys)
            self.responses += 1

    def _send(self, pending: dict[str, tuple], keys: list[str]) -> None:
        state = pending[keys[0]][0]
        answers = self.engine.ask(state, [pending[key][1:] for key in keys])
        for key, probabilities in zip(keys, answers):
            self.cache[key] = probabilities


class LocalJev:
    """Answers with a local GGUF model, one forward pass per question.

    A d1 model is asked in the prompt format it was tuned on. Other models get lettered options, noul as Yes/No.
    """

    def __init__(self, model_path: str):
        self.model_path = model_path

    def ask(self, state: Any, questions: list[tuple]) -> list[list[float]]:
        llm, _ = load_local_model(self.model_path)
        if llm.metadata.get("lfm2.decision.type") == "lfm2-d1":
            return [_d1_probabilities(llm, state, *question) for question in questions]
        answers = []
        for kind, question, criteria in questions:
            if kind == "noul":
                options = ["Yes", "No"]
            elif kind == "choice":
                options = [label if description is None else f"{label}: {description}" for label, description in criteria.items()]
            else:
                options = criteria
            answers.append(_option_probabilities(self.model_path, state, question, options))
        return answers


class ClefJev:
    """Answers with a local Clef GGUF: every question about one state in one forward pass.

    The model's joint decision head scores each option of each question; no text is generated.
    """

    def __init__(self, model_path: str):
        self.model_path = model_path

    def ask(self, state: Any, questions: list[tuple]) -> list[list[float]]:
        llm = load_clef_model(self.model_path)
        options = [_clef_options(kind, criteria) for kind, _, criteria in questions]

        # The pieces are tokenized one by one, as in training.
        tokens: list[int] = []
        orders: list[int] = []

        def add(text: str, order: int = 0) -> None:
            piece = llm.tokenize(text.encode("utf-8"), add_bos=False, special=True)
            tokens.extend(piece)
            orders.extend([order] * len(piece))

        add(f"<|im_start|>system\n{_CLEF_SYSTEM}<|im_end|>\n<|im_start|>user\nSTATE:\n")
        add(_clef_render(state))
        add("\n\nSCHEMA FIELDS:\n")
        for i, (kind, question, _) in enumerate(questions):
            add(f"\nFIELD {i + 1}\nID: q{i}\nTYPE: {kind}\nINSTRUCTION: ")
            add(_clef_render(question), _CLEF_ORDER_QUESTION[kind])
            add("\nALLOWED OPTIONS:\n")
            for j, (key, description) in enumerate(options[i]):
                add(f"OPTION {j + 1}: ")
                semantics = {"option_id": key}
                if description is not None:
                    semantics["description"] = description
                add(_clef_render(semantics), _CLEF_ORDER_OPTION)
                add("\n")
            add("END FIELD\n")
        add("\n<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\nJOINT SCHEMA DECISIONS:")
        if len(tokens) > llm.n_ctx():
            raise ValueError(f"Jev prompt is {len(tokens)} tokens, over the {llm.n_ctx()} token context")

        set_order = _clef_set_order_function()
        llama_memory_clear(llama_get_memory(llm.ctx), True)
        batch = llama_lib.llama_batch_ext_init(llm.ctx)
        try:
            for index, (token, order) in enumerate(zip(tokens, orders)):
                llama_lib.llama_batch_ext_add_token(batch, 0, token)
                llama_lib.llama_batch_ext_set_pos(batch, index, ctypes.byref(llama_lib.llama_pos(index)))
                llama_lib.llama_batch_ext_set_output_embd(batch, index, True)
                if order:
                    set_order(batch, index, order)
            if llama_lib.llama_process(llm.ctx, _LLAMA_PROCESS_TYPE_DECODE, batch) != 0:
                raise RuntimeError("llama_process failed for the Jev prompt")
        finally:
            llama_lib.llama_batch_ext_free(batch)

        # Row i of the embeddings output holds the score of option i, counted across the questions.
        results = []
        row = 0
        for (kind, _, criteria), question_options in zip(questions, options):
            scores = np.array(
                [llama_lib.llama_get_embeddings_ith(llm.ctx, row + i)[0] for i in range(len(question_options))],
                dtype=np.float64,
            )
            row += len(question_options)
            if np.isnan(scores).any():
                raise RuntimeError("The Clef model could not evaluate the questions")
            weights = np.exp(scores - scores.max())
            probabilities = dict(zip((key for key, _ in question_options), (weights / weights.sum()).tolist()))
            if kind == "choice":
                # Clef takes the options sorted by label; answer in the order they were given.
                results.append([probabilities[str(label)] for label in criteria])
            else:
                results.append(list(probabilities.values()))
        return results


def _clef_render(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _clef_options(kind: str, criteria: Any) -> list[tuple[str, Any]]:
    if kind == "noul":
        return _CLEF_NOUL_OPTIONS
    if kind == "choice":
        return sorted((str(label), description) for label, description in criteria.items())
    return [(str(level), description) for level, description in enumerate(criteria)]


def _clef_set_order_function() -> Any:
    for symbol in _CLEF_SET_ORDER_SYMBOLS:
        try:
            function = getattr(llama_lib._lib, symbol)
        except AttributeError:
            continue
        function.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_int]
        function.restype = ctypes.c_bool
        return function
    raise RuntimeError("This llama-cpp-python build cannot run Clef models. See the README for the required version.")


class TypeSafeJev:
    """Answers with TypeSafe's Jev API, all questions about one state in one request.

    Returns probabilities in the order of the options.
    """

    def __init__(self, client: Any):
        self.client = client

    def ask(self, state: Any, questions: list[tuple]) -> list[list[float]]:
        typed = {}
        for i, (kind, question, criteria) in enumerate(questions):
            if kind == "noul":
                typed[f"q{i}"] = Noul(instructions=question)
            elif kind == "choice":
                typed[f"q{i}"] = Choice(instructions=question, criteria=criteria)
            else:
                typed[f"q{i}"] = Score(instructions=question, criteria=criteria)
        answers = self.client.system_one(state=state, questions=typed).answers
        results = []
        for i, (kind, _, criteria) in enumerate(questions):
            answer = answers[f"q{i}"]
            if kind == "noul":
                results.append([answer.noul, 1.0 - answer.noul])
            elif kind == "choice":
                results.append([answer.probabilities[label] for label in criteria])
            else:
                results.append([answer.probabilities[level] for level in range(len(criteria))])
        return results


def _option_probabilities(model_path: str, state: Any, question: Any, options: list) -> list[float]:
    """Reads one decision from the next-token logits of the option letters, like SemIf's direct path."""
    if not 2 <= len(options) <= len(_LETTERS):
        raise ValueError(f"Jev questions need 2-{len(_LETTERS)} options, got {len(options)}")
    llm, formatter = load_local_model(model_path)
    payload = {
        "evidence": state,
        "criterion": question,
        "options": [{"letter": letter, "description": option} for letter, option in zip(_LETTERS, options)],
    }
    messages = [
        {"role": "system", "content": _DIRECT_SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    prompt = formatter(messages=messages, enable_thinking=False).prompt
    slots = []
    for letter in _LETTERS[: len(options)]:
        encoded = llm.tokenize(letter.encode("utf-8"), add_bos=False, special=False)
        if len(encoded) != 1:
            raise ValueError(f"Model tokenizer does not encode {letter!r} as one token")
        slots.append(encoded[0])
    logits = _next_token_logits(llm, prompt)[slots].astype(np.float64)
    weights = np.exp(logits - logits.max())
    return (weights / weights.sum()).tolist()


def _d1_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _d1_probabilities(llm: Any, state: Any, kind: str, question: Any, criteria: Any) -> list[float]:
    """Reads one decision from the next-token logits of the answer words d1 was tuned to reply with."""

    def token_ids(forms: Any) -> list[int]:
        encoded = [llm.tokenize(form.encode("utf-8"), add_bos=False, special=False) for form in forms]
        return [tokens[0] for tokens in encoded if len(tokens) == 1]

    if kind == "noul":
        body = "\n\nReply with yes or no only."
        groups = [token_ids(forms) for forms in _D1_NOUL_FORMS]
    elif kind == "choice":
        if not 2 <= len(criteria) <= len(_D1_CODES):
            raise ValueError(f"d1 choice questions need 2-{len(_D1_CODES)} options, got {len(criteria)}")
        labels = [str(label).strip() for label in criteria]
        # Labels that are single letters are their own codes.
        codes = labels if all(len(label) == 1 and label.isalpha() for label in labels) else _D1_CODES[: len(labels)]
        lines = [
            f"{code} {_d1_text(description) if description else label.replace('_', ' ')}"
            for code, label, description in zip(codes, labels, criteria.values())
        ]
        body = "\n\nOptions:\n" + "\n".join(lines) + "\n\nReply with the option code only."
        groups = [token_ids((code, f" {code}")) for code in codes]
    else:
        if not 2 <= len(criteria) <= 10:
            raise ValueError(f"d1 score questions need 2-10 levels, got {len(criteria)}")
        legend = "".join(f"{level} {_d1_text(description)}\n" for level, description in enumerate(criteria))
        body = f"\n\n{legend}\nReply with a single digit 0-{len(criteria) - 1} only."
        groups = [token_ids([str(level)]) for level in range(len(criteria))]
    if not all(groups) or len({group[0] for group in groups}) != len(groups):
        raise ValueError("Model tokenizer does not encode each d1 answer as one distinct token")
    state_text = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False, indent=2)
    prompt = (
        f"<|startoftext|><|im_start|>user\n{state_text}\n\n\nQUESTION:\n"
        f"{_d1_text(question)}{body}<|im_end|>\n<|im_start|>assistant\n"
    )
    vocabulary = _next_token_logits(llm, prompt)
    # Each option scores its best form.
    scores = np.array([vocabulary[group].max() for group in groups], dtype=np.float64)
    weights = np.exp(scores - scores.max())
    return (weights / weights.sum()).tolist()


def _next_token_logits(llm: Any, prompt: str) -> Any:
    tokens = llm.tokenize(prompt.encode("utf-8"), add_bos=False, special=True)
    if len(tokens) >= llm.n_ctx():
        raise ValueError(f"Jev prompt is {len(tokens)} tokens, over the {llm.n_ctx()} token context")
    # Each question starts from empty memory, including the recurrent state of hybrid models such as Qwen3.5.
    # Decode with the llama.cpp API directly instead of the Llama evaluation helper,
    # whose method name trips the ComfyUI Registry dynamic-execution scanner.
    llama_memory_clear(llama_get_memory(llm.ctx), True)
    batch = llama_batch_init(len(tokens), 0, 1)
    try:
        for index, token in enumerate(tokens):
            batch.token[index] = token
            batch.pos[index] = index
            batch.n_seq_id[index] = 1
            batch.seq_id[index][0] = 0
            batch.logits[index] = int(index == len(tokens) - 1)
        batch.n_tokens = len(tokens)
        if llama_decode(llm.ctx, batch) != 0:
            raise RuntimeError("llama_decode failed for the Jev prompt")
    finally:
        llama_batch_free(batch)
    return np.ctypeslib.as_array(llama_get_logits_ith(llm.ctx, -1), shape=(llm.n_vocab(),))


def _model_dirs() -> list[str]:
    dirs = []
    for key in ("LLM", "llm", "text_encoders"):
        try:
            dirs.extend(folder_paths.get_folder_paths(key))
        except KeyError:
            pass
    dirs.append(os.path.join(folder_paths.models_dir, "LLM"))
    return list(dict.fromkeys(os.path.normpath(d) for d in dirs))


def list_local_models() -> dict[str, str]:
    """GGUF language models under models/LLM and models/text_encoders, keyed by display name."""
    models = {}
    for root in _model_dirs():
        if not os.path.isdir(root):
            continue
        for current_dir, _, files in os.walk(root):
            for file_name in files:
                if file_name.endswith(".gguf") and not file_name.startswith("mmproj"):
                    path = os.path.join(current_dir, file_name)
                    models[_display_name(path)] = path
    return dict(sorted(models.items(), key=lambda item: item[0].lower()))


def _display_name(path: str) -> str:
    # models registered through extra_model_paths.yaml may be outside models_dir or on another drive
    try:
        rel = os.path.relpath(path, folder_paths.models_dir)
    except ValueError:
        return path
    return path if rel.startswith("..") else rel.replace("\\", "/")


def is_clef_model(model_path: str) -> bool:
    """Reads general.architecture, which GGUF writers store as the first metadata entry."""
    with open(model_path, "rb") as f:
        # magic, version, tensor count, metadata count, then the first key: length and bytes
        header = f.read(32)
        if len(header) < 32 or header[:4] != b"GGUF":
            return False
        key_length = struct.unpack("<Q", header[24:])[0]
        if key_length != len(b"general.architecture") or f.read(key_length) != b"general.architecture":
            return False
        value_type, value_length = struct.unpack("<IQ", f.read(12))
        return value_type == _GGUF_TYPE_STRING and value_length == len(b"clef") and f.read(value_length) == b"clef"


def _open_model(model_path: str, **kwargs: Any) -> Any:
    if Llama is None:
        raise RuntimeError("llama-cpp-python is not installed. See the README for installation.")
    unload_local_model()
    device = comfy.model_management.get_torch_device()
    comfy.model_management.free_memory(os.path.getsize(model_path) * 1.2, device)
    # n_batch = n_ctx so one decode call can take the whole prompt
    return Llama(model_path=model_path, n_ctx=_N_CTX, n_batch=_N_CTX, n_gpu_layers=-1, verbose=False, **kwargs)


def load_clef_model(model_path: str) -> Any:
    global _loaded_model
    if _loaded_model is not None and _loaded_model[0] == model_path:
        return _loaded_model[1]
    # The decision head reads the whole prompt in one physical batch, and its scores come out as embeddings.
    llm = _open_model(model_path, n_ubatch=_N_CTX, embeddings=True)
    _loaded_model = (model_path, llm, None)
    return llm


def load_local_model(model_path: str) -> tuple[Any, Any]:
    global _loaded_model
    if _loaded_model is not None and _loaded_model[0] == model_path:
        return _loaded_model[1], _loaded_model[2]
    llm = _open_model(model_path)
    template = llm.metadata.get("tokenizer.chat_template")
    if not template:
        llm.close()
        raise ValueError(f"GGUF has no chat template: {model_path}")
    bos, eos = llm.token_bos(), llm.token_eos()
    formatter = Jinja2ChatFormatter(
        template=template,
        bos_token=llm.detokenize([bos], special=True).decode("utf-8") if bos != -1 else "",
        eos_token=llm.detokenize([eos], special=True).decode("utf-8") if eos != -1 else "",
    )
    _loaded_model = (model_path, llm, formatter)
    return llm, formatter


def unload_local_model() -> None:
    # Same cleanup as ComfyUI-LLM-Session's Unload LLM Model: drop the model, collect, then empty the device cache
    global _loaded_model
    if _loaded_model is None:
        return
    llm = _loaded_model[1]
    _loaded_model = None
    llm.close()
    del llm
    gc.collect()
    comfy.model_management.soft_empty_cache()
