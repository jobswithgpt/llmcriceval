#!/usr/bin/env python3
import argparse, json, random

def sample_jsonl(in_path, out_path, n, seed):
    rng = random.Random(seed)
    buf = []
    with open(in_path, "r") as f:
        for line in f:
            obj = json.loads(line)
            buf.append(obj)
    rng.shuffle(buf)
    buf = buf[:n]
    with open(out_path, "w") as w:
        for obj in buf:
            w.write(json.dumps(obj, ensure_ascii=True) + "\n")
    print(f"sampled {len(buf)} -> {out_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="t20_qa_all.jsonl")
    ap.add_argument("--out", default="t20_qa_sample.jsonl")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    sample_jsonl(args.inp, args.out, args.n, args.seed)

if __name__ == "__main__":
    main()

