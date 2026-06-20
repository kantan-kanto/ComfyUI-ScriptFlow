# ComfyUI-ScriptFlow

**Version:** 1.2.0
**License:** GPL-3.0

A general-purpose calculation node that evaluates a safe Python-like script subset and returns multiple text and numeric outputs based on the inputs.

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
- Safer execution: AST interpreter with restricted syntax and no file/OS access.

## Use Cases
- In Wan2.2 I2V workflows, automatically select a recommended resolution
  (512×384 or 384×512) based on whether the input image is portrait or landscape.
- Batch-generate file names (e.g., local LLM prompt history, output logs).
- Apply conditional logic to control workflow behavior (e.g., switch parameters or routes based on inputs).
- Parse and transform LLM outputs into structured values for downstream nodes.
Dynamically generate numeric parameters (e.g., seeds, thresholds, scaling values) using custom calculations.

## Nodes

### `MultiOutputScript`
**Category:** `utils`

Inputs (optional, connectable):
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
- If you need `FLOAT` values from integer inputs, use the `centi` node.
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

### `centi`
**Category:** `utils`

Inputs (optional, connectable):
- `int_1` (INT)
- `int_2` (INT)
- `int_3` (INT)

Outputs:
- `float_1` (FLOAT) = `int_1 / 100`
- `float_2` (FLOAT) = `int_2 / 100`
- `float_3` (FLOAT) = `int_3 / 100`

Notes:
- If `int_n` is not connected, the corresponding `float_n` output is `None`.
- The node is intentionally minimal and connector-only.

---

## Execution Environment
The script is parsed with Python AST and evaluated by ScriptFlow's safe interpreter. It supports common workflow logic such as assignment, arithmetic, branching, loops, user-defined helper functions, dictionaries, lists, strings, and selected methods.

### Allowed functions
- `len`, `min`, `max`, `sum`, `abs`, `round`
- `int`, `float`, `str`, `bool`
- `sorted`, `reversed`
- `enumerate`, `range`, `zip`
- `any`, `all`, `pow`, `divmod`
- `list`, `dict`, `tuple`

### Allowed namespaces
- `random`: `random`, `randint`, `uniform`, `choice`
- `datetime`: `datetime.now`, `date.today`, date/time fields such as `year`, `month`, `day`, `hour`, `minute`, `second`, plus `isoformat` and `strftime` (`strftime` requires v1.2.0 or later)
- `math`: `ceil`, `floor`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log10`, `exp`, `pow`, `fabs`, `isfinite`, `pi`, `e`, `tau`

### Allowed methods
- `str`: `replace`, `find`, `strip`, `split`, `splitlines`, `startswith`, `endswith`, `join`, `lower`, `upper`
- `list`: `append`

### Not allowed
- `import` statements
- file access (`open`, etc.)
- OS operations (`os`, `sys`)
- dynamic Python execution
- blocked syntax in safe mode: `Import`, `ImportFrom`, `Global`, `Nonlocal`, `ClassDef`, `Try`, `With`, `AsyncWith`, `Lambda`, `Delete`, `Yield`, `Await`
- blocked calls in safe mode: dynamic execution, file/input access, runtime namespace inspection, and dynamic attribute mutation

### Execution Notes
- Using `random` or `datetime` makes outputs non-deterministic.
- `datetime.strftime(...)` is supported in v1.2.0 or later for concise timestamp formatting:
  ```python
  now = datetime.datetime.now()
  ot1 = now.strftime("%Y%m%d%H%M%S")
  ```
- For versions earlier than v1.2.0, format the same timestamp manually:
  ```python
  now = datetime.datetime.now()
  ot1 = f'{now.year:04d}{now.month:02d}{now.day:02d}{now.hour:02d}{now.minute:02d}{now.second:02d}'
  ```
- Type mismatches raise an error and stop execution.
- Safe mode validates AST before evaluation and stops scripts that exceed the step or loop limit.
- Use only trusted scripts/workflows. Do not run untrusted code from unknown sources.

## Examples

### Demo
![Demo](images/MultiOutputScript.gif)

Demonstrates running the sample workflow with a landscape image and a portrait image.

### Example Workflow

```
examples/
 ├─ example_workflow.json
```

## Application Recipes

### Convert `LLM Dialogue Cycle` transcript text to `dialogue_segments_json`

<details>
<summary>Show ComfyUI-LLM-Session transcript conversion recipe</summary>

`ComfyUI-LLM-Session` returns the full result of `LLM Dialogue Cycle` as `transcript_text`.
You can connect that text to `MultiOutputScript.in_text_1` and paste the script below into
the `code` field to generate a speaker-tagged JSON text for downstream dialogue TTS nodes.

Recommended workflow:

```text
LLM Dialogue Cycle
  -> transcript_text
  -> MultiOutputScript.in_text_1
  -> MultiOutputScript.out_text_1
  -> dialogue_segments_json input of a TTS node
```

Paste this code into `MultiOutputScript.code`:

```python
# Convert ComfyUI-LLM-Session "LLM Dialogue Cycle" transcript_text
# into dialogue_segments_json for TTS.
# Only text inside Japanese corner quotes 「...」 is used as spoken dialogue.
#
# Input:
#   it1: transcript_text
#
# Output:
#   ot1: JSON text with schema "kantan.dialogue.v1"
#
# Expected transcript lines:
#   [2026-05-16T12:00:00] USER -> A: initial prompt
#   [2026-05-16T12:00:01] A: 彼女は少し考えた。「こんにちは。」
#   [2026-05-16T12:00:02] B: 彼は笑った。「やあ。」「調子はどう？」
#
# The parser also accepts the unicode arrow form:
#   USER → A:

def json_escape(value):
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s

def extract_spoken_text(value):
    source = str(value)
    parts = []
    position = 0

    while position < len(source):
        start = source.find("「", position)
        if start < 0:
            position = len(source)
        else:
            end = source.find("」", start + 1)
            if end < 0:
                position = len(source)
            else:
                spoken = source[start + 1:end].strip()
                if spoken:
                    parts.append(spoken)
                position = end + 1

    return "\n".join(parts)

transcript = str(it1 or "")
lines = transcript.splitlines()
utterances = []
current = None

for raw_line in lines:
    line = str(raw_line)
    speaker = None
    text = None
    timestamp = ""

    if line.startswith("[") and "] " in line:
        close_index = line.find("] ")
        timestamp = line[1:close_index]
        rest = line[close_index + 2:]

        if rest.startswith("A:"):
            speaker = "A"
            text = rest[2:].strip()
        elif rest.startswith("B:"):
            speaker = "B"
            text = rest[2:].strip()
        elif rest.startswith("USER -> A:"):
            speaker = "USER"
            text = rest[len("USER -> A:"):].strip()
        elif rest.startswith("USER → A:"):
            speaker = "USER"
            text = rest[len("USER → A:"):].strip()

    if speaker == "A" or speaker == "B":
        if current is not None:
            utterances.append(current)
        current = {
            "speaker": speaker,
            "text": text,
            "timestamp": timestamp,
        }
    else:
        if current is not None:
            if current["text"]:
                current["text"] = current["text"] + "\n" + line
            else:
                current["text"] = line

if current is not None:
    utterances.append(current)

items = []
index = 1
for u in utterances:
    spoken_text = extract_spoken_text(u["text"])
    if not spoken_text:
        continue

    item = (
        '{"index":'
        + str(index)
        + ',"speaker":"'
        + json_escape(u["speaker"])
        + '","text":"'
        + json_escape(spoken_text)
        + '","timestamp":"'
        + json_escape(u["timestamp"])
        + '"}'
    )
    items.append(item)
    index = index + 1

ot1 = (
    '{"schema":"kantan.dialogue.v1",'
    + '"source":"ComfyUI-LLM-Session LLM Dialogue Cycle",'
    + '"utterances":['
    + ",".join(items)
    + "]}"
)
```

The resulting `out_text_1` is a JSON string like this:

```json
{
  "schema": "kantan.dialogue.v1",
    "source": "ComfyUI-LLM-Session LLM Dialogue Cycle",
    "utterances": [
      {
        "index": 1,
        "speaker": "A",
        "text": "こんにちは。",
        "timestamp": "2026-05-16T12:00:01"
      },
      {
        "index": 2,
        "speaker": "B",
        "text": "やあ。\n調子はどう？",
        "timestamp": "2026-05-16T12:00:02"
      }
  ]
}
```

Notes:

- `USER -> A` / `USER → A` is intentionally skipped so TTS reads only character dialogue.
- Multiline model output is kept inside the previous `A` or `B` utterance.
- Only text inside `「...」` is emitted to `utterances[].text`; narration and inner thoughts outside quotes are skipped.
- If one utterance contains multiple quoted lines, they are joined with newlines.
- Utterances without `「...」` are omitted from the TTS script.
- `out_text_2`, `out_text_3`, and numeric outputs are unused by this recipe.

</details>

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
### 1.2.0
- Replaced direct Python execution with a safe AST interpreter for ComfyUI Registry compatibility.
- Added Python-subset support for helper functions, loops, dictionaries, lists, string methods, f-strings, `random`, `datetime`, and `math`.
- Replaced trace-based timeout handling with step and loop limits.
- Kept existing `MultiOutputScript` inputs and outputs unchanged.

### 1.1.1
- Added safe-mode AST validation before script execution.
- Blocked unsafe syntax (`Import`, `ImportFrom`, `Global`, `Nonlocal`, `ClassDef`, `Try`, `With`, `AsyncWith`).
- Blocked unsafe dynamic execution, file/input access, namespace inspection, and dynamic attribute mutation calls.
- Added execution timeout guard (`1.5s` default) to stop runaway scripts.
- Updated security notes for trusted-workflow usage.

### 1.1.0
Added `centi` node (`utils`).
- Minimal connector-only utility node.
- Three optional integer inputs: `int_1`, `int_2`, `int_3`.
- Three float outputs: `float_1`, `float_2`, `float_3`.
- Each connected input is converted by `int_n / 100`; unconnected inputs return `None`.

### 1.0.1
- Improved documentation and project metadata.

### 1.0.0
- Initial release
