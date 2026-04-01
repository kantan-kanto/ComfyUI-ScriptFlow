# ComfyUI-ScriptFlow

**Version:** 1.0.1
**License:** GPL-3.0

A general-purpose calculation node that executes user-written Python code and returns multiple text and numeric outputs based on the inputs.

This custom node accepts numbers (int/float) and text (string) as inputs, runs calculations and logical operations internally, and returns multiple values through separate output ports. It consolidates workflows that previously required combining several basic nodes into a single node.

## Installation

1. Navigate to the `ComfyUI/custom_nodes/` directory.
2. Clone this repository:
   ```bash
   git clone https://github.com/kantan-kanto/ComfyUI-ScriptFlow
   ```
3. Restart ComfyUI.

## Key Features
- Multiple inputs: freely combine numeric and text inputs.
- Calculations and logic: supports arithmetic, comparison, and simple conditional branching.
- Multiple outputs: pass results to downstream nodes via separate output ports.
- Safer execution: restricted environment (no file/OS access).

## Use Cases
- In Wan2.2 I2V workflows, automatically select a recommended resolution
  (512×384 or 384×512) based on whether the input image is portrait or landscape.
- Batch-generate file names (e.g., local LLM prompt history, output logs).
- Apply conditional logic to control workflow behavior (e.g., switch parameters or routes based on inputs).
- Parse and transform LLM outputs into structured values for downstream nodes.
Dynamically generate numeric parameters (e.g., seeds, thresholds, scaling values) using custom calculations.

## Node
**Name:** `MultiOutputScript`  
**Category:** `utils`

### UI Ports (Current)
Inputs (connectable):
- `in_text_1` (accepts any input; validated as `str` at runtime)
- `in_text_2` (accepts any input; validated as `str` at runtime)
- `in_text_3` (accepts any input; validated as `str` at runtime)
- `in_value_1` (accepts any input; validated as `int` or `float` at runtime)
- `in_value_2` (accepts any input; validated as `int` or `float` at runtime)
- `in_value_3` (accepts any input; validated as `int` or `float` at runtime)
- `code` (multiline string)

Outputs:
- `out_text_1` (STRING)
- `out_text_2` (STRING)
- `out_text_3` (STRING)
- `out_value_1` (INT)
- `out_value_2` (INT)
- `out_value_3` (INT)

Notes on numeric outputs:
- Outputs are `INT`.
- If a value is a float, the fractional part is truncated on output.
- If you prefer rounding or ceiling, handle it in the script (e.g., `round(...)`, `math.ceil(...)`).

### Script Variables
Use the following variables inside `code`:
- Inputs: `it1`, `it2`, `it3`, `iv1`, `iv2`, `iv3`
- Outputs: `ot1`, `ot2`, `ot3`, `ov1`, `ov2`, `ov3`

Unassigned outputs default to `None`.

### Script Example
```python
# Example: keep landscape at 512x384, portrait at 384x512
# Connect GetImageSize width/height to in_value_1/in_value_2
# iv1: image width, iv2: image height
w, h = iv1, iv2
ov1, ov2 = (512, 384) if w >= h else (384, 512)
```

---

## Execution Environment
The script is executed using:
```python
exec(code, globals_dict, locals_dict)
```

### Allowed builtins
- `len`, `min`, `max`, `sum`, `abs`, `round`
- `int`, `float`, `str`, `bool`
- `sorted`, `reversed`
- `enumerate`, `range`, `zip`, `map`, `filter`
- `any`, `all`, `pow`, `divmod`
- `list`, `dict`, `tuple`

### Allowed modules
- `random`
- `datetime`
- `math`

### Not allowed
- `import` statements
- file access (`open`, etc.)
- OS operations (`os`, `sys`)
- re-running `eval`/`exec`

### Execution Notes
- Using `random` or `datetime` makes outputs non-deterministic.
- Type mismatches raise an error and stop execution.

## Examples

### Demo
![Demo](images/MultiOutputScript.gif)

Demonstrates running the sample workflow with a landscape image and a portrait image.

### Example Workflow

```
examples/
 ├─ example_workflow.json
```

## License

This project is licensed under the **GNU General Public License v3.0**.

**Copyright (C) 2026 kantan-kanto**  
GitHub: https://github.com/kantan-kanto

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see https://www.gnu.org/licenses/.

## Support

- **Issues**: Report bugs or request features via GitHub Issues
- **Examples**: Check [examples/](examples/) for workflow templates

---

## Release Notes
### 1.0.0
- Initial release
