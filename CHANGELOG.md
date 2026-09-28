# Changelog

All notable changes to ComfyUI-ScriptFlow will be documented in this file.


## [Unreleased]


## [1.3.0] - 2026-09-29

- Added `MultiOutputScript (Jev)` node (`utils`)
  - Same inputs, outputs, and script rules as `MultiOutputScript`, plus a `jev` namespace that answers typed questions about text
  - `jev.yes(state, question[, threshold])`, `jev.noul(state, question)`, `jev.choice(state, question, options)`, `jev.probabilities(state, question, options)`, and `jev.score(state, question, levels)`
  - Using a `jev.noul()` probability directly as a condition raises an error instead of always being true
  - Identical questions within a run are asked only once; `max_jev_calls` limits API requests or model evaluations per run
  - Default script picks one of eight aspect ratios for the prompt in `in_text_1`, sizes it to the megapixels in `in_value_1`, and lists every ratio's probability in `out_text_1`

- Added two backends selected by the `model` input; scripts are the same for both
  - `TypeSafe API`: asks TypeSafe AI's Jev through the optional `typesafe-sdk` package, with the API key read from `api_key.txt` in the node's installation directory on every run
  - Local GGUF models as a fallback when the Jev API is not available: models under `models/LLM` and `models/text_encoders`, including paths registered in `extra_model_paths.yaml` on other drives
  - The local backend reads the decision from next-token probabilities of lettered options in one forward pass through the optional `llama-cpp-python` package, adapted from SemIf (OpenJev, MIT License); no text is generated and nothing is sent over the network
  - The local model is loaded on the first `jev` question of a run and always unloaded when the run ends, freeing VRAM on CUDA, Intel XPU, and other ComfyUI devices

- Kept `MultiOutputScript` and `centi` unchanged
  - `jev` is not available in `MultiOutputScript`, which still makes no network requests and loads no models
  - Existing nodes do not require `typesafe-sdk` or `llama-cpp-python`

- Added `api_key.txt` to `.gitignore`
- Moved release notes from `README.md` to `CHANGELOG.md`
- Replaced the README demo with a `MultiOutputScript (Jev)` demo at the top of the README


## [1.2.0] - 2026-05-31

- Replaced direct Python execution with a safe AST interpreter for ComfyUI Registry compatibility.
- Added Python-subset support for helper functions, loops, dictionaries, lists, string methods, f-strings, `random`, `datetime`, and `math`.
- Replaced trace-based timeout handling with step and loop limits.
- Kept existing `MultiOutputScript` inputs and outputs unchanged.


## [1.1.1] - 2026-04-06

- Added safe-mode AST validation before script execution.
- Blocked unsafe syntax (`Import`, `ImportFrom`, `Global`, `Nonlocal`, `ClassDef`, `Try`, `With`, `AsyncWith`).
- Blocked unsafe dynamic execution, file/input access, namespace inspection, and dynamic attribute mutation calls.
- Added execution timeout guard (`1.5s` default) to stop runaway scripts.
- Updated security notes for trusted-workflow usage.


## [1.1.0] - 2026-04-03

Added `centi` node (`utils`).
- Minimal connector-only utility node.
- Three optional integer inputs: `int_1`, `int_2`, `int_3`.
- Three float outputs: `float_1`, `float_2`, `float_3`.
- Each connected input is converted by `int_n / 100`; unconnected inputs return `None`.


## [1.0.1] - 2026-04-01

- Improved documentation and project metadata.


## [1.0.0] - 2026-03-31

- Initial release
