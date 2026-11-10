"""
Benchmark gate: fail when answer quality drops (roadmap N3, 10 November 2026).

Runs the graduation benchmark with the production answer path (the reader and answer
models in src/config/settings.py) and compares it with evaluation/benchmark/baseline.json.

    python evaluation/gate.py --mode quick          # 5 items, about $0.15, every pull request
    python evaluation/gate.py --mode full           # 20 items, about $1, before releases
    python evaluation/gate.py --mode full --write-baseline   # after an accepted change

Fails (exit 1) when, against the baseline:
- the mean claim score falls by more than the allowed drop (quick 0.10, full 0.05; a
  single run moves by about 0.03 on the full set and more on five items),
- an evidence-gap question is no longer answered as a gap,
- contradicted claims rise by more than 2,
- any item errors.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASELINE = ROOT / "evaluation/benchmark/baseline.json"
PROJECT = "7efdc60e-e863-480c-929e-616574725e5f"  # Poverty graduation programmes
JUDGES = "anthropic/claude-sonnet-5.5,openai/gpt-6-sol"
ALLOWED_DROP = {"quick": 0.10, "full": 0.05}


def production_models() -> tuple[str, str]:
    from src.config.settings import settings

    return settings.reader_model, settings.answer_model


def run(mode: str, label: str) -> dict:
    reader, answer = production_models()
    cmd = [sys.executable, str(ROOT / "evaluation/run_benchmark.py"),
           str(ROOT / "evaluation/benchmark/graduation_sr_v0.yaml"),
           "--project-id", PROJECT, "--pipeline", "studies", "--label", label,
           "--reader-model", reader, "--answer-models", answer, "--judges", JUDGES]
    if mode == "quick":
        cmd += ["--subset", "quick"]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        print(proc.stdout[-3000:], proc.stderr[-3000:], sep="\n")
        raise SystemExit("benchmark run failed")
    # The run just written is the newest matching file (same-day reruns get a time suffix)
    path = max(glob.glob(str(ROOT / f"evaluation/results/benchmark_graduation_sr_v0_{label}_*.json")),
               key=os.path.getmtime)
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))


def gaps(result: dict) -> dict:
    return {r["id"]: r["refusal_ok"] for r in result["results"] if r["refusal_ok"] is not None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["quick", "full"], default="quick")
    ap.add_argument("--write-baseline", action="store_true")
    args = ap.parse_args()

    result = run(args.mode, f"gate-{args.mode}")
    s = result["summary"]
    current = {
        "mean_claim_score": s["mean_claim_score"],
        "contradicted_claims": s["contradicted_claims"],
        "errors": s["errors"],
        "gaps": gaps(result),
        "models": {"reader": s.get("reader_model"), "answer": s.get("answer_model")},
        "date": s["date"],
        "spend_usd": s.get("openrouter_spend_usd"),
    }
    print(json.dumps(current, indent=2))

    baselines = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    if args.write_baseline:
        baselines[args.mode] = current
        BASELINE.write_text(json.dumps(baselines, indent=2) + "\n", encoding="utf-8")
        print(f"baseline for {args.mode} written to {BASELINE.relative_to(ROOT)}")
        return

    base = baselines.get(args.mode)
    if not base:
        raise SystemExit(f"no {args.mode} baseline: run with --write-baseline first")
    failures = []
    drop = base["mean_claim_score"] - current["mean_claim_score"]
    if drop > ALLOWED_DROP[args.mode]:
        failures.append(f"claim score {current['mean_claim_score']} is {drop:.3f} below the baseline "
                        f"{base['mean_claim_score']} (allowed {ALLOWED_DROP[args.mode]})")
    for item, ok in base["gaps"].items():
        if ok and current["gaps"].get(item) is False:
            failures.append(f"{item} is no longer answered as an evidence gap")
    if current["contradicted_claims"] > base["contradicted_claims"] + 2:
        failures.append(f"contradicted claims rose from {base['contradicted_claims']} to {current['contradicted_claims']}")
    if current["errors"]:
        failures.append(f"{current['errors']} items failed")

    if failures:
        print("\nGATE FAILED:\n- " + "\n- ".join(failures))
        raise SystemExit(1)
    print(f"\nGATE PASSED ({args.mode}): claim score {current['mean_claim_score']} vs baseline {base['mean_claim_score']}")


if __name__ == "__main__":
    main()
