# How general local models answer uncertain questions: `jev.*` behavior and how to ask
[en | [ja](README.ja.md)]

Technical report (October 2026)

## Summary

`MultiOutputScript (Jev)` can make decisions with a local GGUF model instead of TypeSafe's Jev. This report compares how Jev, Clef-Flash, and a general model (Qwen3.5-9B) answer questions whose answer cannot be known, and looks at how to ask when a general model is used.

- On questions with a certain answer, the three models gave almost the same answers.
- On questions with an uncertain answer, they behaved differently. When 50/50 statements were asked "Is this statement true?" with `jev.noul`, the mean was 0.44 for Jev, 0.31 for Clef-Flash, and 0.06 for Qwen3.5-9B.
- A low value from Qwen3.5-9B means "cannot say it is true", not "unlikely to happen". It answered 0.02 for a statement whose probability is 0.92.
- Asking about both a statement and its negation, and combining the two answers, brought the 50/50 statements to 0.51 with Qwen3.5-9B as well.
- Having the model pick a probability level (`jev.score`) recovered the size of the probability to some degree. The result depended on how the levels were defined and on their order.
- Reversing the question to "Is this statement false?" did not work as a substitute for the negation.

This is a small test of 31 pairs (62 statements), and the level-based questions were tried with one quantization of Qwen3.5-9B only. It shows tendencies.

## 1. Purpose

The output of a decision model is often cut at a threshold and used to branch (for example `jev.yes(state, question, 0.5)`). When some inputs do not give enough to decide, the branch taken depends on which value the model uses to express "I cannot tell".

This report checks two things:

1. How a general local model answers uncertain questions differently from Jev.
2. How much of that difference can be closed by how the script asks.

Two properties expected of a model that answers with probabilities were used as criteria:

- **Criterion 1**: the probabilities of the two statements of a pair add up to 1.
- **Criterion 2**: a 50/50 statement gets 0.5.

## 2. Method

### 2.1 Models

| Model | Kind | How the answer is produced |
| --- | --- | --- |
| Jev | TypeSafe's decision model (API) | The API returns probabilities |
| Clef-Flash | Qwen3.5-9B further trained for decisions (`ggml-org/Clef-Flash-GGUF`, Q8_0) | The values from the decision head are turned into probabilities |
| Qwen3.5-9B | General LLM (`unsloth/Qwen3.5-9B-GGUF`, Q8_0) | The probabilities of the option letters as the next token are read |

For a general model, the options are shown with letters (for `jev.noul`, A: Yes and B: No) and the model is told to answer with one letter only. No text is generated. The probability of each letter as the next token is read, and the values are rescaled so that the letters add up to 1 (any other output is left out). This is the method proposed by SemIf (OpenJev). The values in this report are uncalibrated. Calibration is discussed in sections 3.2 and 5. Because nothing is sampled, there is no random seed or temperature setting.

The instruction is as follows. The statement, the question, and the options are passed together as JSON.

```text
Apply the supplied criterion to the supplied evidence. Choose exactly one listed option. Respond with only its uppercase letter, with no explanation or reasoning.
```

All three models were run through this node's own decision code (v1.3.3). Questions were sent one at a time.

### 2.2 Statements

There are 31 pairs of statements, 62 statements in total. Statements and questions are in English. The full list is in [`data/items.json`](data/items.json).

| Group | Code | Pairs | Content | Example |
| --- | --- | --- | --- | --- |
| Known facts | K | 6 | The first is true, the second false | Paris is the capital of France. / ... of Germany. |
| Near-certain future | N | 6 | The first is almost sure to happen | The sun will rise tomorrow. / ... will not rise tomorrow. |
| Future with a tendency | T | 6 | The first is more likely, but not certain | The S&P 500 index will be higher one year from now ... / lower ... |
| 50/50 | U | 8 | Both are about 50% | The next coin I flip will land heads. / ... tails. |
| Known probability | P | 5 | The exact probability can be calculated | The next roll of a fair six-sided die will show a 1. (1/6) / ... a number other than 1. (5/6) |

The 26 pairs of K, N, T, and U were asked to all three models. The 5 pairs of P were added later and asked to Qwen3.5-9B only.

### 2.3 Questions

| Code | Function | Question | Options |
| --- | --- | --- | --- |
| Q1 | `jev.noul` | Is this statement true? | Yes / No |
| Q2 | `jev.noul` | Is this statement more likely to be true than false? | Yes / No |
| F1 | `jev.noul` | Is this statement false? | Yes / No |
| S6 | `jev.score` | How likely is this statement to be true? | 0-10%, 10-30%, 30-50%, 50-70%, 70-90%, 90-100% |
| S11 | `jev.score` | How likely is this statement to be true? | 0%, 10%, ..., 100% |
| F6 | `jev.score` | How likely is this statement to be false? | The same six levels as S6 |

Q1 and Q2 were asked to all three models. F1, S6, S11, and F6 were asked to Qwen3.5-9B only. The level-based questions were asked twice, with the options in ascending and in descending order.

As a control, Qwen3.5-9B was also asked to write the probability as a number (20 statements). The instruction was "What is the probability that the following statement is true? Answer with a single number from 0 to 100 (percent) and nothing else.", and the text was generated by taking the most likely token at each step.

### 2.4 Measures

- **Pair sum**: the sum of the values for the two statements of a pair (criterion 1).
- **Distance from 0.5**: the mean absolute difference between the value and 0.5 over the 16 50/50 statements (criterion 2).
- **Mean error**: the mean absolute difference between the value and the true probability over the 10 known-probability statements.
- **Rank correlation**: Spearman's rank correlation between the value and the true probability over the same 10 statements.
- **Negation-combined value**: (value for the statement + 1 − value for the negation) / 2. The pair sum is 1 by construction.
- **Estimate from levels**: the value of each level (for S6 and F6 the midpoints 0.05, 0.20, 0.40, 0.60, 0.80, 0.95; for S11 the points 0, 0.1, ..., 1.0) weighted by the probability the model gave that level.

Negation-combined values were not measured separately. They are calculated from the values already measured.

## 3. Results

### 3.1 The three models compared (Q1)

Values are mean yes-probabilities, with the first statement of the pair on the left and the second on the right. The results of Qwen3.5-9B for "Future with a tendency" and "50/50", shown in bold italics, are far from criteria 1 and 2 of section 1, and are examined further from section 3.2 on.

| Group | Jev | Clef-Flash | Qwen3.5-9B |
| --- | --- | --- | --- |
| Known facts | 0.92 / 0.03 | 0.95 / 0.02 | 0.99 / 0.01 |
| Near-certain future | 0.88 / 0.07 | 0.86 / 0.11 | 0.85 / 0.13 |
| Future with a tendency | 0.58 / 0.37 | 0.62 / 0.36 | ***0.07 / 0.08*** |
| 50/50 | 0.44 / 0.44 | 0.36 / 0.26 | ***0.07 / 0.04*** |

| Measure | Jev | Clef-Flash | Qwen3.5-9B |
| --- | --- | --- | --- |
| Pair sum: known facts | 0.95 | 0.97 | 1.00 |
| Pair sum: near-certain future | 0.95 | 0.96 | 0.98 |
| Pair sum: future with a tendency | 0.95 | 0.98 | ***0.15*** |
| Pair sum: 50/50 | 0.88 | 0.62 | ***0.11*** |
| Distance from 0.5 (50/50) | 0.06 | 0.22 | ***0.44*** |

- For known facts, all three models gave a value on the correct side for all 12 statements.
- Jev returned 0.34 to 0.51 for all 16 50/50 statements.
- Qwen3.5-9B answered No to almost every uncertain statement (future with a tendency, 50/50). It does not answer No to everything about the future: it returned 0.99 for "The sun will rise tomorrow." (near-certain future).
- Clef-Flash had a pair sum of 0.98 for the future with a tendency, very different from Qwen3.5-9B before tuning (0.15). For questions like coins and dice it stayed at 0.62 (the coin flip was 0.16 / 0.10).

Clef-Flash and Qwen3.5-9B also differ in how the answer is produced. This test cannot separate whether the difference between the two comes from the tuned weights or from the way the answer is produced.

Clef-Flash chose one side clearly for the future with a tendency (0.80 / 0.06 for the S&P 500, where Jev gave 0.53 / 0.31). However, it returned 0.09 / 0.81 for "It will not rain / will rain in Tokyo on this day next year", the opposite of the actual frequency, and 0.81 / 0.71 for "The next US president will be older / younger than 50 when taking office", answering Yes to both.

### 3.2 What the No of Qwen3.5-9B represents

From here on, the results of Qwen3.5-9B for "Future with a tendency" and "50/50" are examined.

The first check was that the No of Qwen3.5-9B is **not the result of probability going to tokens other than the letters**. The share of the whole vocabulary's probability taken by A and B (`allowed_token_mass` in SemIf) was recorded for 124 questions: 62 statements × Q1 and Q2.

| | Minimum | Median | Maximum |
| --- | --- | --- | --- |
| Share taken by A and B | 0.9971 | 0.9992 | 0.9999 |

The most likely token other than A and B was "C", at 0.15% at most. Tokens that would begin a refusal or an explanation did not appear among the top 10. The model chooses B (No) clearly.

**"Cannot tell" and "almost surely will not happen" get the same value.** The mean difference between the logits of A and B (positive means toward Yes) is as follows.

| Kind of statement | Logit difference | As a probability |
| --- | --- | --- |
| True fact | +5.6 | about 1.00 |
| Near-certain to happen | +2.9 | about 0.95 |
| Future with a tendency | −3.0 | about 0.05 |
| 50/50 | −3.3 | about 0.04 |
| Near-certain not to happen | −3.3 | about 0.04 |
| False fact | −6.2 | about 0.002 |

**The values do not follow the order of the probabilities.** The Q1 answers for known-probability statements are below. The rank correlation over the 10 statements was −0.38.

| Statement | True probability | Q1 value |
| --- | --- | --- |
| Drawing an ace from a deck | 0.08 | 0.03 |
| Rolling a 1 | 0.17 | 0.02 |
| Drawing a heart | 0.25 | 0.03 |
| Rolling a 3, 4, 5, or 6 | 0.67 | 0.35 |
| Drawing a card that is not a heart | 0.75 | 0.02 |
| Rolling a number other than 1 | 0.83 | 0.01 |
| Drawing a card that is not an ace | 0.92 | 0.02 |

Qwen3.5-9B appears to answer "Is this statement true?" by the standard "can it be said to be true for certain?". The value that comes out is not the probability of the event but the confidence in the answer No. Because the value carries no information about the size of the probability, turning Q1 values into probabilities afterwards (calibration) is difficult.

### 3.3 Changing the question (Q2)

With the question changed to "Is this statement more likely to be true than false?":

- Jev and Clef-Flash showed almost the same tendency as with Q1.
- Qwen3.5-9B no longer answered No to everything. For the known-probability statements it chose the correct side (above or below 0.5) for 8 of 10.
- However, the values of Qwen3.5-9B were close to 0 or 1 and did not express the size of the probability. The 50/50 statements swung to Yes or No depending on the statement (0.02 to 0.99; distance from 0.5 was 0.36).

The answers of a general model depend strongly on the wording of the question.

### 3.4 Asking about both the statement and its negation

With Q1, Qwen3.5-9B answers Yes to "near-certain to happen" and No to "cannot tell". What it does not separate is "cannot tell" from "near-certain not to happen". The negation of the latter is "near-certain to happen", so asking about the negation as well separates them.

| Kind of statement | Answer for the statement | Answer for the negation |
| --- | --- | --- |
| Near-certain to happen | Yes | No |
| Near-certain not to happen | No | Yes |
| Cannot tell | No | No |

The statements were written as pairs, so the other statement of the pair was taken as the negation and the negation-combined value was calculated (Q1). The value in parentheses is from asking about the statement alone. Bold italics mark the items that were far from the criteria in section 3.1.

| Group | Jev | Clef-Flash | Qwen3.5-9B |
| --- | --- | --- | --- |
| Known facts | 0.95 (0.92) | 0.96 (0.95) | 0.99 (0.99) |
| Near-certain future | 0.90 (0.88) | 0.88 (0.86) | 0.86 (0.85) |
| Future with a tendency | 0.60 (0.58) | 0.63 (0.62) | ***0.49 (0.07)*** |
| 50/50 | 0.50 (0.44) | 0.55 (0.36) | ***0.51 (0.07)*** |

| Distance from 0.5 (50/50) | Jev | Clef-Flash | Qwen3.5-9B |
| --- | --- | --- | --- |
| Statement alone | 0.06 | 0.22 | ***0.44*** |
| Combined with the negation | 0.006 | 0.053 | ***0.015*** |

For Qwen3.5-9B, cutting the two answers at 0.5 and sorting each pair into "true / false / cannot tell" gave the expected result for 29 of 31 pairs.

- Known facts and near-certain future (12 pairs): 10 pairs were "true".
- Future with a tendency, 50/50, and known probability (19 pairs): all 19 pairs were "cannot tell".

The two pairs that missed were "It will snow / will not snow in Sapporo next January" (No to both) and "A total solar eclipse will / will not occur within the next five years" (Yes to both). A Yes to both is a sign that the answer cannot be trusted.

This method does not recover the size of the probability. A statement with probability 0.08 and one with 0.92 both get a negation-combined value near 0.5 (for the known-probability statements the mean error was 0.244 and the rank correlation −0.12).

### 3.5 Having the model pick a probability level

The results below are for Qwen3.5-9B only.

**Control: written as a number, the answer is almost exact.** The mean error over the 10 known-probability statements was 0.003 (for example "9" for a true probability of 7.7%, "16.67" for 16.7%, and "92" for 92.3%). For the coin flip it answered "50". The model has the knowledge of the probabilities. That the size of the probability does not show with Q1 comes from how the question is asked.

| Statement | True probability | Number written |
| --- | --- | --- |
| Drawing an ace from a deck | 7.7% | 9 |
| Rolling a 1 | 16.7% | 16.67 |
| Drawing a heart | 25% | 25 |
| Two heads in two coin flips | 25% | 25 |
| Rolling a 1 or a 2 | 33.3% | 33 |
| Rolling a 3, 4, 5, or 6 | 66.7% | 66 |
| Drawing a card that is not a heart | 75% | 75 |
| Not two heads in two coin flips | 75% | 75 |
| Rolling a number other than 1 | 83.3% | 83 |
| Drawing a card that is not an ace | 92.3% | 92 |
| 50/50 statements (4: coin, die, time of birth, grains of sand) | 50% | 50 for all |
| The sun will rise / will not rise tomorrow | — | 100 / 0 |
| Paris is the capital of France / of Germany | — | 100 / 0 |
| The S&P 500 will be higher / lower in one year | — | 65 / 50 |

**Asked by level, the size of the probability shows to some degree.** The results for the 10 known-probability statements are as follows.

| How it was asked | Rank correlation | Mean error |
| --- | --- | --- |
| Q1 (Yes / No) | −0.38 | — |
| S6, ascending | +0.88 | 0.095 |
| S6, descending | +0.76 | 0.208 |
| S11, ascending | +0.77 | 0.202 |
| S11, descending | +0.80 | 0.203 |
| Written as a number | +1.00 | 0.003 |

The two level-based questions are shown again here. Both use the question "How likely is this statement to be true?", and only the options differ.

- **S6 (six ranges)**: 0-10%, 10-30%, 30-50%, 50-70%, 70-90%, 90-100%. The estimate uses the midpoint of each range (0.05, 0.20, 0.40, 0.60, 0.80, 0.95).
- **S11 (eleven points)**: 0%, 10%, 20%, ..., 100%. The estimate uses the value of each point (0, 0.1, ..., 1.0).

**Six ranges (S6) and eleven points (S11) are good at different things.**

| Measure | S6 | S11 |
| --- | --- | --- |
| Distance from 0.5 (50/50; ascending / descending) | 0.118 / 0.140 | 0.027 / 0.029 |
| Difference in the estimate between the two orders (mean of 62 statements) | 0.087 | 0.042 |
| Pair sum: known facts (mean of the two orders) | 1.07 | 1.03 |
| Pair sum: near-certain future (mean of the two orders) | 1.14 | 1.04 |

- With S6, the 50/50 statements came out at about 0.60. 50% lies on the border between "30-50%" and "50-70%", and the model chose "50-70%" for 14 of 16 statements.
- S6 depended strongly on the order. "Drawing a card that is not a heart" (true probability 0.75) was 0.75 in ascending order and 0.24 in descending order.
- With S11, 14 of the 16 50/50 statements came out at 0.50, and the pair sums are close to 1. Asking about the statement alone almost meets criteria 1 and 2.
- With S11, the size of the probability hardly shows, because the model chooses "50%" for most statements that are not certain. It chose "50%" both for "Drawing a heart" (0.25) and for "Drawing a card that is not a heart" (0.75).

When there is a "50%" option, 50/50 statements are answered correctly, but uncertain statements gather there. S11 works much like sorting into "true / false / cannot tell".

**Six ranges asked about both the statement and its negation cover both.**

| How it was asked (S6) | Distance from 0.5 | Mean error | Rank correlation |
| --- | --- | --- | --- |
| Ascending, statement alone | 0.118 | 0.095 | +0.88 |
| Ascending, combined with the negation | 0.027 | 0.069 | +0.90 |
| Descending, combined with the negation | 0.034 | 0.148 | +0.92 |

The shift of the 50/50 statements goes in the same direction for the statement and for the negation, so it cancels when the two are combined. The levels are better listed in ascending order.

| Statement | True probability | Statement alone | Combined with the negation |
| --- | --- | --- | --- |
| Drawing an ace from a deck | 0.08 | 0.06 | 0.13 |
| Rolling a 1 | 0.17 | 0.05 | 0.19 |
| Drawing a heart | 0.25 | 0.32 | 0.29 |
| Two heads in two coin flips | 0.25 | 0.06 | 0.12 |
| Rolling a 1 or a 2 | 0.33 | 0.53 | 0.44 |

### 3.6 "Is this statement false?" is not a substitute for the negation

Instead of writing a negation, the statement was kept as it is and the question was reversed (F1, F6). The combined value was calculated as (Q1 value + 1 − F1 value) / 2.

| Group | Combined with the negated statement | Combined with F1 |
| --- | --- | --- |
| Known facts | 0.99 | 0.99 |
| Near-certain future | 0.86 | 0.87 |
| Future with a tendency | 0.49 | 0.36 |
| 50/50 | 0.51 | 0.42 |

| Measure | Combined with the negated statement | Combined with the "false" question |
| --- | --- | --- |
| Distance from 0.5 (Yes / No) | 0.015 | 0.109 |
| Distance from 0.5 (six ranges, ascending) | 0.027 | 0.072 |
| Mean error (six ranges, ascending) | 0.069 | 0.146 |

There is no difference for certain statements. What breaks is the uncertain ones. Asked "Is this statement true?" about an uncertain statement, Qwen3.5-9B almost always answers No, but asked "Is this statement false?" it sometimes answered Yes (for "The next coin I flip will land tails.", Q1 was 0.03 and F1 was 0.60). It does not say an uncertain statement is "true", but it says "false" more easily.

The negated statement likely works because it is asked with the same question, so the bias of the question applies to both in the same way and cancels.

### 3.7 Summary of the ways of asking (Qwen3.5-9B)

| How it was asked | 50/50 at 0.5 | Size of the probability | Writing a negation | Questions |
| --- | --- | --- | --- | --- |
| Yes / No, statement alone | No | Does not show | Not needed | 1 |
| Yes / No, combined with the negation | Yes | Does not show | Needed | 2 |
| Eleven points, statement alone | Yes | Hardly shows | Not needed | 1 |
| Six ranges, statement alone | Shifted (about 0.60) | Shows to some degree | Not needed | 1 |
| Six ranges, combined with the negation | Yes | Shows to some degree | Needed | 2 |
| Combined with the "false" question | Shifted | Does not show | Not needed | 2 |
| Written as a number | Yes | Shows | Not needed | Needs text generation |

## 4. Guidelines for using a general model

From the above, the following can be said for scripts that use `jev.*` with a general local model.

1. **Do not read a low `jev.noul` or `jev.yes` value as "unlikely".** It includes "cannot say it is true". Inputs that do not give enough to decide almost always take the No branch.
2. **If "true / false / cannot tell" is enough, ask once with eleven points.**
3. **If you ask Yes / No, ask about both the statement and its negation.** Treat No to both as "cannot tell", and Yes to both as an answer that cannot be trusted.
4. **If you also want the size of the probability, list six ranges in ascending order and ask about both the statement and its negation.**
5. **Write the negation as a statement.** Changing the question to "Is this statement false?" is not a substitute. For this reason, there is currently no way for the node to create the negated question automatically.
6. **Put what you want to know directly into the question.** "Is it true" and "is it the more likely side" give very different answers.
7. **Review thresholds when you change the model.** With the same script, the branch taken for uncertain inputs differs between Jev, Clef-Flash, and a general model.

Asking about both the statement and its negation. Numeric outputs (`ov1` and so on) are integers, so the negation-combined value is multiplied by 100 and output as 0 to 100.

```python
# it1: the statement, it2: its negation
# ov1: negation-combined value (0-100), ot1: classification
a = jev.noul(it1, "Is this statement true?")
b = jev.noul(it2, "Is this statement true?")
ov1 = (a + 1 - b) / 2 * 100

if a < 0.5 and b < 0.5:
    ot1 = "unsure"
elif a >= 0.5 and b >= 0.5:
    ot1 = "contradiction"
elif a >= 0.5:
    ot1 = "true"
else:
    ot1 = "false"
```

Asking with eleven points. `jev.score` returns the expected index of the chosen level (0 to 10), so multiplying by 10 gives a value from 0 to 100.

```python
levels = ["0%", "10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]
ov1 = jev.score(it1, "How likely is this statement to be true?", levels) * 10
```

With six ranges, the midpoints are not evenly spaced, so multiplying the `jev.score` value by 20 does not give the same value as 100 times the estimate in section 3.5. Keep this in mind when using it as an approximation.

## 5. Limitations

- This is a small test of 31 pairs (62 statements). There are only 5 known-probability pairs (10 statements), and the comparison of the ways of asking rests on these few statements.
- It does not rank the models. Questions about the future have no correct answer, and the accuracy of the predictions was not measured.
- Combining with the negation was thought of while looking at this data, and its effect was checked on the same data. It has not been checked on other statements.
- Some pairs are not strict negations (such as "higher" and "lower"). The result can change with how the negation is written.
- The level-based questions (S6, S11), the effect of combining with the negation for levels, and the "false" questions (F1, F6) were tried with Qwen3.5-9B only. They were not asked to Jev or Clef-Flash.
- Only two ways of defining the levels were tried.
- The only general model is Qwen3.5-9B at Q8_0. Another model, another quantization, or another decision method may give different results.
- The values of the general model are uncalibrated. SemIf (OpenJev) recommends calibrating for each use, but calibration was not tried here. As section 3.2 shows, the Yes / No values carry no information about the size of the probability, and no statements suitable for calibration have been prepared.
- Every question was measured once. The values of a local model do not change under the same conditions, because nothing is sampled. Jev's values vary a little for the same question: when the 16 50/50 statements were asked three times with Q1, the largest range was 0.04.
- Statements and questions are in English. Other languages were not tried.

## 6. Data

The statements and the results are in [`data/`](data/). A statement ID is the pair code followed by `a` (first statement) or `b` (second statement), for example `U1a`.

| File | Content |
| --- | --- |
| `items.json` | Statements (`pairs`), question texts (`questions`), group descriptions (`groups`), and the true probabilities of the known-probability statements (`probabilities`) |
| `results_jev.json` | Jev. `p_yes` for Q1 and Q2. Q1 of the 50/50 statements has three runs (`run` 1 to 3) |
| `results_clef_flash.json` | Clef-Flash. `p_yes` for Q1 and Q2 |
| `results_qwen35.json` | Qwen3.5-9B. `p_yes` for Q1 and Q2 (26 pairs) |
| `results_qwen35_mass.json` | Qwen3.5-9B. For Q1 and Q2 (31 pairs): `p_yes`, the logits of A and B, `allowed_token_mass`, and the 10 most likely tokens |
| `results_qwen35_score.json` | Qwen3.5-9B. The probability of each level for S6 (`score`) and the answers of the written-number control (`text`) |
| `results_qwen35_score11.json` | Qwen3.5-9B. The probability of each level for S11 |
| `results_qwen35_false.json` | Qwen3.5-9B. `p_yes` for F1 (`noul`) and the probability of each level for F6 (`score`) |

The level probabilities (`p`) are stored from the lowest level to the highest, whichever order the options were shown in. `order` is the order shown.

## 7. Measurement conditions

- Dates: October 5, 2026 (comparison of the three models), October 6 to 8, 2026 (additional measurements with Qwen3.5-9B)
- Node: ComfyUI-ScriptFlow v1.3.3
- Jev: TypeSafe API (typesafe-sdk 0.7.1). The model name returned by the API was `jev-1.13.0` when checked on October 8, 2026. The model name at the time of measurement (October 5) was not recorded.
- Local models: llama-cpp-python 0.4.2 (SYCL build), Windows 11
