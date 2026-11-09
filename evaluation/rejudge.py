"""
Re-score saved benchmark answers with other judges, without re-running the pipeline.

    python evaluation/rejudge.py evaluation/results/benchmark_..._after-fixes_2026-11-09.json \
        --judges anthropic/claude-sonnet-5.5,openai/gpt-6-sol --label after-fixes-2judges
"""

import argparse
import asyncio
import csv
import json
import os
from pathlib import Path

import yaml

from run_benchmark import ROOT, openrouter_usage, score_item, write_results


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("results_json")
    ap.add_argument("--benchmark", default=str(ROOT / "evaluation/benchmark/graduation_sr_v0.yaml"))
    ap.add_argument("--judges", required=True)
    ap.add_argument("--label", required=True)
    args = ap.parse_args()

    saved = json.load(open(args.results_json, encoding="utf-8"))
    items = {i["id"]: i for i in yaml.safe_load(open(args.benchmark, encoding="utf-8"))["items"]}
    included = list(csv.DictReader(open(ROOT / "evaluation/benchmark/graduation_included_studies.csv", encoding="utf-8")))
    judges = args.judges.split(",")
    key = os.environ["OPENROUTER_API_KEY"]
    before = openrouter_usage(key)
    sem = asyncio.Semaphore(4)

    async def one(r):
        async with sem:
            return await score_item(items[r["id"]], r["answer"], r["cited_studies"], r["seconds"], r.get("model_used"),
                                    r.get("error"), included, key, judges, {})

    results = list(await asyncio.gather(*(one(r) for r in saved["results"])))
    after = openrouter_usage(key)
    spend = round(after - before, 4) if before is not None and after is not None else None
    extra = {k: v for k, v in saved["summary"].items() if k in ("pipeline", "model_config", "reader_model", "answer_model")}
    extra["rejudged_from"] = Path(args.results_json).name
    print(json.dumps(write_results(args.label, args.benchmark, saved["summary"]["project_id"], results, extra, judges, spend), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
