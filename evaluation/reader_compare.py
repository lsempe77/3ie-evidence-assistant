"""
Compare reader models on the same candidate studies (roadmap N3, 10 November 2026).

For each benchmark question the candidate studies are found once; then every reader
model reads the same studies. Haiku 5.5 is the reference reader. Reported per model:
agreement with the reference on relevance (and Cohen's kappa), recall and precision
of the reference's relevant studies, agreement on direction, JSON failures, how many
numbers in its findings appear in the passages it was given (an invented-figure
check), time and measured OpenRouter spend.

    python evaluation/reader_compare.py --project-id <uuid> \
        --models anthropic/claude-haiku-5.5,z-ai/glm-5.3-flash,deepseek/deepseek-v4.1-flash-1017
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from run_benchmark import openrouter_usage  # noqa: E402
from src.agents.study_synthesis import PASSAGES_PER_STUDY, StudySynthesisPipeline  # noqa: E402

NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")


def numbers_in(text: str) -> set:
    # Ignore single digits and four-digit years, which match anywhere by chance
    out = set()
    for n in NUMBER.findall(text or ""):
        n = n.replace(",", ".")
        if len(n.replace(".", "")) < 2 or re.fullmatch(r"(19|20)\d\d", n):
            continue
        out.add(n)
    return out


def kappa(a: list, b: list) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--benchmark", default=str(ROOT / "evaluation/benchmark/graduation_sr_v0.yaml"))
    ap.add_argument("--models", required=True, help="comma-separated; the first is the reference reader")
    ap.add_argument("--only")
    args = ap.parse_args()

    models = args.models.split(",")
    items = yaml.safe_load(open(args.benchmark, encoding="utf-8"))["items"]
    if args.only:
        items = [i for i in items if i["id"] in set(args.only.split(","))]
    key = os.environ["OPENROUTER_API_KEY"]
    pipe = StudySynthesisPipeline(args.project_id, reader_model=models[0])

    per_model = {m: {"readings": {}, "seconds": 0.0, "spend": 0.0} for m in models}
    texts = {}  # (item, study) -> passages given to the readers
    for item in items:
        groups, _ = await pipe.candidate_groups(item["question"])
        for sid, rows in groups:
            texts[(item["id"], sid)] = " ".join(r.text for r in rows[:PASSAGES_PER_STUDY])
        print(f"[{item['id']}] {len(groups)} candidate studies", flush=True)
        for m in models:
            before = openrouter_usage(key)
            t0 = time.time()
            readings = await pipe.read_groups(item["question"], groups, model=m)
            per_model[m]["seconds"] += time.time() - t0
            after = openrouter_usage(key)
            if before is not None and after is not None:
                per_model[m]["spend"] += after - before
            per_model[m]["readings"][item["id"]] = readings
            print(f"    {m:42} relevant {sum(r.relevant for r in readings):3}  errors {sum(1 for r in readings if r.error)}"
                  f"  {time.time() - t0:5.1f}s", flush=True)

    ref = models[0]
    summary = {}
    for m in models:
        ref_rel, m_rel, dir_agree, dir_total, errors, n = [], [], 0, 0, 0, 0
        grounded = total_nums = 0
        for item in items:
            ref_by = {r.study_id: r for r in per_model[ref]["readings"][item["id"]]}
            for r in per_model[m]["readings"][item["id"]]:
                rr = ref_by[r.study_id]
                n += 1
                errors += bool(r.error)
                ref_rel.append(int(rr.relevant and bool(rr.finding)))
                m_rel.append(int(r.relevant and bool(r.finding)))
                if rr.relevant and r.relevant and rr.direction and r.direction:
                    dir_total += 1
                    dir_agree += rr.direction == r.direction
                if r.relevant and r.finding:
                    nums = numbers_in(r.finding)
                    source = texts[(item["id"], r.study_id)].replace(",", ".")
                    total_nums += len(nums)
                    grounded += sum(1 for x in nums if x in source)
        tp = sum(1 for a, b in zip(ref_rel, m_rel) if a and b)
        summary[m] = {
            "studies_read": n,
            "relevant": sum(m_rel),
            "agreement_with_reference": round(sum(a == b for a, b in zip(ref_rel, m_rel)) / n, 3),
            "kappa_with_reference": kappa(ref_rel, m_rel),
            "recall_of_reference_relevant": round(tp / max(1, sum(ref_rel)), 3),
            "precision_vs_reference": round(tp / max(1, sum(m_rel)), 3),
            "direction_agreement": round(dir_agree / dir_total, 3) if dir_total else None,
            "json_or_call_errors": errors,
            "numbers_in_findings": total_nums,
            "numbers_found_in_passages": round(grounded / total_nums, 3) if total_nums else None,
            "seconds_per_question": round(per_model[m]["seconds"] / len(items), 1),
            "openrouter_spend_usd": round(per_model[m]["spend"], 4),
            "spend_per_question_usd": round(per_model[m]["spend"] / len(items), 4),
        }

    out = ROOT / "evaluation/results" / f"reader_compare_{date.today().isoformat()}"
    out.with_suffix(".json").write_text(json.dumps({"reference": ref, "items": len(items), "summary": summary}, indent=2), encoding="utf-8")
    cols = ["relevant", "agreement_with_reference", "kappa_with_reference", "recall_of_reference_relevant",
            "precision_vs_reference", "direction_agreement", "json_or_call_errors", "numbers_found_in_passages",
            "seconds_per_question", "spend_per_question_usd"]
    lines = [f"# Reader comparison ({date.today().isoformat()}), reference {ref}, {len(items)} questions", "",
             "| Model | " + " | ".join(cols) + " |", "| --- |" + " --- |" * len(cols)]
    lines += [f"| {m} | " + " | ".join(str(summary[m][c]) for c in cols) + " |" for m in models]
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
