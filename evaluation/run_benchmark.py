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


async def judge(item: dict, answer: str, key: str) -> dict:
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
            json={"model": JUDGE_MODEL, "temperature": 0, "max_tokens": 1500,
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


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("benchmark")
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--only", help="comma-separated item ids")
    ap.add_argument("--label", default="baseline")
    args = ap.parse_args()

    from src.agents.evidence_assistant_agent import EvidenceAssistantAgent, SearchSettings
    from src.retrieval.hybrid_retriever import HybridRetriever

    bench = yaml.safe_load(open(args.benchmark, encoding="utf-8"))
    items = bench["items"]
    if args.only:
        wanted = set(args.only.split(","))
        items = [i for i in items if i["id"] in wanted]
    included = list(csv.DictReader(open(ROOT / "evaluation/benchmark/graduation_included_studies.csv", encoding="utf-8")))

    key = os.environ["OPENROUTER_API_KEY"]
    spend_before = openrouter_usage(key)
    model_config = project_model_config(args.project_id)
    agent = EvidenceAssistantAgent(retriever=HybridRetriever(project_id=args.project_id))

    results = []
    for item in items:
        print(f"[{item['id']}] {item['question'][:80]}", flush=True)
        t0 = time.time()
        try:
            resp = await agent.chat(query=item["question"], include_citations=True,
                                    search_settings=SearchSettings(), model_config=model_config)
            answer, citations, model = resp.answer, resp.citations or [], resp.model_used
            error = None
        except Exception as e:  # record and continue
            answer, citations, model, error = "", [], None, f"{type(e).__name__}: {e}"
        seconds = round(time.time() - t0, 1)
        cited = sorted({c.get("study_id") for c in citations if c.get("study_id")})

        gold = gold_studies(item, included)
        recall = None
        if gold:
            recall = {"gold": len(gold), "found": len(gold & set(cited)), "recall": round(len(gold & set(cited)) / len(gold), 3)}

        try:
            verdict = await judge(item, answer, key)
        except Exception as e:
            verdict = {"error": f"{type(e).__name__}: {e}"}

        claims = verdict.get("claims", [])
        score = (sum({"supported": 1, "partly": 0.5}.get(c.get("verdict"), 0) for c in claims) / len(claims)) if claims else None
        results.append({
            "id": item["id"], "type": item["type"], "question": item["question"], "seconds": seconds,
            "model_used": model, "error": error, "answer": answer, "cited_studies": cited,
            "n_studies": len(cited), "recall": recall, "judge": verdict,
            "claim_score": round(score, 3) if score is not None else None,
            "contradicted": sum(1 for c in claims if c.get("verdict") == "contradicted"),
            "must_not_violations": len([v for v in verdict.get("must_not_violations", []) if v]),
            "refusal_ok": verdict.get("refusal_ok"),
        })
        print(f"    {seconds}s, {len(cited)} studies, claim score {results[-1]['claim_score']}, "
              f"recall {recall['recall'] if recall else '-'}", flush=True)

    spend_after = openrouter_usage(key)
    scored = [r for r in results if r["claim_score"] is not None]
    summary = {
        "benchmark": Path(args.benchmark).name, "label": args.label, "date": date.today().isoformat(),
        "project_id": args.project_id, "model_config": model_config, "judge_model": JUDGE_MODEL,
        "items": len(results), "errors": sum(1 for r in results if r["error"]),
        "mean_claim_score": round(sum(r["claim_score"] for r in scored) / len(scored), 3) if scored else None,
        "contradicted_claims": sum(r["contradicted"] for r in results),
        "must_not_violations": sum(r["must_not_violations"] for r in results),
        "refusal_ok": f"{sum(1 for r in results if r['refusal_ok'] is True)}/{sum(1 for r in results if r['refusal_ok'] is not None)}",
        "mean_studies_cited": round(sum(r["n_studies"] for r in results) / len(results), 1) if results else None,
        "mean_seconds": round(sum(r["seconds"] for r in results) / len(results), 1) if results else None,
        "openrouter_spend_usd": round(spend_after - spend_before, 4) if spend_before is not None and spend_after is not None else None,
    }

    out = ROOT / "evaluation/results" / f"benchmark_{Path(args.benchmark).stem}_{args.label}_{date.today().isoformat()}"
    out.with_suffix(".json").write_text(json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Benchmark {summary['benchmark']}: {args.label} ({summary['date']})", "",
             "| Metric | Value |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in summary.items() if k not in ("model_config",)]
    lines += ["", "| Item | Type | Claim score | Contradicted | Studies | Recall | Refusal ok | Seconds |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in results:
        rec = f"{r['recall']['found']}/{r['recall']['gold']}" if r["recall"] else "-"
        lines.append(f"| {r['id']} | {r['type']} | {r['claim_score']} | {r['contradicted']} | {r['n_studies']} | {rec} | {r['refusal_ok']} | {r['seconds']} |")
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
