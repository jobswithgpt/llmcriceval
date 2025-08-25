# Measuring hallucinations in stats rich domain With Cricket (T20)

## Abstract

We benchmark models on single-match cricket facts generated directly from CricSheet T20 YAML scorecards. Each item is either numeric (integer) or multiple-choice (options baked from the source). Models must emit strict JSON: `{"number": int}`, `{"choice": "<option>"}`, or `{"no_answer": true}`.On 100 items per model, GPT-5 achieves the lowest hallucination rate when it answers; a search enabled model (gpt-4o-search-preview) attains both high coverage and high accuracy. This supports the thesis that in dense stat domains (like cricket) models cannot realistically memorize the long tail; retrieval is required for high accuracy.

**Attribution:** Data derived from [CricSheet](https://cricsheet.org).

---

## Methods (brief)

* **Source of truth:** Each QA item is derived from exactly one CricSheet YAML; we store the file path with the item. No cross-match aggregation.
* **Question types (10):**

  1. toss\_winner (choice: 2 teams)
  2. toss\_decision (choice: bat/field)
  3. match\_winner (choice: 2 teams)
  4. victory\_margin\_runs (number)
  5. victory\_margin\_wkts (number)
  6. team\_total (number, per team)
  7. top\_scorer\_name (choice: all players in match; ties allowed via `gold_set`)
  8. top\_scorer\_runs (number for a fixed top batter)
  9. top\_wicket\_taker\_name (choice: all players; ties allowed via `gold_set`)
  10. total\_match\_runs (number)
* **I/O contract:** Single prompt per item. Model returns:

  * `{"choice":"<one of options>"}` for names/teams,
  * `{"number": <int>}` for numeric,
  * `{"no_answer": true}` if unsure.
* **Scoring:**

  * Answered = valid JSON and valid field (choice in options or integer).
  * Correct = choice in `gold_set` or number equals `gold`.
  * Hallucination = answered but incorrect.
  * Errors/invalid JSON/invalid options = unanswered.

---

## Results (N=100 per model)

| Model                 | Answer rate | Accuracy (overall) | Accuracy (when answered) | Hallucination rate (when answered) | Wrong / 100 prompts |
| --------------------- | ----------: | -----------------: | -----------------------: | ---------------------------------: | ------------------: |
| gpt-4o-search-preview |        0.96 |               0.88 |                   0.9082 |                             0.0918 |                9.00 |
| gpt-5                 |        0.35 |               0.27 |                   0.7714 |                             0.2286 |                8.00 |
| gpt-4o-mini           |        0.37 |               0.14 |                   0.3784 |                             0.6216 |               23.00 |
| gpt-5-mini            |        0.05 |               0.02 |                   0.4000 |                             0.6000 |                3.00 |

Notes:

* Wrong per 100 prompts = `answer_rate * hallucination_rate_when_answered * 100`.
* gpt-5-mini’s low overall wrong count is driven by high abstention (very low coverage).

---

## Discussion and Thesis

* **Dense stats are not memorized.** With many “nearby” entities and numbers, parametric memory is insufficient. Hallucinations cluster around plausible near misses (e.g., wrong victory margin, teammate names).
* **Retrieval wins.** gpt-4o-search-preview (with search) reaches both high coverage and high faithfulness, confirming that some form of RAG or built-in search is the practical path to high accuracy.
* **Operational guidance.**
  * When data that you need to search for doesn't fit context:
     * Critical domains: prefer a conservative model (e.g., gpt-5-mini or similar behavior) plus retrieval; abstain when evidence is missing.
     * General Q\&A: a stronger model (e.g., GPT-5) plus retrieval balances coverage and reliability.
* **Abstention as a knob.** Lower hallucinations per 100 prompts can be achieved either by higher precision or by answering less; choose based on risk tolerance.

---

## Limitations

* Domain is cricket only; replicate on other dense stat domains (baseball, finance, claim databases).
* Sample size per model is 100; increase N for tighter intervals and per-type CIs.
* Wrong answers in search retrieval method aren't necessarily wrong. It is just that cricsheet data isn't agreeing with other sources of data that search used.

---

## Appendix A: Prompt Contract (single prompt, model decides type)

```
System: Output valid JSON only. If unsure, return {"no_answer": true}.
User: <item.prompt>
If options are shown, choose from them.

Return ONLY one of:
{"choice":"<one of options>"}
{"number": <integer>}
{"no_answer": true}
```
## Commands

```
python scripts/sample.py --in t20_qa_all.jsonl --n 100 
python scripts/eval.py --qa t20_qa_sample.jsonl --model gpt-4o-search-preview  --out_dir gpt-4o-search-preview > gpt-4o-search-preview.txt
```

**Attribution:** Thanks to CricSheet for high-quality structured scorecards: [https://cricsheet.org](https://cricsheet.org)

Also available at [https://kaamvaam.com/machine-learning-ai/llm-eval-hallucinations-t20-cricket/](blog)
