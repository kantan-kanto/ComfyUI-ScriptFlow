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

import json
import os
from typing import Any

import comfy.model_management
import folder_paths
import numpy as np

try:
    from llama_cpp import Llama, llama_get_memory, llama_memory_clear
    from llama_cpp.llama_chat_format import Jinja2ChatFormatter
except ImportError:
    Llama = None


_LETTERS = "ABCDEFGHIJKLMNOP"
_DIRECT_SYSTEM = (
    "Apply the supplied criterion to the supplied evidence. Choose exactly one listed option. "
    "Respond with only its uppercase letter, with no explanation or reasoning."
)
_N_CTX = 8192

_loaded_model: tuple[str, Any, Any] | None = None


class JevBackend:
    """Caches answers and limits model calls for a single script run."""

    def __init__(self, model_path: str, max_calls: int):
        self.model_path = model_path
        self.max_calls = max_calls
        self.calls = 0
        self.cache: dict[str, Any] = {}

    def noul(self, state: Any, question: Any) -> float:
        return self._ask(state, question, ["Yes", "No"])[0]

    def choice(self, state: Any, question: Any, options: list | dict) -> str:
        if isinstance(options, list):
            options = {str(option): None for option in options}
        labels = list(options)
        descriptions = [label if description is None else f"{label}: {description}" for label, description in options.items()]
        probabilities = self._ask(state, question, descriptions)
        return labels[probabilities.index(max(probabilities))]

    def score(self, state: Any, question: Any, levels: list) -> float:
        probabilities = self._ask(state, question, list(levels))
        return sum(level * p for level, p in enumerate(probabilities))

    def _ask(self, state: Any, question: Any, options: list) -> list[float]:
        key = json.dumps([state, question, options], sort_keys=True, ensure_ascii=False)
        if key in self.cache:
            return self.cache[key]
        if self.calls >= self.max_calls:
            raise RuntimeError(f"Script exceeded max_jev_calls ({self.max_calls})")
        self.calls += 1
        probabilities = _option_probabilities(self.model_path, state, question, options)
        self.cache[key] = probabilities
        return probabilities


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
    # reset() alone keeps the recurrent state of hybrid models such as Qwen3.5
    llama_memory_clear(llama_get_memory(llm.ctx), True)
    llm.reset()
    llm.eval(tokens)
    logits = llm.scores[0, slots].astype(np.float64)
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
    llm = Llama(model_path=model_path, n_ctx=_N_CTX, n_gpu_layers=-1, verbose=False)
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
    global _loaded_model
    if _loaded_model is None:
        return
    _loaded_model[1].close()
    _loaded_model = None
