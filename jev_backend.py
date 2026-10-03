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

import gc
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import comfy.model_management
import folder_paths
import numpy as np

try:
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
    """Answers with a local GGUF model, one forward pass per question. Noul is asked as Yes/No options."""

    def __init__(self, model_path: str):
        self.model_path = model_path

    def ask(self, state: Any, questions: list[tuple]) -> list[list[float]]:
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
    tokens = llm.tokenize(prompt.encode("utf-8"), add_bos=False, special=True)
    if len(tokens) >= llm.n_ctx():
        raise ValueError(f"Jev prompt is {len(tokens)} tokens, over the {llm.n_ctx()} token context")
    slots = []
    for letter in _LETTERS[: len(options)]:
        encoded = llm.tokenize(letter.encode("utf-8"), add_bos=False, special=False)
        if len(encoded) != 1:
            raise ValueError(f"Model tokenizer does not encode {letter!r} as one token")
        slots.append(encoded[0])
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
    vocabulary = np.ctypeslib.as_array(llama_get_logits_ith(llm.ctx, -1), shape=(llm.n_vocab(),))
    logits = vocabulary[slots].astype(np.float64)
    weights = np.exp(logits - logits.max())
    return (weights / weights.sum()).tolist()


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


def load_local_model(model_path: str) -> tuple[Any, Any]:
    global _loaded_model
    if _loaded_model is not None and _loaded_model[0] == model_path:
        return _loaded_model[1], _loaded_model[2]
    if Llama is None:
        raise RuntimeError("llama-cpp-python is not installed. See the README for installation.")
    unload_local_model()
    device = comfy.model_management.get_torch_device()
    comfy.model_management.free_memory(os.path.getsize(model_path) * 1.2, device)
    # n_batch = n_ctx so one llama_decode call can take the whole prompt
    llm = Llama(model_path=model_path, n_ctx=_N_CTX, n_batch=_N_CTX, n_gpu_layers=-1, verbose=False)
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
