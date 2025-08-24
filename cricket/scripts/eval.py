#!/usr/bin/env python3
import argparse, csv, json, os, time
from openai import OpenAI

def build_prompt(item):
    p = item["prompt"]
    opts = item.get("options") or []
    instr = (
        "Return ONLY JSON. If you can answer by choosing from options, output "
        '{"choice":"<one of options>"}; if the answer is numeric, output '
        '{"number": <integer>}; if unsure, output {"no_answer": true}.'
    )
    if opts:
        return f"{p}\nOptions: {json.dumps(opts, ensure_ascii=True)}\n{instr}"
    return f"{p}\n{instr}"

def call_openai(client, model, prompt, temperature, max_tokens):
    if model.startswith("gpt-5"):
        params = {
            "model": model,
            "input": [
                {"role": "system", "content": "Answer concisely. Output valid JSON only as instructed."},
                {"role": "user", "content": prompt},
            ],
            "text": {"verbosity": "low"},
        }
        r = client.responses.create(**params)
        return (r.output_text or "").strip()
    else:
        params = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Answer concisely. Output valid JSON only as instructed."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if model.startswith("gpt-4o-search-preview"):
            del params["temperature"]

        r = client.chat.completions.create(**params)
        return (r.choices[0].message.content or "").strip()


def parse_json(s):
    try:
        return json.loads(s)
    except Exception:
        try:
            i, j = s.index("{"), s.rindex("}") + 1
            return json.loads(s[i:j])
        except Exception:
            return None

def eval_item(item, raw):
    answered, correct, pred = 0, 0, ""
    obj = parse_json(raw)
    if not isinstance(obj, dict) or obj.get("no_answer") is True:
        return answered, correct, pred
    # choice path
    if "choice" in obj and (item.get("options") is not None):
        choice = obj.get("choice")
        if not isinstance(choice, str):
            return answered, correct, pred
        options = item.get("options") or []
        if options and choice not in options:
            return answered, correct, pred  # invalid option -> unanswered
        gold_set = item.get("gold_set") or ([item["gold"]] if "gold" in item and isinstance(item["gold"], str) else [])
        answered = 1
        correct = 1 if (gold_set and choice in gold_set) else 0
        pred = choice
        return answered, correct, pred
    # number path
    if "number" in obj and ("gold" in item):
        num = obj.get("number")
        if not isinstance(num, int):
            return answered, correct, pred
        answered = 1
        correct = 1 if int(item["gold"]) == num else 0
        pred = str(num)
        return answered, correct, pred
    # otherwise unanswered
    return answered, correct, pred

def summarize(rows):
    n = len(rows)
    ans = sum(r["answered"] for r in rows)
    cor = sum(r["correct"] for r in rows)
    hal = sum(1 for r in rows if r["answered"] and not r["correct"])
    by = {}
    for r in rows:
        by.setdefault(r["type"], []).append(r)
    by_type = {}
    for k, v in by.items():
        a = sum(x["answered"] for x in v)
        c = sum(x["correct"] for x in v)
        h = sum(1 for x in v if x["answered"] and not x["correct"])
        by_type[k] = {
            "n": len(v),
            "answer_rate": a / len(v) if v else 0.0,
            "accuracy_when_answered": (c / a) if a else 0.0,
            "hallucination_rate_when_answered": (h / a) if a else 0.0,
        }
    return {
        "n": n,
        "answer_rate": ans / n if n else 0.0,
        "accuracy_overall": cor / n if n else 0.0,
        "accuracy_when_answered": (cor / ans) if ans else 0.0,
        "hallucination_rate_when_answered": (hal / ans) if ans else 0.0,
        "by_type": by_type,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qa", default="t20_qa_sample.jsonl")
    ap.add_argument("--out_dir", default="out_eval")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max_tokens", type=int, default=32)
    ap.add_argument("--rate_sleep", type=float, default=0.0)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    client = OpenAI()

    rows = []
    with open(args.qa, "r") as f:
        for i, line in enumerate(f, 1):
            item = json.loads(line)
            prompt = build_prompt(item)
            try:
                raw = call_openai(client, args.model, prompt, args.temperature, args.max_tokens)
            except Exception as e:
                raw = f"ERROR: {e}"
            answered, correct, pred = eval_item(item, raw)
            rows.append({
                "idx": i,
                "type": item.get("type", ""),
                "source": item.get("source", ""),
                "prompt": item["prompt"],
                "gold": item.get("gold", item.get("gold_set", [])),
                "pred": pred,
                "answered": answered,
                "correct": correct,
                "hallucination": 1 if (answered and not correct) else 0,
                "model_raw": raw,
            })
            if args.rate_sleep > 0:
                time.sleep(args.rate_sleep)

    # outputs.jsonl
    out_jsonl = os.path.join(args.out_dir, "outputs.jsonl")
    with open(out_jsonl, "w") as w:
        for r in rows:
            w.write(json.dumps(r, ensure_ascii=True) + "\n")

    # items.csv
    out_items = os.path.join(args.out_dir, "items.csv")
    with open(out_items, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["idx","type","source","answered","correct","hallucination","gold","pred","prompt","model_raw"])
        for r in rows:
            wr.writerow([r["idx"], r["type"], r["source"], r["answered"], r["correct"],
                         r["hallucination"], json.dumps(r["gold"], ensure_ascii=True), r["pred"], r["prompt"], r["model_raw"]])

    # wrong.csv (answered but incorrect)
    out_wrong = os.path.join(args.out_dir, "wrong.csv")
    with open(out_wrong, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["idx","type","source","gold","pred","prompt","model_raw"])
        for r in rows:
            if r["answered"] == 1 and r["correct"] == 0:
                wr.writerow([r["idx"], r["type"], r["source"], json.dumps(r["gold"], ensure_ascii=True),
                             r["pred"], r["prompt"], r["model_raw"]])

    # summary.json
    summ = summarize(rows)
    summ.update({
        "outputs_jsonl": out_jsonl,
        "items_csv": out_items,
        "wrong_csv": out_wrong,
    })
    with open(os.path.join(args.out_dir, "summary.json"), "w") as f:
        json.dump(summ, f, indent=2)

    print(json.dumps({
        "n": summ["n"],
        "answer_rate": round(summ["answer_rate"], 4),
        "accuracy_overall": round(summ["accuracy_overall"], 4),
        "accuracy_when_answered": round(summ["accuracy_when_answered"], 4),
        "hallucination_rate_when_answered": round(summ["hallucination_rate_when_answered"], 4),
        "items_csv": out_items,
        "wrong_csv": out_wrong
    }, indent=2))

if __name__ == "__main__":
    main()

