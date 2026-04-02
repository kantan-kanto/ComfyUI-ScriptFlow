# ComfyUI-ScriptFlow
# Copyright (C) 2026 kantan-kanto (https://github.com/kantan-kanto)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from __future__ import annotations

__version__ = "1.1.0"

import datetime
import math
import random
from typing import Any, Dict


_ALLOWED_BUILTINS = {
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "range": range,
    "zip": zip,
    "map": map,
    "filter": filter,
    "any": any,
    "all": all,
    "pow": pow,
    "divmod": divmod,
    "list": list,
    "dict": dict,
    "tuple": tuple,
}


class AnyType(str):
    def __ne__(self, __value: object) -> bool:  # allow any connection type
        return False


_ANY_TYPE = AnyType("*")


def _build_globals() -> Dict[str, Any]:
    return {
        "__builtins__": _ALLOWED_BUILTINS,
        "random": random,
        "datetime": datetime,
        "math": math,
    }


def _validate_outputs(locals_dict: Dict[str, Any]) -> None:
    text_keys = ("ot1", "ot2", "ot3")
    value_keys = ("ov1", "ov2", "ov3")

    for key in text_keys:
        val = locals_dict.get(key)
        if val is None:
            continue
        if not isinstance(val, str):
            raise ValueError(f"{key} must be str or None, got {type(val).__name__}")

    for key in value_keys:
        val = locals_dict.get(key)
        if val is None:
            continue
        if not isinstance(val, (int, float)):
            raise ValueError(f"{key} must be int/float or None, got {type(val).__name__}")


def _select_numeric_value(
    base_value: Any, override_value: Any, label: str
) -> float | int:
    if override_value is None:
        return base_value
    if not isinstance(override_value, (int, float)):
        raise ValueError(f"{label} must be int/float, got {type(override_value).__name__}")
    return override_value


def _select_text_value(base_value: Any, override_value: Any, label: str) -> str:
    if override_value is None:
        return base_value
    if not isinstance(override_value, str):
        raise ValueError(f"{label} must be str, got {type(override_value).__name__}")
    return override_value


class MultiOutputScript:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "code": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": (
                            "# UI inputs: in_text_1, in_text_2, in_text_3, in_value_1, in_value_2, in_value_3\n"
                            "# Script inputs: it1, it2, it3, iv1, iv2, iv3\n"
                            "# UI outputs: out_text_1, out_text_2, out_text_3, out_value_1, out_value_2, out_value_3\n"
                            "# Script outputs: ot1, ot2, ot3, ov1, ov2, ov3\n"
                            "# Example:\n"
                            "width, height = (512, 384) if iv1 > iv2 else (384, 512)\n"
                            "ov1, ov2 =  width, height\n"
                        ),
                    },
                ),
            },
            "optional": {
                "in_text_1": (_ANY_TYPE,),
                "in_text_2": (_ANY_TYPE,),
                "in_text_3": (_ANY_TYPE,),
                "in_value_1": (_ANY_TYPE,),
                "in_value_2": (_ANY_TYPE,),
                "in_value_3": (_ANY_TYPE,),
            },
        }

    RETURN_TYPES = (
        "STRING",
        "STRING",
        "STRING",
        "INT",
        "INT",
        "INT",
    )
    RETURN_NAMES = (
        "out_text_1",
        "out_text_2",
        "out_text_3",
        "out_value_1",
        "out_value_2",
        "out_value_3",
    )
    FUNCTION = "run"
    CATEGORY = "utils"

    def run(
        self,
        code: str,
        in_text_1: Any = None,
        in_text_2: Any = None,
        in_text_3: Any = None,
        in_value_1: Any = None,
        in_value_2: Any = None,
        in_value_3: Any = None,
    ):
        it1 = _select_text_value("", in_text_1, "in_text_1")
        it2 = _select_text_value("", in_text_2, "in_text_2")
        it3 = _select_text_value("", in_text_3, "in_text_3")
        iv1 = _select_numeric_value(0.0, in_value_1, "in_value_1")
        iv2 = _select_numeric_value(0.0, in_value_2, "in_value_2")
        iv3 = _select_numeric_value(0.0, in_value_3, "in_value_3")

        locals_dict: Dict[str, Any] = {
            "it1": it1,
            "it2": it2,
            "it3": it3,
            "iv1": iv1,
            "iv2": iv2,
            "iv3": iv3,
            "ot1": None,
            "ot2": None,
            "ot3": None,
            "ov1": None,
            "ov2": None,
            "ov3": None,
        }

        globals_dict = _build_globals()
        exec(code, globals_dict, locals_dict)

        _validate_outputs(locals_dict)

        return (
            locals_dict.get("ot1"),
            locals_dict.get("ot2"),
            locals_dict.get("ot3"),
            None if locals_dict.get("ov1") is None else int(locals_dict.get("ov1")),
            None if locals_dict.get("ov2") is None else int(locals_dict.get("ov2")),
            None if locals_dict.get("ov3") is None else int(locals_dict.get("ov3")),
        )


class Centi:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "int_1": ("INT", {"forceInput": True}),
                "int_2": ("INT", {"forceInput": True}),
                "int_3": ("INT", {"forceInput": True}),
            },
        }

    RETURN_TYPES = ("FLOAT", "FLOAT", "FLOAT")
    RETURN_NAMES = ("float_1", "float_2", "float_3")
    FUNCTION = "run"
    CATEGORY = "utils"

    def run(
        self,
        int_1: int | None = None,
        int_2: int | None = None,
        int_3: int | None = None,
    ):
        return (
            None if int_1 is None else float(int_1) / 100.0,
            None if int_2 is None else float(int_2) / 100.0,
            None if int_3 is None else float(int_3) / 100.0,
        )


NODE_CLASS_MAPPINGS = {
    "MultiOutputScript": MultiOutputScript,
    "centi": Centi,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MultiOutputScript": "MultiOutputScript",
    "centi": "centi",
}
