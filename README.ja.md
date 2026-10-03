# ComfyUI-ScriptFlow（日本語版）
[[en](README.md) | ja]

---

**Version:** 1.3.2
**License:** GPL-3.0

System One の判断モデルを使える、安全な Python 風スクリプトノードです。
TypeSafe AI の Jev API（フォールバックとしてローカルの GGUF LLM）に Yes/No・選択・スコアの質問をして、その答えを `if` 文の中でそのまま使えます。

![MultiOutputScript (Jev) demo](images/MultiOutputScript_Jev.gif)

デモ：`MultiOutputScript (Jev)` が TypeSafe API を使ってテキストプロンプトに合うアスペクト比を選び、各比率の確率を一覧にして、幅と高さを画像ノードに渡しています。

デモを簡略化した例です。テキストプロンプトを `in_text_1` につなぐと、その答えで幅と高さが決まります。

```python
if jev.yes(it1, "Does a portrait orientation suit this prompt?"):
    ov1, ov2 = 832, 1280
else:
    ov1, ov2 = 1280, 832
```

System One モデルはテキストを生成せず、1 回の高速な処理で確率として答えを返します。そのため、答えをそのままワークフローの判断に使えます。

複数の入出力により、計算・論理判断・テキスト編集・条件分岐・解像度の選択・ファイル名の生成などを 1 つのノードで扱えます。これまで複数の基本ノードを組み合わせていた処理をまとめられます。スクリプトは制限付きのインタープリタで実行され、ファイルや OS にはアクセスしません。

## インストール

1. `ComfyUI/custom_nodes/` ディレクトリに移動します。
2. このリポジトリをクローンします。
   ```bash
   git clone https://github.com/kantan-kanto/ComfyUI-ScriptFlow
   ```
3. ComfyUI を再起動します。

`MultiOutputScript` と `centi` ノードに追加のパッケージは不要です。`MultiOutputScript (Jev)` は、使うバックエンドに応じて以下のセットアップが必要です。

### `MultiOutputScript (Jev)` のセットアップ

#### TypeSafe APIを使う場合

1. ComfyUI を実行している Python 環境に SDK をインストールします。
   ```bash
   pip install typesafe-sdk
   ```
2. このカスタムノードの実際のインストール先ディレクトリに `api_key.txt` を作成し、TypeSafe の API キーを記入します（1 行、引用符なし）。
   ```
   ComfyUI/custom_nodes/<your-installation-folder>/api_key.txt
   ```
   キーは実行のたびにこのファイルから読み込まれます。`api_key.txt` は `.gitignore` に登録されています。コミットしないでください。

#### ローカルモデル（フォールバック）を使う場合

- ComfyUI を実行している Python 環境に [llama-cpp-python](https://github.com/JamePeng/llama-cpp-python) をインストールします。JamePeng 版と、本家の [abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python) 0.3.35 で動作を確認しています。
- 指示追従型（instruction-tuned）の GGUF モデルを `ComfyUI/models/LLM`（または `models/text_encoders`）に置きます。GGUF にはチャットテンプレート（`tokenizer.chat_template` メタデータ）が含まれている必要があります。ほとんどの指示追従型 GGUF には含まれています。Qwen3.5-9B Q8_0 と Gemma-4-E4B Q8 で動作を確認しています。

## 主な機能
- 複数の入力：数値とテキストの入力を自由に組み合わせられます。
- 計算と論理：四則演算、比較、簡単な条件分岐に対応します。
- 複数の出力：結果を別々の出力ポートから下流のノードに渡せます。
- AI による判断：`MultiOutputScript (Jev)` で `jev.yes` / `jev.choice` / `jev.score` を確率付きで使えます。TypeSafe AI の Jev API、またはフォールバックとしてローカルの GGUF モデルを使います。
- 安全な実行：スクリプトは構文を制限した AST インタープリタで実行され、ファイルや OS にはアクセスしません。モデルや TypeSafe API にアクセスするのは、Jev ノードの `jev` 関数だけです。

## 使用例
- Wan2.2 の I2V ワークフローで、入力画像が縦長か横長かに応じて推奨解像度
  （512×384 または 384×512）を自動で選ぶ。
- ファイル名をまとめて生成する（例：ローカル LLM のプロンプト履歴、出力ログ）。
- 条件分岐でワークフローの動作を制御する（例：入力に応じてパラメータや経路を切り替える）。
- LLM の出力を解析・変換し、下流のノード向けの構造化された値にする。
- シード、しきい値、倍率などの数値パラメータを、独自の計算で動的に生成する。
- 生成前に、テキストプロンプトに合うアスペクト比とサイズを、各比率の確率付きで選ぶ（Jev ノードの初期スクリプト）。
- テキストの意味でワークフローを振り分ける（例：プロンプトが夜の情景かを判定する、主題を分類する）。

## ノード

### `MultiOutputScript`
**Category:** `utils`

入力（任意、接続可能）：
- `in_text_1`（任意の入力を受け付け、実行時に `str` か検証）
- `in_text_2`（任意の入力を受け付け、実行時に `str` か検証）
- `in_text_3`（任意の入力を受け付け、実行時に `str` か検証）
- `in_value_1`（任意の入力を受け付け、実行時に `int` または `float` か検証）
- `in_value_2`（任意の入力を受け付け、実行時に `int` または `float` か検証）
- `in_value_3`（任意の入力を受け付け、実行時に `int` または `float` か検証）
- `code`（複数行の文字列）

出力：
- `out_text_1`（STRING）
- `out_text_2`（STRING）
- `out_text_3`（STRING）
- `out_value_1`（INT）
- `out_value_2`（INT）
- `out_value_3`（INT）

数値出力についての注意：
- 出力は `INT` です。
- 整数入力から `FLOAT` の値が必要な場合は、`centi` ノードを使ってください。
- 値が小数の場合、出力時に小数部分は切り捨てられます。
- 四捨五入や切り上げをしたい場合は、スクリプト内で処理してください（例：`round(...)`、`math.ceil(...)`）。

### スクリプト変数
`code` の中では次の変数を使います。
- 入力：`it1`、`it2`、`it3`、`iv1`、`iv2`、`iv3`
- 出力：`ot1`、`ot2`、`ot3`、`ov1`、`ov2`、`ov3`

代入しなかった出力は `None` になります。

### スクリプト例
```python
# Example: keep landscape at 512x384, portrait at 384x512
# Connect GetImageSize width/height to in_value_1/in_value_2
# iv1: image width, iv2: image height
w, h = iv1, iv2
ov1, ov2 = (512, 384) if w >= h else (384, 512)
```

### `MultiOutputScript (Jev)`
**Category:** `utils`

`MultiOutputScript` と同じ入力・出力・スクリプトの規則に加えて、`jev` 名前空間を使えます。TypeSafe AI の判断モデルである [Jev](https://typesafe.ai) に、テキストについての型付きの質問をし、その答えでスクリプトを分岐できます。

- **TypeSafe API**（基本）：質問をインターネット経由で Jev に送ります。
- **ローカル GGUF モデル**（フォールバック）：Jev API を使えない場合や、テキストを手元のマシンから出したくない場合に使います。汎用の指示追従型モデルで Jev 風の判断を近似するもので、[SemIf (OpenJev)](https://github.com/TheoLeeCJ/SemIf-OpenJev) の方式に従い、文字を割り当てた選択肢の次トークン確率を 1 回の順伝播で読み取ります。テキストは生成せず、ネットワークにも何も送りません。答えや確率は Jev とは異なります。

スクリプトはどちらでも同じです。各バックエンドのセットアップは[インストール](#インストール)を参照してください。

追加の入力：
- `model`：`TypeSafe API`、またはローカルの GGUF モデル（`mmproj-*` ファイルは表示されません）。
- `max_jev_calls`（INT、初期値 8）：1 回の実行での Jev リクエストの上限です。同じ `state` についての質問は 1 回のリクエストにまとめて送るため（[質問のまとめ送り](#質問のまとめ送り)を参照）、質問数ではなくリクエスト数を制限します。上限を超えるリクエストは送る前にエラーで止まります。同じ実行の中で同じ質問は 1 回しか問い合わせません。

関数（`state` は文字列・辞書・リスト。テキストのみ）：
- `jev.yes(state, question[, threshold])` → `bool`（Yes の確率が `threshold` 以上か。初期値 `0.5`）
- `jev.noul(state, question)` → Yes の確率（`0.0`〜`1.0`）。しきい値と比較して使ってください。そのまま条件に使うとエラーになります。
- `jev.choice(state, question, options)` → 最も確からしい選択肢（`str`）。`options` はラベルのリスト、またはラベルから説明への辞書です（ローカルモデルでは 2〜16 個）。
- `jev.probabilities(state, question, options)` → 各選択肢とその確率の `dict`（合計 `1.0`）。`options` は `jev.choice` と同じです。同じ引数で両方を呼んでも、問い合わせは 1 回です。
- `jev.score(state, question, levels)` → 順序付きの段階の説明に対する期待値（`float`、`0`〜`len(levels) - 1`）（ローカルモデルでは 2〜16 段階）

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

ノードの初期スクリプトは、`it1` のプロンプトに合う 8 種類のアスペクト比から 1 つを選び、`in_value_1` のメガピクセル数（未接続時は `1.0`。幅と高さは 64 の倍数に丸め）に合わせてサイズを決めます。幅と高さを `out_value_1` / `out_value_2` に、各比率の確率を `out_text_1` に出力します。

各関数は 1 つの質問をします。[TypeSafe Python SDK](https://pypi.org/project/typesafe-sdk/) で書いた場合のコードとの対応を示します。

| ScriptFlow | TypeSafe SDK |
| --- | --- |
| `jev.noul(state, q)` | `client.system_one(state=state, questions={"q": Noul(instructions=q)}).answers["q"].noul` |
| `jev.yes(state, q, t)` | `... .answers["q"].noul >= t` |
| `jev.choice(state, q, options)` | `client.system_one(state=state, questions={"q": Choice(instructions=q, criteria=options)}).answers["q"].choice` |
| `jev.probabilities(state, q, options)` | `... .answers["q"].probabilities`（`jev.choice` と同じリクエスト） |
| `jev.score(state, q, levels)` | `client.system_one(state=state, questions={"q": Score(instructions=q, criteria=levels)}).answers["q"].score` |

リストで渡した `options` は `criteria={label: None, ...}` として送られます。`confidence`、Score の段階ごとの確率、Noul の `criteria` は利用できません。

#### 質問のまとめ送り

質問は可能な範囲でまとめて送られます。

1. スクリプトの実行中、`jev` の質問はその場では送らず、順に溜めておきます。
2. 答えを変数やリストに入れる、自分で定義した関数に渡す、`float()` を通す、といった使い方なら実行を続けます。`if` の条件、比較、計算、f 文字列、`sorted`、`join`、出力などで答えの値を初めて使ったところで、実行を止めます。
3. 溜めた質問を `state` ごとに 1 回のリクエストで送り、スクリプトを最初から実行し直します。答えが分かった質問はその値を返し、新しい質問は同じように溜めます。

`state` が違うリクエストは、TypeSafe API では同時に送り、ローカルモデルでは順に処理します。質問を 1 つずつ問い合わせる場合と同じ質問をし、同じ結果を出力します。1 回の実行の中では、実行し直すたびに `random` の状態と `datetime.datetime.now()` の時刻が同じところから始まるので、実行し直しても質問は変わりません。

次の例では、`a` は `if` まで使われないので、`q1` と `q2` は 1 回のリクエストで送られます。`q3` は `a` が分かってから 2 回目のリクエストで送られます。

```python
a = jev.noul(it1, "q1")
b = jev.noul(it1, "q2")
if a > 0.5:
    c = jev.noul(it1, "q3")
```

多くの質問を 1 回のリクエストで送るには、`state` を同じにして、質問ごとに違う内容は質問文に入れてください。

TypeSafe API では、1 回のリクエストが [TypeSafe Python SDK](https://pypi.org/project/typesafe-sdk/) の `system_one` 呼び出し 1 回にあたります。上の例の 1 回目のリクエストは次のとおりです。

```python
client.system_one(state=it1, questions={"q0": Noul(instructions="q1"), "q1": Noul(instructions="q2")})
```

注意：
- TypeSafe API は `state` と質問をインターネット経由で送信します。外部に出せないテキストには使わないでください。
- ローカルモデルの質問は 1 回の順伝播で処理されます（GPU 上の 4B〜9B モデルで約 1〜1.5 秒）。モデルは実行ごとに最初の質問で読み込まれ（数秒）、実行が終わるとアンロードされて、ワークフローの残りのために VRAM を解放します。
- ローカルモデルの確率は較正されておらず、モデルによって変わります。しきい値は実際の入力で試して決めてください。
- 実行ごとにコンソールへ `[ComfyUI-ScriptFlow] Jev requests: N, states: S, questions: Q, responses: M` を出力します。送ったリクエスト数、異なる `state` の数、質問数、返信があったリクエスト数です。返信数がリクエスト数より少なければ、途中のリクエストが失敗しています。同じ実行のキャッシュから答えた質問は数えません。
- `typesafe-sdk` がインストールされていると、`httpx2`（SDK が使う HTTP クライアント）と `typesafe_sdk` のロガーを WARNING に設定するため、リクエストごとの INFO ログは表示されません。
- `MultiOutputScript` はモデルを読み込まず、ネットワークにもアクセスしません。`jev` は使えません。
- このプロジェクトは独立したもので、TypeSafe AI とは関係ありません。

### `centi`
**Category:** `utils`

入力（任意、接続可能）：
- `int_1`（INT）
- `int_2`（INT）
- `int_3`（INT）

出力：
- `float_1`（FLOAT）= `int_1 / 100`
- `float_2`（FLOAT）= `int_2 / 100`
- `float_3`（FLOAT）= `int_3 / 100`

注意：
- `int_n` が接続されていない場合、対応する `float_n` の出力は `None` です。
- 意図的に最小限の、接続のみのノードにしています。

---

## 実行環境
スクリプトは Python の AST で解析され、ScriptFlow の安全なインタープリタで評価されます。代入、計算、分岐、ループ、ユーザー定義のヘルパー関数、辞書、リスト、文字列、一部のメソッドなど、ワークフローでよく使う処理に対応しています。

### 使える関数
- `len`、`min`、`max`、`sum`、`abs`、`round`
- `int`、`float`、`str`、`bool`
- `sorted`、`reversed`
- `enumerate`、`range`、`zip`
- `any`、`all`、`pow`、`divmod`
- `list`、`dict`、`tuple`
- `jev.yes`、`jev.noul`、`jev.choice`、`jev.probabilities`、`jev.score`（`MultiOutputScript (Jev)` のみ。[該当の節](#multioutputscript-jev)を参照）

### 使える名前空間
- `random`：`random`、`randint`、`uniform`、`choice`
- `datetime`：`datetime.now`、`date.today`、`year`・`month`・`day`・`hour`・`minute`・`second` などの日時の項目、`isoformat` と `strftime`（`strftime` は v1.2.0 以降）
- `math`：`ceil`、`floor`、`sqrt`、`sin`、`cos`、`tan`、`asin`、`acos`、`atan`、`atan2`、`log`、`log10`、`exp`、`pow`、`fabs`、`isfinite`、`pi`、`e`、`tau`

### 使えるメソッド
- `str`：`replace`、`find`、`strip`、`split`、`splitlines`、`startswith`、`endswith`、`join`、`lower`、`upper`
- `list`：`append`

### 使えないもの
- `import` 文
- ファイルへのアクセス（`open` など）
- OS の操作（`os`、`sys`）
- Python の動的な実行
- セーフモードで禁止している構文：`Import`、`ImportFrom`、`Global`、`Nonlocal`、`ClassDef`、`Try`、`With`、`AsyncWith`、`Lambda`、`Delete`、`Yield`、`Await`
- セーフモードで禁止している呼び出し：動的な実行、ファイルや入力へのアクセス、実行時の名前空間の参照、属性の動的な変更

### 実行時の注意
- `random` や `datetime` を使うと、出力は毎回変わる可能性があります。
- v1.3.2 以降では、`datetime.datetime.now()` と `datetime.date.today()` は実行を開始した時刻を返すため、1 つのスクリプトの中で何度呼んでも同じ値になります。
- v1.2.0 以降では、`datetime.strftime(...)` でタイムスタンプを簡潔に整形できます。
  ```python
  now = datetime.datetime.now()
  ot1 = now.strftime("%Y%m%d%H%M%S")
  ```
- v1.2.0 より前のバージョンでは、同じタイムスタンプを手作業で整形します。
  ```python
  now = datetime.datetime.now()
  ot1 = f'{now.year:04d}{now.month:02d}{now.day:02d}{now.hour:02d}{now.minute:02d}{now.second:02d}'
  ```
- 型が合わない場合はエラーになり、実行が止まります。
- セーフモードでは評価の前に AST を検証し、ステップ数やループ回数の上限を超えたスクリプトを止めます。
- 信頼できるスクリプトやワークフローだけを使ってください。出所の分からないコードは実行しないでください。

## 例

### ワークフローの例

```
examples/
 ├─ example_workflow.json
```

## 応用レシピ

### `LLM Dialogue Cycle` の会話ログを `dialogue_segments_json` に変換する

<details>
<summary>ComfyUI-LLM-Session の会話ログ変換レシピを表示</summary>

`ComfyUI-LLM-Session` は、`LLM Dialogue Cycle` の結果全体を `transcript_text` として出力します。
そのテキストを `MultiOutputScript.in_text_1` につなぎ、下のスクリプトを `code` 欄に貼り付けると、
後段の会話用 TTS ノード向けに、話者タグ付きの JSON テキストを生成できます。

推奨するワークフロー：

```text
LLM Dialogue Cycle
  -> transcript_text
  -> MultiOutputScript.in_text_1
  -> MultiOutputScript.out_text_1
  -> dialogue_segments_json input of a TTS node
```

次のコードを `MultiOutputScript.code` に貼り付けます。

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

出力される `out_text_1` は、次のような JSON 文字列です。

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

注意：

- TTS がキャラクターのセリフだけを読むよう、`USER -> A` / `USER → A` は意図的に除外しています。
- モデルの出力が複数行にわたる場合は、直前の `A` または `B` の発話に含めます。
- `utterances[].text` に出力するのは `「...」` の中のテキストだけです。かぎかっこの外の地の文や心の声は除外します。
- 1 つの発話に複数のかぎかっこがある場合は、改行でつなぎます。
- `「...」` を含まない発話は、TTS 用のスクリプトから除外します。
- このレシピでは、`out_text_2`、`out_text_3`、数値出力は使いません。

</details>

## ライセンス

このプロジェクトは **GNU General Public License v3.0** の下でライセンスされています。

**Copyright (C) 2026 kantan-kanto**  
GitHub: https://github.com/kantan-kanto

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see https://www.gnu.org/licenses/.

## サポート

- **Issues**：不具合の報告や機能の要望は GitHub Issues へお願いします
- **Documentation**：バージョン履歴は [CHANGELOG.md](CHANGELOG.md) を参照してください
- **Examples**：ワークフローのテンプレートは [examples/](examples/) を参照してください

---

## 変更履歴

詳しいバージョン履歴は [CHANGELOG.md](CHANGELOG.md) を参照してください。

### 現在のバージョン：1.3.2
- `MultiOutputScript (Jev)` がスクリプトを変えずに質問をまとめて送るように：同じ `state` の質問は 1 回のリクエストで送り、`state` が違うリクエストは同時に送る
- `max_jev_calls` が質問数ではなくリクエスト数を制限するように
- 実行ごとに Jev のリクエスト数、`state` 数、質問数、返信数をコンソールに出力
- TypeSafe SDK と HTTP クライアントのリクエストごとの INFO ログを非表示に
- `datetime.datetime.now()` と `datetime.date.today()` が実行を開始した時刻を返すように
