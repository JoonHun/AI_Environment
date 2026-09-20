#!/usr/bin/env python3
"""Ollama prefill/decode benchmark, solo models, stdlib only.

Usage:
  python3 bench.py MODEL [MODEL...] [--runs 3] [--num-predict 256] [--ctx 8192]
                      [--draft N] [--base URL] [--prompt-tokens 256]

Notes:
  * Benchmark each model SOLO — stop other loaded models first (SKILL.md rule).
  * --draft overrides each model's Modelfile value (0=off, 4=on) for MTP A/B.
  * Non-streaming /api/generate returns prompt_eval_* (prefill) and eval_* (decode).
  * Reports median of runs; run1 is cold-start (model load) and skews low.
  * Flags a model 'UNSTABLE' when decode swings >5% across runs — do not rank it.
"""
import argparse
import json
import statistics
import time
import urllib.request


def one_run(base, model, prompt, num_predict, ctx, draft):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": num_predict,
            "num_ctx": ctx,
            "draft_num_predict": draft,
        },
    }
    req = urllib.request.Request(
        f"{base.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.loads(r.read().decode())
    pd = d["prompt_eval_duration"] / 1e9
    ed = d["eval_duration"] / 1e9
    prefill = d["prompt_eval_count"] / pd if pd else 0.0
    decode = d["eval_count"] / ed if ed else 0.0
    return prefill, decode


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("models", nargs="+", help="Ollama model tag(s), benchmarked solo")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--num-predict", type=int, default=256)
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--draft", type=int, default=None,
                    help="draft_num_predict override (0=off, 4=on); default: each model's Modelfile value")
    ap.add_argument("--base", default="http://localhost:11434")
    ap.add_argument("--prompt-tokens", type=int, default=256,
                    help="approx input tokens (sentence repeated; ~32 tok/sentence)")
    args = ap.parse_args()

    sentence = ("Explain in detail how a transformer attention mechanism works, "
                "including query, key, value projections, scaled dot-product "
                "attention, and the role of multi-head attention. ")
    reps = max(1, args.prompt_tokens // 32)
    prompt = sentence * reps

    print(f"=== Ollama benchmark | runs={args.runs} num_predict={args.num_predict} "
          f"ctx={args.ctx} draft={args.draft if args.draft is not None else '<modelfile>'} ===")
    results = []
    for model in args.models:
        pres, decs = [], []
        for i in range(args.runs):
            p, dl = one_run(args.base, model, prompt, args.num_predict, args.ctx, args.draft)
            pres.append(p)
            decs.append(dl)
            cold = " (cold-start)" if i == 0 else ""
            print(f"  {model} run{i+1}: prefill {p:8.1f} tok/s | decode {dl:6.1f} tok/s{cold}", flush=True)
            time.sleep(1)
        pmed = statistics.median(pres)
        dmed = statistics.median(decs)
        swing = (max(decs) - min(decs)) / dmed * 100 if dmed else 0.0
        flag = "  UNSTABLE (>5% swing)" if swing > 5 else ""
        results.append((model, pmed, dmed, swing))
        print(f"  >> {model}: prefill {pmed:.1f} | decode {dmed:.1f} tok/s | swing {swing:.0f}%{flag}\n", flush=True)
        time.sleep(3)  # let this model unload before the next loads (solo rule)

    print("=== summary (decode, descending) ===")
    for m, p, d, s in sorted(results, key=lambda r: -r[2]):
        print(f"  {m:48s} prefill {p:8.1f} tok/s | decode {d:6.1f} tok/s | swing {s:.0f}%")


if __name__ == "__main__":
    main()
