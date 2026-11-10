"""
Run a benchmark YAML against the Evidence Assistant agent and score the answers.

    python evaluation/run_benchmark.py evaluation/benchmark/graduation_sr_v0.yaml \
        --project-id 7efdc60e-e863-480c-929e-616574725e5f

For each item it runs the same agent the API runs (HybridRetriever on the project,
the project's model_config, default search settings) and records the answer, the
cited studies and the time taken. Then:

- an LLM judge marks each gold claim supported, partly supported, contradicted or
  missing, flags must_not statements, and checks refusal on gap items;
- retrieval recall is computed against the review's included studies held in the
  collection (evaluation/benchmark/graduation_included_studies.csv): all of them for
  the broad effectiveness items, the programme's studies for country items.

Results go to evaluation/results/benchmark_<name>_<date>.json and .md. The OpenRouter
spend for the run is read from the key's usage before and after.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

JUDGE_MODEL = "anthropic/claude-sonnet-5.5"
# Items whose gold set for recall is every included study in the collection
BROAD_RECALL_TYPES = {"synthesis"}
# Country items: gold set is the included studies of the named programme
PROGRAMME_FOR_ITEM = {"grad-012": "bab amal", "grad-013": "forsa", "grad-014": "forsa", "grad-019": "haku"}

JUDGE_PROMPT = """You grade an answer from a research assistant against gold claims taken from a
systematic review. Judge meaning, not wording. The assistant only sees a subset of the
review's studies, so a claim stated more cautiously but in the same direction is
"partly". A claim the answer does not address is "missing". A claim the answer states
the opposite of is "contradicted".

QUESTION: {question}

ANSWER:
{answer}

GOLD CLAIMS:
{claims}

STATEMENTS THAT COUNT AS ERRORS (must_not):
{must_not}

{refusal_rule}

Return JSON only:
{{"claims": [{{"claim": "<gold claim>", "verdict": "supported|partly|contradicted|missing", "note": "<short reason>"}}],
  "must_not_violations": ["<which must_not statement the answer makes, if any>"],
  "refusal_ok": true | false | null,
  "overall_note": "<one sentence>"}}"""


def openrouter_usage(key: str) -> float | None:
    try:
        r = httpx.get("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {key}"}, timeout=20)
        return float(r.json()["data"]["usage"])
    except Exception:
        return None


async def judge(item: dict, answer: str, key: str, model: str = JUDGE_MODEL) -> dict:
    refusal_rule = (
        "This is an evidence-gap question: refusal_ok is true only if the answer says the evidence is "
        "limited or absent and does not present unsupported findings as established."
        if item.get("expect_refusal") else "refusal_ok: null (not a gap question)."
    )
    prompt = JUDGE_PROMPT.format(
        question=item["question"],
        answer=answer or "(no answer)",
        claims="\n".join(f"- {c}" for c in item.get("gold_claims", [])),
        must_not="\n".join(f"- {c}" for c in item.get("must_not", [])) or "- (none)",
        refusal_rule=refusal_rule,
    )
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "temperature": 0, "max_tokens": 1500,
                  "messages": [{"role": "user", "content": prompt}]},
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def gold_studies(item: dict, included: list[dict]) -> set[str] | None:
    held = [r for r in included if r["in_collection"] == "yes"]
    if item["id"] in PROGRAMME_FOR_ITEM:
        name = PROGRAMME_FOR_ITEM[item["id"]]
        ids = {d for r in held if name in r["program"].lower() for d in r["doc_ids"].split("|") if d}
        return ids
    if item["type"] in BROAD_RECALL_TYPES:
        return {d for r in held for d in r["doc_ids"].split("|") if d}
    return None


def project_model_config(project_id: str) -> dict | None:
    from supabase import create_client

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    row = client.table("rag_projects").select("model_config").eq("id", project_id).single().execute().data
    return (row or {}).get("model_config")


def claim_score(verdict: dict, kinds: list | None = None, only: str | None = None) -> float | None:
    """Share of gold claims supported (partly = 0.5). With `only`, score just the claims of that kind."""
    claims = verdict.get("claims", [])
    if only and kinds:
        claims = [c for i, c in enumerate(claims) if i < len(kinds) and kinds[i] == only]
    if not claims:
        return None
    return sum({"supported": 1, "partly": 0.5}.get(c.get("verdict"), 0) for c in claims) / len(claims)


async def score_item(item: dict, answer: str, cited: list, seconds: float, model: str | None,
                     error: str | None, included: list, key: str, judges: list, extra: dict) -> dict:
    gold = gold_studies(item, included)
    recall = None
    if gold:
        hit = len(gold & set(cited))
        recall = {"gold": len(gold), "found": hit, "recall": round(hit / len(gold), 3)}
    verdicts = {}
    for jm in judges:
        try:
            verdicts[jm] = await judge(item, answer, key, jm)
        except Exception as e:
            verdicts[jm] = {"error": f"{type(e).__name__}: {e}"}
    by_judge = {jm: claim_score(v) for jm, v in verdicts.items()}
    kinds = item.get("claim_kinds") or ["study"] * len(item.get("gold_claims", []))
    study_scores = [x for x in (claim_score(v, kinds, "study") for v in verdicts.values()) if x is not None]
    scores = [v for v in by_judge.values() if v is not None]
    primary = verdicts[judges[0]]
    claims = primary.get("claims", [])
    return {
        "id": item["id"], "type": item["type"], "question": item["question"], "seconds": seconds,
        "model_used": model, "error": error, "answer": answer, "cited_studies": cited,
        "n_studies": len(cited), "recall": recall, "judge": primary, "judges": verdicts,
        "claim_score": round(sum(scores) / len(scores), 3) if scores else None,
        "claim_score_by_judge": {jm: (round(v, 3) if v is not None else None) for jm, v in by_judge.items()},
        "study_claim_score": round(sum(study_scores) / len(study_scores), 3) if study_scores else None,
        "contradicted": sum(1 for c in claims if c.get("verdict") == "contradicted"),
        "must_not_violations": len([v for v in primary.get("must_not_violations", []) if v]),
        "refusal_ok": primary.get("refusal_ok"),
        **extra,
    }


def write_results(label: str, bench_path: str, project_id: str, results: list, extra_summary: dict,
                  judges: list, spend: float | None) -> dict:
    scored = [r for r in results if r["claim_score"] is not None]

    def judge_mean(jm):
        vals = [r["claim_score_by_judge"].get(jm) for r in results if r["claim_score_by_judge"].get(jm) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    summary = {
        "benchmark": Path(bench_path).name, "label": label, "date": date.today().isoformat(),
        "project_id": project_id, **extra_summary, "judge_models": judges,
        "items": len(results), "errors": sum(1 for r in results if r["error"]),
        "mean_claim_score": round(sum(r["claim_score"] for r in scored) / len(scored), 3) if scored else None,
        "mean_claim_score_by_judge": {jm: judge_mean(jm) for jm in judges},
        "mean_study_claim_score": round(sum(r["study_claim_score"] for r in results if r.get("study_claim_score") is not None)
                                        / max(1, sum(1 for r in results if r.get("study_claim_score") is not None)), 3),
        "contradicted_claims": sum(r["contradicted"] for r in results),
        "must_not_violations": sum(r["must_not_violations"] for r in results),
        "refusal_ok": f"{sum(1 for r in results if r['refusal_ok'] is True)}/{sum(1 for r in results if r['refusal_ok'] is not None)}",
        "mean_studies_cited": round(sum(r["n_studies"] for r in results) / len(results), 1) if results else None,
        "mean_seconds": round(sum(r["seconds"] for r in results) / len(results), 1) if results else None,
        "openrouter_spend_usd": spend,
    }
    safe_label = label.replace(".", "-")  # dots would be read as a file suffix
    out = ROOT / "evaluation/results" / f"benchmark_{Path(bench_path).stem}_{safe_label}_{date.today().isoformat()}"
    out.with_suffix(".json").write_text(json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Benchmark {summary['benchmark']}: {label} ({summary['date']})", "", "| Metric | Value |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in summary.items() if k != "model_config"]
    lines += ["", "| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in results:
        rec = f"{r['recall']['found']}/{r['recall']['gold']}" if r["recall"] else "-"
        lines.append(f"| {r['id']} | {r['type']} | {r['claim_score']} | {r['contradicted']} | {r['n_studies']} | {rec} | {r['refusal_ok']} | {r['seconds']} |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def spend_since(key: str, before: float | None) -> float | None:
    after = openrouter_usage(key)
    return round(after - before, 4) if before is not None and after is not None else None


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("benchmark")
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--only", help="comma-separated item ids")
    ap.add_argument("--subset", choices=["quick"], help="run only items marked quick: true")
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--pipeline", choices=["agent", "studies"], default="agent")
    ap.add_argument("--answer-models", default="anthropic/claude-sonnet-5.5",
                    help="studies pipeline: comma-separated answer models sharing one reading pass")
    ap.add_argument("--reader-model", default="anthropic/claude-haiku-5.5")
    ap.add_argument("--judges", default=JUDGE_MODEL, help="comma-separated judge models; the first is primary")
    args = ap.parse_args()

    bench = yaml.safe_load(open(args.benchmark, encoding="utf-8"))
    items = bench["items"]
    if args.only:
        wanted = set(args.only.split(","))
        items = [i for i in items if i["id"] in wanted]
    if args.subset == "quick":
        items = [i for i in items if i.get("quick")]
    included = list(csv.DictReader(open(ROOT / "evaluation/benchmark/graduation_included_studies.csv", encoding="utf-8")))
    judges = args.judges.split(",")
    key = os.environ["OPENROUTER_API_KEY"]

    if args.pipeline == "agent":
        from src.agents.evidence_assistant_agent import EvidenceAssistantAgent, SearchSettings
        from src.retrieval.hybrid_retriever import HybridRetriever

        before = openrouter_usage(key)
        model_config = project_model_config(args.project_id)
        agent = EvidenceAssistantAgent(retriever=HybridRetriever(project_id=args.project_id))
        results = []
        for item in items:
            print(f"[{item['id']}] {item['question'][:80]}", flush=True)
            t0 = time.time()
            try:
                resp = await agent.chat(query=item["question"], include_citations=True,
                                        search_settings=SearchSettings(), model_config=model_config)
                answer, citations, model, error = resp.answer, resp.citations or [], resp.model_used, None
            except Exception as e:
                answer, citations, model, error = "", [], None, f"{type(e).__name__}: {e}"
            cited = sorted({c.get("study_id") for c in citations if c.get("study_id")})
            r = await score_item(item, answer, cited, round(time.time() - t0, 1), model, error, included, key, judges, {})
            results.append(r)
            print(f"    {r['seconds']}s, {r['n_studies']} studies, claim score {r['claim_score']}, "
                  f"recall {r['recall']['recall'] if r['recall'] else '-'}", flush=True)
        summary = write_results(args.label, args.benchmark, args.project_id, results,
                                {"pipeline": "agent", "model_config": model_config}, judges, spend_since(key, before))
        print(json.dumps(summary, indent=2))
        return

    # Studies pipeline: read once per question, then answer with each model
    from src.agents.study_synthesis import StudySynthesisPipeline

    answer_models = args.answer_models.split(",")
    pipe = StudySynthesisPipeline(args.project_id, reader_model=args.reader_model, answer_model=answer_models[0])
    before = openrouter_usage(key)
    readings_by_item, read_meta = {}, {}
    for item in items:
        print(f"[{item['id']}] reading: {item['question'][:70]}", flush=True)
        readings, timing = await pipe.read_studies(item["question"])
        readings_by_item[item["id"]], read_meta[item["id"]] = readings, timing
        print(f"    {timing} relevant={sum(1 for r in readings if r.relevant)}", flush=True)
    read_spend = spend_since(key, before)
    read_seconds = {k: v["retrieve_s"] + v["rerank_s"] + v["read_s"] for k, v in read_meta.items()}

    summaries = {}
    for model in answer_models:
        pipe.answer_model = model
        short = model.split("/")[-1]
        before = openrouter_usage(key)
        sem = asyncio.Semaphore(4)  # items answered and judged in parallel

        async def run_one(item):
            async with sem:
                readings = readings_by_item[item["id"]]
                t0 = time.time()
                try:
                    res = await pipe.answer(item["question"], readings)
                    answer, cited, error = res.answer, sorted({c["study_id"] for c in res.citations}), None
                except Exception as e:
                    answer, cited, error = "", [], f"{type(e).__name__}: {e}"
                seconds = round(read_seconds[item["id"]] + (time.time() - t0), 1)
                extra = {"studies_read": len(readings), "studies_relevant": sum(1 for r in readings if r.relevant),
                         "read_timing": read_meta[item["id"]]}
                r = await score_item(item, answer, cited, seconds, model, error, included, key, judges, extra)
                print(f"[{short}] {item['id']} {r['seconds']}s, read {extra['studies_read']}, relevant "
                      f"{extra['studies_relevant']}, cited {r['n_studies']}, claim score {r['claim_score']}", flush=True)
                return r

        results = list(await asyncio.gather(*(run_one(item) for item in items)))
        summaries[model] = write_results(
            f"{args.label}_{short}", args.benchmark, args.project_id, results,
            {"pipeline": "studies", "reader_model": args.reader_model, "answer_model": model,
             "reading_spend_usd_shared": read_spend}, judges, spend_since(key, before))
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
