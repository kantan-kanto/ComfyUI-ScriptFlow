# ComfyUI-ScriptFlow
[en | [ja](README.ja.md)]

**Version:** 1.3.4
**License:** GPL-3.0

Safe Python-like script node for ComfyUI with a System One decision model.
Ask yes/no, choice, and score questions via TypeSafe AI's Jev API, with local GGUF LLMs as a fallback, and use the answer directly in an `if` statement.

![MultiOutputScript (Jev) demo](images/MultiOutputScript_Jev.gif)

`MultiOutputScript (Jev)` picks an aspect ratio for a text prompt through the TypeSafe API, lists every ratio's probability, and passes the width and height to an image node.

A simplified version of the demo: connect a text prompt to `in_text_1`, and the answer picks the width and height.

```python
if jev.yes(it1, "Does a portrait orientation suit this prompt?"):
    ov1, ov2 = 832, 1280
else:
    ov1, ov2 = 1280, 832
```

A System One model answers with probabilities in a single fast pass instead of generating text, so the answer can drive workflow logic directly.

Multiple inputs and outputs let one node handle math, logic, text editing, conditional routing, resolution selection, filename generation, and more — work that previously took several basic nodes. Scripts run in a restricted interpreter with no file or OS access.

## Installation

1. Navigate to the `ComfyUI/custom_nodes/` directory.
2. Clone this repository:
   ```bash
   git clone https://github.com/kantan-kanto/ComfyUI-ScriptFlow
   ```
3. Restart ComfyUI.

The `MultiOutputScript` and `centi` nodes need no extra packages. `MultiOutputScript (Jev)` needs the setup below for the backend you use.

### For `MultiOutputScript (Jev)`

#### TypeSafe API

1. Install the SDK in the Python environment that runs ComfyUI:
   ```bash
   pip install typesafe-sdk
   ```
2. Create `api_key.txt` in the actual installation directory of this custom node and add your TypeSafe API key (single line, no quotes):
   ```
   ComfyUI/custom_nodes/<your-installation-folder>/api_key.txt
   ```
   The key is read from this file on every run. `api_key.txt` is listed in `.gitignore`; never commit it.

#### Local models (fallback)

- Install [llama-cpp-python](https://github.com/JamePeng/llama-cpp-python) in the Python environment that runs ComfyUI. Tested with the JamePeng fork and the upstream [abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python) 0.3.35.
- Put an instruction-tuned GGUF model in `ComfyUI/models/LLM` (or `models/text_encoders`). The GGUF must include a chat template (`tokenizer.chat_template` metadata), as most instruction-tuned GGUFs do. Tested with Qwen3.5-9B Q8_0 and Gemma-4-E4B Q8.
- To use [Clef](https://huggingface.co/Cloudflare/clef-flash), Cloudflare's open-weight decision model, put a Clef GGUF in the llama.cpp native format, such as [ggml-org/Clef-Flash-GGUF](https://huggingface.co/ggml-org/Clef-Flash-GGUF), in the same folder. It needs the JamePeng fork of llama-cpp-python 0.4.2 or later. A Clef GGUF converted as an ordinary chat model is treated as a general model and does not use Clef's decision head. Tested with Clef-Flash Q8_0 on Windows (Intel Arc, SYCL build); Linux and macOS are untested.
- To use [d1](https://huggingface.co/LiquidAI/d1-3B), Liquid AI's open-weight decision model, put a d1 GGUF, such as [LiquidAI/d1-3B-GGUF](https://huggingface.co/LiquidAI/d1-3B-GGUF), in the same folder. It needs a llama-cpp-python build that loads LFM2 models. The `mmproj` file is not needed. Tested with d1-3B Q8_0 and the JamePeng fork of llama-cpp-python 0.4.2 on Windows (Intel Arc, SYCL build); Linux and macOS are untested.

## Key Features
- Multiple inputs: freely combine numeric and text inputs.
- Calculations and logic: supports arithmetic, comparison, and simple conditional branching.
- Multiple outputs: pass results to downstream nodes via separate output ports.
- AI decisions: `jev.yes` / `jev.choice` / `jev.score` in `MultiOutputScript (Jev)`, with probabilities, through TypeSafe AI's Jev API or a local GGUF model as a fallback.
- Safer execution: scripts run in an AST interpreter with restricted syntax and no file/OS access. Only the Jev node's `jev` functions reach a model or the TypeSafe API.

## Use Cases
- In Wan2.2 I2V workflows, automatically select a recommended resolution
  (512×384 or 384×512) based on whether the input image is portrait or landscape.
- Batch-generate file names (e.g., local LLM prompt history, output logs).
- Apply conditional logic to control workflow behavior (e.g., switch parameters or routes based on inputs).
- Parse and transform LLM outputs into structured values for downstream nodes.
- Dynamically generate numeric parameters (e.g., seeds, thresholds, scaling values) using custom calculations.
- Pick an aspect ratio and size for a text prompt before generation, with the probability of every ratio (Jev node default script).
- Route workflows by the meaning of text, e.g. check whether a prompt describes a night scene or classify its main subject.

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

### `MultiOutputScript (Jev)`
**Category:** `utils`

Same inputs, outputs, and script rules as `MultiOutputScript`, plus a `jev` namespace that asks [Jev](https://typesafe.ai), TypeSafe AI's decision model, typed questions about text and lets scripts branch on the answer.

- **TypeSafe API** (primary): sends the questions to Jev over the internet.
- **Local GGUF model** (fallback): for when the Jev API is not available, or when text must stay on your machine. It approximates Jev-style decisions with a general instruction-tuned model, reading the answer from next-token probabilities of lettered options in one forward pass, following [SemIf (OpenJev)](https://github.com/TheoLeeCJ/SemIf-OpenJev). No text is generated and nothing is sent over the network. Answers and probabilities differ from Jev's.
- **Local Clef model**: [Clef](https://huggingface.co/Cloudflare/clef-flash) is an open-weight decision model with the same question types as Jev. A GGUF whose `general.architecture` metadata is `clef` is treated as a Clef model. Selecting one uses the model's decision head instead of the approximation above, and answers every question about one `state` in one forward pass: the `state` and the questions are laid out in Clef's input format, and the score the decision head gives each option is turned into probabilities with a softmax per question. No text is generated and nothing is sent over the network. Answers and probabilities differ from Jev's.
- **Local d1 model**: [d1](https://huggingface.co/LiquidAI/d1-3B) is an open-weight decision model with the same question types as Jev. A GGUF whose `lfm2.decision.type` metadata is `lfm2-d1` is treated as a d1 model. Selecting one asks each question in the prompt format d1 was tuned on instead of the lettered options above, and reads the answer from the next-token probabilities of the reply d1 was tuned to give: yes or no for `jev.noul`, an option code for `jev.choice`, and a digit for `jev.score`. No text is generated and nothing is sent over the network. Answers and probabilities differ from Jev's.

Scripts are the same for all of them. See [Installation](#installation) for the setup of each backend.

Extra inputs:
- `model`: `TypeSafe API`, or a local GGUF model (`mmproj-*` files are hidden).
- `max_jev_calls` (INT, default 8): maximum Jev requests per run. Questions about the same `state` share one request (see [Batched questions](#batched-questions)), so this limits requests, not questions. A run stops with an error before sending requests that would exceed it. Identical questions within a run are asked only once.

Functions (`state` is a string, dict, or list; text only):
- `jev.yes(state, question[, threshold])` → `bool` (yes-probability ≥ `threshold`, default `0.5`)
- `jev.noul(state, question)` → yes-probability (`0.0`–`1.0`). Compare it with a threshold; using it directly as a condition raises an error.
- `jev.choice(state, question, options)` → the most likely option (`str`). `options` is a list of labels, or a dict of labels to descriptions (2–16 options for general local models).
- `jev.probabilities(state, question, options)` → `dict` of each option to its probability (sums to `1.0`). Same `options` as `jev.choice`; asking both with the same arguments asks the model once.
- `jev.score(state, question, levels)` → expected level (`float`, `0` to `len(levels) - 1`) for ordered level descriptions (2–16 levels for general local models)

```python
# it1: a prompt text
if jev.yes(it1, "Does this prompt describe a night scene?", 0.7):
    ov1 = 30
else:
    ov1 = 20

kind = jev.choice(it1, "Which orientation suits this prompt?", ["portrait", "landscape"])
ov2, ov3 = (384, 512) if kind == "portrait" else (512, 384)

probs = jev.probabilities(it1, "Which orientation suits this prompt?", ["portrait", "landscape"])
ot1 = f"{kind} (portrait: {probs['portrait']:.3f}, landscape: {probs['landscape']:.3f})"
```

The node's default script picks one of eight aspect ratios for the prompt in `it1`, sizes it to the megapixels in `in_value_1` (default `1.0` when unconnected; width and height rounded to multiples of 64), outputs the width and height to `out_value_1` / `out_value_2`, and lists every ratio's probability in `out_text_1`.

Each function asks one question. The table shows the equivalent code written with the [TypeSafe Python SDK](https://pypi.org/project/typesafe-sdk/):

| ScriptFlow | TypeSafe SDK |
| --- | --- |
| `jev.noul(state, q)` | `client.system_one(state=state, questions={"q": Noul(instructions=q)}).answers["q"].noul` |
| `jev.yes(state, q, t)` | `... .answers["q"].noul >= t` |
| `jev.choice(state, q, options)` | `client.system_one(state=state, questions={"q": Choice(instructions=q, criteria=options)}).answers["q"].choice` |
| `jev.probabilities(state, q, options)` | `... .answers["q"].probabilities` (same request as `jev.choice`) |
| `jev.score(state, q, levels)` | `client.system_one(state=state, questions={"q": Score(instructions=q, criteria=levels)}).answers["q"].score` |

A list of `options` is sent as `criteria={label: None, ...}`. `confidence`, the Score level probabilities, and Noul `criteria` are not exposed.

#### Batched questions

Questions are sent in batches where possible:

1. While the script runs, each `jev` question is queued instead of being sent.
2. Storing an answer in a variable or list, passing it to a function you defined, or calling `float()` on it keeps the run going. The run stops when the script first uses an answer's value: in an `if` condition, a comparison, arithmetic, an f-string, `sorted`, `join`, an output, and so on.
3. The queued questions are sent, one request per `state`, and the script runs again from the start. Answered questions now return their values, and new questions are queued the same way.

Requests for different states are sent in parallel with the TypeSafe API, and one after another with a local model. A script asks the same questions and produces the same outputs as when each question is asked on its own. Within one run, every rerun starts from the same `random` state and `datetime.datetime.now()` time, so the questions do not change between reruns.

In this example, `q1` and `q2` go in one request because `a` is not used until the `if`. `q3` is sent in a second request after `a` is known:

```python
a = jev.noul(it1, "q1")
b = jev.noul(it1, "q2")
if a > 0.5:
    c = jev.noul(it1, "q3")
```

To ask many questions in one request, keep the `state` the same and put what differs between questions in the question text.

With the TypeSafe API, each request is one `system_one` call of the [TypeSafe Python SDK](https://pypi.org/project/typesafe-sdk/). The first request of the example above is:

```python
client.system_one(state=it1, questions={"q0": Noul(instructions="q1"), "q1": Noul(instructions="q2")})
```

Notes:
- The TypeSafe API sends `state` and questions over the internet. Do not use it with text you cannot share externally.
- A general local model takes one forward pass per question (about 1–1.5 s with a 4B–9B model on GPU). A Clef model takes one forward pass per request, for all of its questions (about 3 s for a 300-token request with Clef-Flash Q8_0 on an Intel Arc integrated GPU). A d1 model takes one forward pass per question (about 0.5 s with d1-3B Q8_0 on the same GPU). The model is loaded on the first question of each run (several seconds) and unloaded when the run ends to free VRAM for the rest of the workflow.
- Local probabilities are uncalibrated and depend on the model; test thresholds on your own inputs.
- In tests with Qwen3.5-9B, a general local model answered "no" when the text did not settle the question, so a low `jev.noul` value can mean "cannot say it is true" rather than "unlikely". To tell the two apart, ask about both the statement and its negation, or have the model pick a percentage level with `jev.score`. See [How general local models answer uncertain questions](docs/local-model-uncertainty/README.md) for the measurements and example scripts.
- A local prompt is limited to 8,192 tokens: the `state` and one question for a general model, or the `state` and all questions of a request for Clef. Clef is text only.
- With a d1 model, `jev.choice` and `jev.probabilities` take 2 to 26 options and `jev.score` takes 2 to 10 levels. Images are not supported.
- In tests with d1-3B, the probabilities of similar options were spread out, so a single different option could come first: in the aspect ratio example, three portrait ratios shared 0.49 and `1:1` was chosen with 0.35. When options fall into groups, add up `jev.probabilities` by group before picking one.
- Each run prints `[ComfyUI-ScriptFlow] Jev requests: N, states: S, questions: Q, responses: M` to the console: requests sent, distinct states, questions asked, and requests answered. Fewer responses than requests means a request failed. Questions answered from the run's cache are not counted.
- When `typesafe-sdk` is installed, the `httpx2` (the SDK's HTTP client) and `typesafe_sdk` loggers are set to WARNING, so per-request INFO lines are not shown.
- `MultiOutputScript` never loads a model or makes network requests; `jev` is not available there.
- This project is independent and not affiliated with TypeSafe AI.

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
- `jev.yes`, `jev.noul`, `jev.choice`, `jev.probabilities`, `jev.score` (`MultiOutputScript (Jev)` only; see [its section](#multioutputscript-jev))

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
- In v1.3.2 or later, `datetime.datetime.now()` and `datetime.date.today()` return the time the run started, so repeated calls in one script return the same value.
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

### Check a prompt enhancer's output against its system prompt

<details>
<summary>Show prompt enhancer rule check recipe</summary>

A prompt enhancer is an LLM that rewrites a short request into a prompt for an image or video model,
following the rules in its system prompt. This recipe splits that system prompt into rules, asks Jev
whether the enhancer's output breaks each one, and reports a score and the rules that are likely broken.
It reads the rules from the system prompt you connect, so it is not tied to one enhancer.
Paste the script below into the `code` field of `MultiOutputScript (Jev)`.

Recommended workflow:

```text
enhancer output            -> MultiOutputScript (Jev).in_text_1
system prompt              -> MultiOutputScript (Jev).in_text_2
user request (optional)    -> MultiOutputScript (Jev).in_text_3
MultiOutputScript (Jev)
  -> out_text_1   report
  -> out_text_2   likely violations only
  -> out_text_3   rules extracted from the system prompt
  -> out_value_1  adherence score (0-100)
  -> out_value_2  number of likely violations
```

Paste this code into `MultiOutputScript (Jev).code`:

```python
# Score how well a prompt enhancer's output follows its system prompt.
#
# Input:
#   it1: the enhancer's output
#   it2: the system prompt, as plain text or as the text of a JSON config
#        that has a "system_prompt" key
#   it3: the user's request (optional; used by rules that refer to it)
#
# Output:
#   ot1: report, most likely violations first
#   ot2: likely violations only
#   ot3: the rules extracted from the system prompt
#   ov1: adherence score (0-100)
#   ov2: number of likely violations
#
# Jev requests: 2 (one for all rules, one for the overall rating),
# or 1 with OVERALL = False.

MAX_RULES = 40          # rules beyond this are not checked
THRESHOLD = 0.5         # a rule counts as broken at this probability or above
SKIP_HEADINGS = ["example", "sample", "thinking", "reasoning", "例", "思考", "手順"]   # sections whose heading has one of these are skipped
OVERALL = True          # also rate the output against the whole system prompt

def has_any(s, words):
    for w in words:
        if w in s:
            return True
    return False

output = str(it1 or "").strip()
sp = str(it2 or "")
user_text = str(it3 or "").strip()

if sp.strip().startswith("{"):
    k = sp.find('"system_prompt"')
    if k < 0:
        raise ValueError("The JSON has no system_prompt key")
    tail = sp[sp.find('"', sp.find(":", k) + 1) + 1:]
    tail = tail.replace("\\\\", "\x00").replace('\\"', "\x01")
    sp = tail[:tail.find('"')].replace("\\n", "\n").replace("\\t", "\t").replace("\x01", '"').replace("\x00", "\\")

# Under each heading, a line that starts at the left margin is one rule.
# Indented lines belong to the rule above them.
rules = []
heading = ""
skip = False
for line in sp.splitlines():
    s = line.strip()
    if not s:
        continue
    if s[0] in "【#[-":
        if s[:3] == "---":
            continue
        if s[0] != "-" and (s[0] != "[" or s[-1] == "]"):
            heading = s
            skip = has_any(s.lower(), SKIP_HEADINGS)
            continue
    if skip:
        continue
    if rules and line[:1] in " \t　":
        rules[-1][1] = rules[-1][1] + "\n" + s
    else:
        rules.append([heading, s])

truncated = len(rules) > MAX_RULES
rules = rules[:MAX_RULES]

# Every rule shares one state and goes in the question text,
# so all rules are asked in one request.
state = {"output": output}
if user_text:
    state["user_input"] = user_text
results = []
for r in rules:
    q = "Does the output clearly break the instruction below? Answer no if the instruction does not concern the output, or if judging it needs a reference image or anything else not given here."
    if r[0]:
        q += "\nSection: " + r[0]
    p = jev.noul(state, q + "\nInstruction: " + r[1])
    results.append([float(p), r[0], r[1]])

# The overall rating needs the whole system prompt as state, so it is a second request.
# Asking it before the sort below sends it together with the rules.
if OVERALL:
    overall_state = {"system_prompt": sp, "output": output}
    if user_text:
        overall_state["user_input"] = user_text
    level = jev.score(overall_state, "How faithfully does the output follow the system prompt as a whole?", ["ignores most instructions", "follows some instructions", "follows about half", "follows most instructions", "follows every instruction"])

ranked = list(reversed(sorted(results)))
lines = []
issues = []
total = 0.0
for r in ranked:
    total += r[0]
    bad = r[0] >= THRESHOLD
    line = ("[BREAK?] " if bad else "[OK]     ") + f"p={r[0]:.2f} {r[1]} " + r[2].splitlines()[0][:70]
    lines.append(line)
    if bad:
        issues.append(line)

score = round(100 * (1 - total / len(ranked))) if ranked else 0
header = f"Adherence: {score}/100 ({len(issues)} of {len(ranked)} rules likely broken)"
if truncated:
    header += f"\nOnly the first {MAX_RULES} rules were checked"
if OVERALL:
    header += f"\nOverall: {level:.2f} / 4"

ot1 = header + "\n" + "\n".join(lines)
ot2 = header + "\n" + "\n".join(issues)
rule_lines = []
for i, r in enumerate(rules):
    rule_lines.append(f"{i + 1}. {r[0]} {r[1]}")
ot3 = "\n\n".join(rule_lines)
ov1 = score
ov2 = len(issues)
```

The resulting `out_text_1` is a report like this:

```text
Adherence: 71/100 (1 of 4 rules likely broken)
Overall: 3.10 / 4
[BREAK?] p=0.74 ## Output format - Do not write sentences.
[OK]     p=0.21  You are a prompt enhancer for SDXL.
[OK]     p=0.12 ## Output format - Start with "masterpiece, best quality".
[OK]     p=0.09 ## Output format - Output a single line of comma-separated tags.
```

Notes:

- Requires v1.3.2 or later, where questions about the same `state` share one request. The script makes 2 requests, so set `max_jev_calls` to 2 or more.
- `p` is Jev's probability that the output breaks the rule. It is a judgment, not a check: in testing it flagged some rules that were followed and missed some that were broken, and values near `THRESHOLD` changed between runs. Treat the flagged rules as candidates to review.
- The recipe was developed with Jev through the TypeSafe API. In testing, a local Clef-Flash model flagged most rules, including rules the output followed, so it is not recommended for this recipe.
- A rule that needs something the script does not have, such as a reference image, cannot be judged. Connect the user request to `in_text_3` for rules that refer to it.
- `in_text_2` takes the system prompt as plain text, or the text of a JSON config with a `"system_prompt"` key. `\uXXXX` escapes in the JSON are not decoded.
- Lines starting with `#`, `【`, or `[...]` are headings. Under a heading, each line at the left margin is one rule, and indented lines belong to the rule above. Check `out_text_3` to see how your system prompt was split.
- Sections whose heading contains a word in `SKIP_HEADINGS` are skipped, so examples and thinking steps are not judged as rules.
- Only the first `MAX_RULES` rules are checked. A very long system prompt exceeds the script step limit; see [Long system prompts](#long-system-prompts) below.
- With the TypeSafe API, the system prompt, the enhancer output, and the user request are sent over the internet.
- `out_text_3` and the numeric outputs are optional; `out_value_3` is unused.

#### Long system prompts

The script above checks the system prompt one line at a time, so a system prompt of several hundred lines stops with `Script exceeded step limit`.
For those, use the script below. It cuts the system prompt into parts of about `PART_CHARS` characters at blank lines,
and asks Jev whether the output breaks any instruction in each part. Connect the inputs and outputs the same way.

```python
# Score how well a prompt enhancer's output follows a long system prompt.
# The system prompt is cut into parts of about PART_CHARS characters at blank lines,
# and Jev is asked whether the output breaks any instruction in each part.
#
# Input:
#   it1: the enhancer's output
#   it2: the system prompt, as plain text or as the text of a JSON config
#        that has a "system_prompt" key
#   it3: the user's request (optional; used by instructions that refer to it)
#
# Output:
#   ot1: report, most likely violations first
#   ot2: likely violations only
#   ot3: the parts the system prompt was cut into
#   ov1: adherence score (0-100)
#   ov2: number of parts with a likely violation
#
# Jev requests: 2 (one for all parts, one for the overall rating),
# or 1 with OVERALL = False.

PART_CHARS = 1000       # approximate size of one part; smaller parts mean more questions
MAX_PARTS = 60          # parts beyond this are not checked
THRESHOLD = 0.5         # a part counts as broken at this probability or above
OVERALL = True          # also rate the output against the whole system prompt

output = str(it1 or "").strip()
sp = str(it2 or "")
user_text = str(it3 or "").strip()

if sp.strip().startswith("{"):
    k = sp.find('"system_prompt"')
    if k < 0:
        raise ValueError("The JSON has no system_prompt key")
    tail = sp[sp.find('"', sp.find(":", k) + 1) + 1:]
    tail = tail.replace("\\\\", "\x00").replace('\\"', "\x01")
    sp = tail[:tail.find('"')].replace("\\n", "\n").replace("\\t", "\t").replace("\x01", '"').replace("\x00", "\\")
sp = sp.replace("\r\n", "\n").strip()

# Cut at the first blank line after PART_CHARS characters, so no paragraph is split.
parts = []
pos = 0
while pos < len(sp) and len(parts) < MAX_PARTS:
    end = sp.find("\n\n", pos + PART_CHARS)
    if end < 0:
        end = len(sp)
    parts.append(sp[pos:end].strip())
    pos = end
truncated = pos < len(sp)

# Every part shares one state and goes in the question text,
# so all parts are asked in one request.
state = {"output": output}
if user_text:
    state["user_input"] = user_text
results = []
for i, part in enumerate(parts):
    p = jev.noul(state, "Does the output clearly break any instruction in the part of the system prompt below? Answer no if the instructions do not concern the output, or if judging them needs a reference image or anything else not given here.\nPart of the system prompt:\n" + part)
    results.append([float(p), i + 1])

# The overall rating needs the whole system prompt as state, so it is a second request.
# Asking it before the sort below sends it together with the parts.
if OVERALL:
    overall_state = {"system_prompt": sp, "output": output}
    if user_text:
        overall_state["user_input"] = user_text
    level = jev.score(overall_state, "How faithfully does the output follow the system prompt as a whole?", ["ignores most instructions", "follows some instructions", "follows about half", "follows most instructions", "follows every instruction"])

lines = []
issues = []
total = 0.0
for r in reversed(sorted(results)):
    total += r[0]
    bad = r[0] >= THRESHOLD
    # Show the first line of the part as its title, skipping divider lines.
    title = parts[r[1] - 1].strip("=-_*# \n\t").splitlines()[0][:60]
    line = ("[BREAK?] " if bad else "[OK]     ") + f"p={r[0]:.2f} part {r[1]}: {title}"
    lines.append(line)
    if bad:
        issues.append(line)

score = round(100 * (1 - total / len(parts))) if parts else 0
header = f"Adherence: {score}/100 ({len(issues)} of {len(parts)} parts likely broken)"
if truncated:
    header += f"\nOnly the first {MAX_PARTS} parts were checked"
if OVERALL:
    header += f"\nOverall: {level:.2f} / 4"

ot1 = header + "\n" + "\n".join(lines)
ot2 = header + "\n" + "\n".join(issues)
part_texts = []
for i, part in enumerate(parts):
    part_texts.append(f"--- part {i + 1} ---\n{part}")
ot3 = "\n\n".join(part_texts)
ov1 = score
ov2 = len(issues)
```

The resulting `out_text_1` is a report like this:

```text
Adherence: 74/100 (2 of 19 parts likely broken)
Overall: 2.90 / 4
[BREAK?] p=0.78 part 7: Keep the events in the order the user gave them.
[BREAK?] p=0.61 part 12: Describe the camera only when the user asks for it.
[OK]     p=0.34 part 1: You are a prompt enhancer for a video model.
[OK]     p=0.22 part 3: Use the requested duration.
```

Notes:

- The notes above about `max_jev_calls`, `p`, `in_text_2`, and the TypeSafe API apply here too.
- A part is cut at the first blank line after `PART_CHARS` characters, so no paragraph is split. Headings and bullets are not interpreted, so this works with any layout, but example sections are not skipped.
- The report names each part by its first line. Read the full text of a flagged part in `out_text_3` to find the instruction in question.
- One question covers several instructions, so the result is coarser than the line-by-line script. Lower `PART_CHARS` for smaller parts and more questions.
- In testing, a system prompt of about 20,000 characters was cut into 19 parts and ran in about 2,200 script steps, well under the step limit.

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
- **Documentation**: See [CHANGELOG.md](CHANGELOG.md) for version history
- **Examples**: Check [examples/](examples/) for workflow templates

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

### Current Version: 1.3.4
- `MultiOutputScript (Jev)` runs local d1 GGUF models (Liquid AI's open-weight decision model), asking each question in the prompt format d1 was tuned on
- Added a technical report on how Jev, Clef-Flash, and a general local model answer questions whose answer cannot be known
