# ComfyUI-ScriptFlow
# Copyright (C) 2026 kantan-kanto (https://github.com/kantan-kanto)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from __future__ import annotations

__version__ = "1.2.0"

import ast
import datetime
import math
import random
from typing import Any, Dict


_DEFAULT_MAX_STEPS = 10000
_DEFAULT_MAX_CALL_DEPTH = 32
_MAX_RANGE_SIZE = 10000

_BLOCKED_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.ClassDef,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Lambda,
    ast.Delete,
    ast.Yield,
    ast.YieldFrom,
    ast.Await,
)

_BLOCKED_CALL_NAMES = {
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "hasattr",
}

_SAFE_FUNCTIONS = {
    "len",
    "min",
    "max",
    "sum",
    "abs",
    "round",
    "int",
    "float",
    "str",
    "bool",
    "sorted",
    "reversed",
    "enumerate",
    "range",
    "zip",
    "any",
    "all",
    "pow",
    "divmod",
    "list",
    "dict",
    "tuple",
}

_SAFE_STR_METHODS = {
    "replace",
    "find",
    "strip",
    "split",
    "splitlines",
    "startswith",
    "endswith",
    "join",
    "lower",
    "upper",
}

_SAFE_LIST_METHODS = {
    "append",
}

_SAFE_DATETIME_ATTRS = {
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "second",
    "microsecond",
}

_SAFE_MATH_FUNCTIONS = {
    "ceil",
    "floor",
    "sqrt",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "atan2",
    "log",
    "log10",
    "exp",
    "pow",
    "fabs",
    "isfinite",
}

_SAFE_MATH_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class _ReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value = value


class _SafeNamespace:
    def __init__(self, name: str):
        self.name = name


class _SafeFunction:
    def __init__(self, name: str, args: ast.arguments, body: list[ast.stmt]):
        self.name = name
        self.arg_names = [arg.arg for arg in args.args]
        self.body = body
        if args.vararg or args.kwarg or args.kwonlyargs or args.defaults:
            raise ValueError(f"Unsupported function signature: {name}")

    def call(self, interpreter: "_SafeScriptInterpreter", args: list[Any]) -> Any:
        if len(args) != len(self.arg_names):
            raise ValueError(
                f"{self.name}() expected {len(self.arg_names)} arguments, got {len(args)}"
            )
        if interpreter.call_depth >= interpreter.max_call_depth:
            raise RuntimeError("Script exceeded maximum call depth")
        frame = dict(zip(self.arg_names, args))
        interpreter.call_depth += 1
        interpreter.frames.append(frame)
        try:
            interpreter._run_block(self.body)
        except _ReturnSignal as signal:
            return signal.value
        finally:
            interpreter.frames.pop()
            interpreter.call_depth -= 1
        return None


class _SafeScriptInterpreter:
    def __init__(
        self,
        variables: Dict[str, Any],
        max_steps: int = _DEFAULT_MAX_STEPS,
        max_call_depth: int = _DEFAULT_MAX_CALL_DEPTH,
    ):
        self.frames = [variables]
        self.max_steps = max_steps
        self.max_call_depth = max_call_depth
        self.steps = 0
        self.call_depth = 0

    def run(self, code: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise ValueError(f"Syntax error in code: {exc}") from exc
        _validate_ast_tree(tree)
        self._run_block(tree.body)
        return self.frames[0]

    def _step(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise RuntimeError("Script exceeded step limit")

    def _run_block(self, statements: list[ast.stmt]) -> None:
        for statement in statements:
            self._step()
            self._run_statement(statement)

    def _run_statement(self, node: ast.stmt) -> None:
        if isinstance(node, ast.Assign):
            value = self._resolve(node.value)
            for target in node.targets:
                self._assign(target, value)
            return
        if isinstance(node, ast.AugAssign):
            current = self._resolve_target(node.target)
            value = self._apply_binop(node.op, current, self._resolve(node.value))
            self._assign(node.target, value)
            return
        if isinstance(node, ast.Expr):
            self._resolve(node.value)
            return
        if isinstance(node, ast.If):
            if self._truthy(self._resolve(node.test)):
                self._run_block(node.body)
            else:
                self._run_block(node.orelse)
            return
        if isinstance(node, ast.For):
            iterable = self._resolve(node.iter)
            count = 0
            for item in iterable:
                count += 1
                if count > _MAX_RANGE_SIZE:
                    raise RuntimeError("Loop exceeded iteration limit")
                self._step()
                self._assign(node.target, item)
                try:
                    self._run_block(node.body)
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    break
            else:
                self._run_block(node.orelse)
            return
        if isinstance(node, ast.While):
            count = 0
            while self._truthy(self._resolve(node.test)):
                count += 1
                if count > _MAX_RANGE_SIZE:
                    raise RuntimeError("Loop exceeded iteration limit")
                self._step()
                try:
                    self._run_block(node.body)
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    break
            else:
                self._run_block(node.orelse)
            return
        if isinstance(node, ast.FunctionDef):
            self._set_name(node.name, _SafeFunction(node.name, node.args, node.body))
            return
        if isinstance(node, ast.Return):
            raise _ReturnSignal(None if node.value is None else self._resolve(node.value))
        if isinstance(node, ast.Break):
            raise _BreakSignal()
        if isinstance(node, ast.Continue):
            raise _ContinueSignal()
        if isinstance(node, ast.Pass):
            return
        raise ValueError(f"Unsupported syntax: {type(node).__name__}")

    def _resolve(self, node: ast.AST) -> Any:
        self._step()
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self._get_name(node.id)
        if isinstance(node, ast.List):
            return [self._resolve(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._resolve(item) for item in node.elts)
        if isinstance(node, ast.Dict):
            return {
                self._resolve(key): self._resolve(value)
                for key, value in zip(node.keys, node.values)
            }
        if isinstance(node, ast.BinOp):
            return self._apply_binop(node.op, self._resolve(node.left), self._resolve(node.right))
        if isinstance(node, ast.UnaryOp):
            return self._apply_unaryop(node.op, self._resolve(node.operand))
        if isinstance(node, ast.BoolOp):
            return self._resolve_boolop(node)
        if isinstance(node, ast.Compare):
            return self._resolve_compare(node)
        if isinstance(node, ast.IfExp):
            return self._resolve(node.body if self._truthy(self._resolve(node.test)) else node.orelse)
        if isinstance(node, ast.Subscript):
            return self._resolve(node.value)[self._resolve_slice(node.slice)]
        if isinstance(node, ast.Slice):
            return self._resolve_slice(node)
        if isinstance(node, ast.Attribute):
            return self._resolve_attribute(self._resolve(node.value), node.attr)
        if isinstance(node, ast.Call):
            return self._resolve_call(node)
        if isinstance(node, ast.JoinedStr):
            return "".join(str(self._resolve_joined_value(value)) for value in node.values)
        if isinstance(node, ast.FormattedValue):
            return self._resolve_joined_value(node)
        raise ValueError(f"Unsupported expression: {type(node).__name__}")

    def _resolve_joined_value(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.FormattedValue):
            value = self._resolve(node.value)
            if node.conversion == 115:
                value = str(value)
            elif node.conversion == 114:
                value = repr(value)
            elif node.conversion == 97:
                value = ascii(value)
            spec = ""
            if node.format_spec is not None:
                spec = str(self._resolve(node.format_spec))
            return format(value, spec)
        return self._resolve(node)

    def _resolve_slice(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Slice):
            lower = None if node.lower is None else self._resolve(node.lower)
            upper = None if node.upper is None else self._resolve(node.upper)
            step = None if node.step is None else self._resolve(node.step)
            return slice(lower, upper, step)
        return self._resolve(node)

    def _resolve_call(self, node: ast.Call) -> Any:
        if node.keywords:
            raise ValueError("Keyword arguments are not supported")
        args = [self._resolve(arg) for arg in node.args]
        if isinstance(node.func, ast.Name):
            return self._call_name(node.func.id, args)
        if isinstance(node.func, ast.Attribute):
            owner = self._resolve(node.func.value)
            return self._call_attribute(owner, node.func.attr, args)
        raise ValueError("Unsupported function call")

    def _call_name(self, name: str, args: list[Any]) -> Any:
        if name.startswith("__"):
            raise ValueError(f"Blocked function call: {name}")
        value = self._find_name(name)
        if isinstance(value, _SafeFunction):
            return value.call(self, args)
        if name in _SAFE_FUNCTIONS:
            return self._call_safe_function(name, args)
        raise ValueError(f"Unsupported function call: {name}")

    def _call_safe_function(self, name: str, args: list[Any]) -> Any:
        if name == "len":
            return len(*args)
        if name == "min":
            return min(*args)
        if name == "max":
            return max(*args)
        if name == "sum":
            return sum(*args)
        if name == "abs":
            return abs(*args)
        if name == "round":
            return round(*args)
        if name == "int":
            return int(*args)
        if name == "float":
            return float(*args)
        if name == "str":
            return str(*args)
        if name == "bool":
            return bool(*args)
        if name == "sorted":
            return sorted(*args)
        if name == "reversed":
            return list(reversed(*args))
        if name == "enumerate":
            return enumerate(*args)
        if name == "range":
            result = range(*args)
            if len(result) > _MAX_RANGE_SIZE:
                raise RuntimeError("range() result is too large")
            return result
        if name == "zip":
            return zip(*args)
        if name == "any":
            return any(*args)
        if name == "all":
            return all(*args)
        if name == "pow":
            return pow(*args)
        if name == "divmod":
            return divmod(*args)
        if name == "list":
            return list(*args)
        if name == "dict":
            return dict(*args)
        if name == "tuple":
            return tuple(*args)
        raise ValueError(f"Unsupported function call: {name}")

    def _call_attribute(self, owner: Any, name: str, args: list[Any]) -> Any:
        if name.startswith("__"):
            raise ValueError(f"Blocked method call: {name}")
        if isinstance(owner, str) and name in _SAFE_STR_METHODS:
            return self._call_str_method(owner, name, args)
        if isinstance(owner, list) and name in _SAFE_LIST_METHODS:
            if name == "append":
                if len(args) != 1:
                    raise ValueError("list.append() expects 1 argument")
                owner.append(args[0])
                return None
        if isinstance(owner, _SafeNamespace):
            return self._call_namespace(owner.name, name, args)
        if isinstance(owner, (datetime.datetime, datetime.date)) and name == "isoformat":
            return owner.isoformat(*args)
        if isinstance(owner, (datetime.datetime, datetime.date)) and name == "strftime":
            return self._call_datetime_strftime(owner, args)
        raise ValueError(f"Unsupported method call: {name}")

    @staticmethod
    def _call_datetime_strftime(owner: datetime.datetime | datetime.date, args: list[Any]) -> str:
        if len(args) != 1:
            raise ValueError("strftime() expects 1 argument")
        fmt = args[0]
        if not isinstance(fmt, str):
            raise ValueError("strftime() format must be str")
        if len(fmt) > 256:
            raise ValueError("strftime() format is too long")
        return owner.strftime(fmt)

    def _call_str_method(self, owner: str, name: str, args: list[Any]) -> Any:
        if name == "replace":
            return owner.replace(*args)
        if name == "find":
            return owner.find(*args)
        if name == "strip":
            return owner.strip(*args)
        if name == "split":
            return owner.split(*args)
        if name == "splitlines":
            return owner.splitlines(*args)
        if name == "startswith":
            return owner.startswith(*args)
        if name == "endswith":
            return owner.endswith(*args)
        if name == "join":
            return owner.join(*args)
        if name == "lower":
            return owner.lower(*args)
        if name == "upper":
            return owner.upper(*args)
        raise ValueError(f"Unsupported string method: {name}")

    def _call_namespace(self, namespace: str, name: str, args: list[Any]) -> Any:
        if namespace == "random":
            if name == "random":
                if args:
                    raise ValueError("random.random() expects no arguments")
                return random.random()
            if name == "randint":
                if len(args) != 2:
                    raise ValueError("random.randint() expects 2 arguments")
                return random.randint(int(args[0]), int(args[1]))
            if name == "uniform":
                if len(args) != 2:
                    raise ValueError("random.uniform() expects 2 arguments")
                return random.uniform(float(args[0]), float(args[1]))
            if name == "choice":
                if len(args) != 1:
                    raise ValueError("random.choice() expects 1 argument")
                return random.choice(args[0])
        if namespace == "datetime.datetime" and name == "now":
            if args:
                raise ValueError("datetime.datetime.now() expects no arguments")
            return datetime.datetime.now()
        if namespace == "datetime.date" and name == "today":
            if args:
                raise ValueError("datetime.date.today() expects no arguments")
            return datetime.date.today()
        if namespace == "math" and name in _SAFE_MATH_FUNCTIONS:
            return self._call_math(name, args)
        raise ValueError(f"Unsupported namespace call: {namespace}.{name}")

    def _call_math(self, name: str, args: list[Any]) -> Any:
        if name == "ceil":
            return math.ceil(*args)
        if name == "floor":
            return math.floor(*args)
        if name == "sqrt":
            return math.sqrt(*args)
        if name == "sin":
            return math.sin(*args)
        if name == "cos":
            return math.cos(*args)
        if name == "tan":
            return math.tan(*args)
        if name == "asin":
            return math.asin(*args)
        if name == "acos":
            return math.acos(*args)
        if name == "atan":
            return math.atan(*args)
        if name == "atan2":
            return math.atan2(*args)
        if name == "log":
            return math.log(*args)
        if name == "log10":
            return math.log10(*args)
        if name == "exp":
            return math.exp(*args)
        if name == "pow":
            return math.pow(*args)
        if name == "fabs":
            return math.fabs(*args)
        if name == "isfinite":
            return math.isfinite(*args)
        raise ValueError(f"Unsupported math function: {name}")

    def _resolve_attribute(self, owner: Any, name: str) -> Any:
        if name.startswith("__"):
            raise ValueError(f"Blocked attribute access: {name}")
        if isinstance(owner, _SafeNamespace):
            namespace_name = f"{owner.name}.{name}"
            if namespace_name in ("datetime.datetime", "datetime.date"):
                return _SafeNamespace(namespace_name)
            if owner.name == "math" and name in _SAFE_MATH_CONSTANTS:
                return _SAFE_MATH_CONSTANTS[name]
            raise ValueError(f"Unsupported namespace attribute: {owner.name}.{name}")
        if isinstance(owner, datetime.datetime) and name in _SAFE_DATETIME_ATTRS:
            return self._datetime_attr(owner, name)
        if isinstance(owner, datetime.date) and name in {"year", "month", "day"}:
            return self._date_attr(owner, name)
        raise ValueError(f"Unsupported attribute access: {name}")

    @staticmethod
    def _datetime_attr(value: datetime.datetime, name: str) -> int:
        if name == "year":
            return value.year
        if name == "month":
            return value.month
        if name == "day":
            return value.day
        if name == "hour":
            return value.hour
        if name == "minute":
            return value.minute
        if name == "second":
            return value.second
        if name == "microsecond":
            return value.microsecond
        raise ValueError(f"Unsupported datetime attribute: {name}")

    @staticmethod
    def _date_attr(value: datetime.date, name: str) -> int:
        if name == "year":
            return value.year
        if name == "month":
            return value.month
        if name == "day":
            return value.day
        raise ValueError(f"Unsupported date attribute: {name}")

    def _apply_binop(self, op: ast.operator, left: Any, right: Any) -> Any:
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Mod):
            return left % right
        if isinstance(op, ast.Pow):
            return left**right
        raise ValueError(f"Unsupported operator: {type(op).__name__}")

    def _apply_unaryop(self, op: ast.unaryop, value: Any) -> Any:
        if isinstance(op, ast.UAdd):
            return +value
        if isinstance(op, ast.USub):
            return -value
        if isinstance(op, ast.Not):
            return not self._truthy(value)
        raise ValueError(f"Unsupported unary operator: {type(op).__name__}")

    def _resolve_boolop(self, node: ast.BoolOp) -> Any:
        if isinstance(node.op, ast.And):
            result = True
            for value_node in node.values:
                result = self._resolve(value_node)
                if not self._truthy(result):
                    return result
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value_node in node.values:
                result = self._resolve(value_node)
                if self._truthy(result):
                    return result
            return result
        raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

    def _resolve_compare(self, node: ast.Compare) -> bool:
        left = self._resolve(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self._resolve(comparator)
            if not self._compare(op, left, right):
                return False
            left = right
        return True

    @staticmethod
    def _compare(op: ast.cmpop, left: Any, right: Any) -> bool:
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.Lt):
            return left < right
        if isinstance(op, ast.LtE):
            return left <= right
        if isinstance(op, ast.Gt):
            return left > right
        if isinstance(op, ast.GtE):
            return left >= right
        if isinstance(op, ast.Is):
            return left is right
        if isinstance(op, ast.IsNot):
            return left is not right
        if isinstance(op, ast.In):
            return left in right
        if isinstance(op, ast.NotIn):
            return left not in right
        raise ValueError(f"Unsupported comparison: {type(op).__name__}")

    def _assign(self, target: ast.AST, value: Any) -> None:
        if isinstance(target, ast.Name):
            self._set_name(target.id, value)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            values = list(value)
            if len(target.elts) != len(values):
                raise ValueError("Unpack target and value length mismatch")
            for child, item in zip(target.elts, values):
                self._assign(child, item)
            return
        if isinstance(target, ast.Subscript):
            owner = self._resolve(target.value)
            owner[self._resolve_slice(target.slice)] = value
            return
        raise ValueError(f"Unsupported assignment target: {type(target).__name__}")

    def _resolve_target(self, target: ast.AST) -> Any:
        if isinstance(target, ast.Name):
            return self._get_name(target.id)
        if isinstance(target, ast.Subscript):
            return self._resolve(target)
        raise ValueError(f"Unsupported assignment target: {type(target).__name__}")

    def _find_name(self, name: str) -> Any:
        if name.startswith("__"):
            raise ValueError(f"Blocked name: {name}")
        for frame in reversed(self.frames):
            if name in frame:
                return frame[name]
        if name in ("random", "datetime", "math"):
            return _SafeNamespace(name)
        return None

    def _get_name(self, name: str) -> Any:
        value = self._find_name(name)
        if value is not None or any(name in frame for frame in self.frames):
            return value
        raise NameError(f"Name is not defined: {name}")

    def _set_name(self, name: str, value: Any) -> None:
        if name.startswith("__"):
            raise ValueError(f"Blocked name: {name}")
        self.frames[-1][name] = value

    @staticmethod
    def _truthy(value: Any) -> bool:
        return bool(value)


class AnyType(str):
    def __ne__(self, __value: object) -> bool:  # allow any connection type
        return False


_ANY_TYPE = AnyType("*")


def _validate_ast_tree(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, _BLOCKED_AST_NODES):
            raise ValueError(
                f"Unsupported syntax in safe mode: {type(node).__name__}"
            )
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(f"Blocked attribute access in safe mode: {node.attr}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError(f"Blocked name in safe mode: {node.id}")

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _BLOCKED_CALL_NAMES:
                raise ValueError(
                    f"Blocked function call in safe mode: {node.func.id}"
                )


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

        locals_dict = _SafeScriptInterpreter(locals_dict).run(code)

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
