# ComfyUI-ScriptFlow
# Copyright (C) 2026 kantan-kanto (https://github.com/kantan-kanto)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from __future__ import annotations

import json
from typing import Any

try:
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
except ImportError:
    TypeSafeClient = None


class JevBackend:
    """Asks Jev one question per call. Scoped to a single script run."""

    def __init__(self, client: Any, max_calls: int):
        self.client = client
        self.max_calls = max_calls
        self.calls = 0
        self.cache: dict[str, Any] = {}

    def noul(self, state: Any, question: str) -> float:
        return self._ask(state, Noul(instructions=question)).noul

    def choice(self, state: Any, question: str, options: list | dict) -> str:
        if isinstance(options, list):
            options = {str(option): None for option in options}
        return self._ask(state, Choice(instructions=question, criteria=options)).choice

    def score(self, state: Any, question: str, levels: list) -> float:
        return self._ask(state, Score(instructions=question, criteria=levels)).score

    def _ask(self, state: Any, question: Any) -> Any:
        key = json.dumps([state, question.model_dump()], sort_keys=True, ensure_ascii=False)
        if key in self.cache:
            return self.cache[key]
        if self.calls >= self.max_calls:
            raise RuntimeError(f"Script exceeded max_jev_calls ({self.max_calls})")
        self.calls += 1
        answer = self.client.system_one(state=state, questions={"q": question}).answers["q"]
        self.cache[key] = answer
        return answer
