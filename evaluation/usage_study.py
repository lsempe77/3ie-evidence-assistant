"""
What goes into an answer? A usage study of paragraphs (started 11 Nov 2026).

Follows every passage from the index to the answer, over many varied questions, and maps
each one back to the paragraph of the paper it came from and that paragraph's role
(src/extraction/relevance_labels.py). For each role it reports the share of the stored
text, of what the reader is shown, of what the reader uses as its supporting quote, and of
what ends up cited, plus how often a shown passage of that role is used.

    python evaluation/usage_study.py labels    --project-id <uuid>   # label every paragraph (~2 cents a paper)
    python evaluation/usage_study.py questions --project-id <uuid>   # write the question set
    python evaluation/usage_study.py run       --project-id <uuid>   # read and answer each question (~4.5 cents each)
    python evaluation/usage_study.py analyse   --project-id <uuid>

Everything is written under evaluation/results/usage_study/<project-id>/. The run logs hold
passage text from the papers: keep them local.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.extraction.relevance_labels import KEEP, keep_results_tables, label_units, units_from_content  # noqa: E402
from src.extraction.store_estimates import DEFAULT_MODEL, _r2  # noqa: E402
from src.extraction.table_estimates import _chat, _parse_json  # noqa: E402

CATEGORIES = {
    "effects": "effects of the programme on a specific outcome (income, consumption, assets, savings, food security, poverty, employment, health, education, psychosocial wellbeing, empowerment)",
    "subgroups": "whether effects differ for a subgroup (women, female-headed households, the poorest, youth, refugees, rural or urban households)",
    "durability": "whether effects last, fade or grow over time after the programme ends",
    "costs": "costs per beneficiary, cost-effectiveness, benefit-cost ratios, value for money",
    "implementation": "how programmes are delivered: coaching, targeting, transfers, staffing, fidelity, take-up, challenges",
    "mechanisms": "why programmes work or fail: channels, constraints, aspirations, market conditions",
    "design": "how the evidence was produced: study designs, RCTs, sample sizes, attrition, measurement",
    "context": "where and for whom: countries, populations, targeting criteria, baseline conditions",
    "variants": "comparisons of programme variants or components (cash vs assets, group vs individual coaching, with or without savings)",
    "side_effects": "spillovers to non-participants, negative or unintended effects",
    "gaps": "what the evidence does not cover, where it is thin",
}

QUESTIONS_PROMPT = """You write realistic questions that researchers and policy staff would ask an
evidence assistant holding a collection of studies on poverty graduation programmes.

COLLECTION OVERVIEW:
{overview}

Write {n} questions in the category: {category} ({description}).
Vary the wording, outcome, country, programme and level of detail. Some short, some specific.
Ask about the evidence, as a user would. Do not mention "the collection" or study numbers.
Return JSON only: {{"questions": ["...", "..."]}}"""

PAPER_PROMPT = """A researcher is using an evidence assistant over a collection of studies on poverty
graduation programmes. Write {n} questions they might ask that THIS paper would help answer, in
different categories ({categories}). Phrase them as questions about the evidence in general, not about
this paper (do not name its authors).

PAPER: {title}
PROGRAMME: {programme}
WHAT IT REPORTS: {summary}

Return JSON only: {{"questions": [{{"category": "<category>", "question": "..."}}]}}"""


def out_dir(project_id: str) -> Path:
    d = ROOT / "evaluation" / "results" / "usage_study" / project_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def rest() -> httpx.Client:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return httpx.Client(base_url=url, headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=120)


def documents(db: httpx.Client, project_id: str) -> List[Dict[str, Any]]:
    return db.get("/documents", params={"select": "id,filename", "rag_project_id": f"eq.{project_id}",
                                        "status": "eq.completed"}).json()


def load_content(project_id: str, doc_key: str, cache: Path) -> List[Dict[str, Any]]:
    path = cache / f"{doc_key[:80]}.json"
    if not path.exists():
        obj = _r2().get_object(Bucket=os.environ.get("R2_BUCKET_NAME", "devchat-pdfs"),
                               Key=f"rags/{project_id}/outputs/json/{doc_key}.json")
        path.write_bytes(obj["Body"].read())
    return json.loads(path.read_text(encoding="utf-8")).get("content_list") or []


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or "")).replace("−", "-").replace("–", "-").lower()


# ---------------------------------------------------------------- 1. labels

def estimate_table_units(units: List[Dict[str, Any]], estimates: List[Dict[str, Any]]) -> set:
    found = set()
    tables = [(k, u) for k, u in enumerate(units) if u["kind"] == "table"]
    for e in estimates:
        cell = _norm((e.get("literal_text") or "").split(" (")[0])
        for k, u in tables:
            if u["page"] == e.get("page") and cell and cell in u.setdefault("_norm", _norm(u["text"])):
                found.add(k)
                break
    return found


async def cmd_labels(args) -> None:
    d = out_dir(args.project_id)
    cache = d / "content"
    cache.mkdir(exist_ok=True)
    (d / "labels").mkdir(exist_ok=True)
    with rest() as db:
        docs = documents(db, args.project_id)
        todo = [x for x in docs if not (d / "labels" / f"{x['filename'][:80]}.json").exists()]
        print(f"{len(todo)} of {len(docs)} documents to label")
        sem = asyncio.Semaphore(4)

        async def one(doc):
            async with sem:
                key = doc["filename"]
                content = await asyncio.to_thread(load_content, args.project_id, key, cache)
                units = units_from_content(content)
                labels = await label_units(units, DEFAULT_MODEL, os.environ["OPENROUTER_API_KEY"])
                est = await asyncio.to_thread(lambda: db.get("/effect_estimates", params={
                    "select": "literal_text,page", "rag_project_id": f"eq.{args.project_id}",
                    "doc_key": f"eq.{key}", "source": "eq.tables_v1", "limit": "5000"}).json())
                labels = keep_results_tables(units, labels, estimate_table_units(units, est))
                (d / "labels" / f"{key[:80]}.json").write_text(json.dumps({
                    "doc_key": key, "labels": labels,
                    "units": [{"page": u["page"], "kind": u["kind"], "words": len(u["text"].split())} for u in units],
                }), encoding="utf-8")
                kept = sum(u_["words"] for u_, lab in zip(
                    [{"words": len(u["text"].split())} for u in units], labels) if lab in KEEP)
                total = sum(len(u["text"].split()) for u in units) or 1
                print(f"  {key[:60]:60} {len(units):4} paragraphs, kept {100 * kept / total:.0f}%", flush=True)

        await asyncio.gather(*(one(x) for x in todo))


# ---------------------------------------------------------------- 2. questions

def benchmark_questions() -> List[Dict[str, str]]:
    import yaml

    bench = yaml.safe_load((ROOT / "evaluation/benchmark/graduation_sr_v0.yaml").read_text(encoding="utf-8"))
    return [{"id": i["id"], "source": "benchmark", "category": "benchmark", "question": i["question"]} for i in bench["items"]]


async def cmd_questions(args) -> None:
    from src.agents.evidence_summary import summary_lines
    from src.vectorstore.chunk_store import ChunkStore

    d = out_dir(args.project_id)
    facts = ChunkStore().study_facts(args.project_id)
    overview = "\n".join(summary_lines(facts)[:3])
    programmes = sorted({f.get("programme_group") or f.get("programme") for f in facts.values() if f.get("programme")})
    overview += "\nProgrammes include: " + "; ".join(programmes[:45])
    key = os.environ["OPENROUTER_API_KEY"]
    out: List[Dict[str, str]] = benchmark_questions()
    async with httpx.AsyncClient(timeout=300, headers={"Authorization": f"Bearer {key}"}) as client:
        async def by_category(cat, desc):
            data = _parse_json(await _chat(client, DEFAULT_MODEL, QUESTIONS_PROMPT.format(
                overview=overview, n=args.per_category, category=cat, description=desc)))
            return [{"source": "category", "category": cat, "question": q} for q in data.get("questions") or []]

        random.seed(7)
        papers = random.sample([(k, f) for k, f in facts.items() if f.get("is_impact_evaluation")],
                               min(args.papers, len(facts)))

        async def by_paper(doc_key, f):
            effects = "; ".join(f"{e.get('outcome_label')} ({e.get('outcome')})" for e in f.get("headline_effects") or [])
            data = _parse_json(await _chat(client, DEFAULT_MODEL, PAPER_PROMPT.format(
                n=args.per_paper, categories=", ".join(CATEGORIES), title=doc_key[:120],
                programme=f.get("programme"), summary=effects or "see programme")))
            return [{"source": "paper", "anchor": doc_key, "category": str(q.get("category", "")),
                     "question": str(q.get("question", ""))} for q in data.get("questions") or [] if q.get("question")]

        groups = await asyncio.gather(*[by_category(c, v) for c, v in CATEGORIES.items()],
                                      *[by_paper(k, f) for k, f in papers])
    for g in groups:
        out.extend(g)
    seen, unique = set(), []
    for q in out:
        k = q["question"].strip().lower()
        if k and k not in seen:
            seen.add(k)
            unique.append({**q, "id": q.get("id") or f"q{len(unique) + 1:03d}"})
    (d / "questions.json").write_text(json.dumps(unique, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(unique)} questions:", dict(Counter(q["category"] for q in unique)))


# ---------------------------------------------------------------- 3. run

async def cmd_run(args) -> None:
    from src.agents.study_synthesis import PASSAGES_PER_STUDY, StudySynthesisPipeline

    d = out_dir(args.project_id)
    questions = json.loads((d / "questions.json").read_text(encoding="utf-8"))
    log = d / "runs.jsonl"
    done = {json.loads(line)["id"] for line in log.read_text(encoding="utf-8").splitlines()} if log.exists() else set()
    todo = [q for q in questions if q["id"] not in done][: args.limit or None]
    print(f"{len(todo)} questions to run ({len(done)} done)")
    sem = asyncio.Semaphore(args.concurrency)
    facts_cache: Dict[str, Any] = {}

    async def one(q):
        async with sem:
            t0 = time.time()
            pipe = StudySynthesisPipeline(args.project_id)
            try:
                groups, timing = await pipe.candidate_groups(q["question"])
                readings = await pipe.read_groups(q["question"], groups)
                if "facts" not in facts_cache:
                    facts_cache["facts"] = await pipe._load_facts()
                pipe._facts = facts_cache["facts"]
                result = await pipe.answer(q["question"], readings)
            except Exception as e:
                print(f"  ✗ {q['id']}: {type(e).__name__}: {str(e)[:120]}", flush=True)
                return
            cited = {c["study_id"] for c in result.citations}
            record = {
                **q, "seconds": round(time.time() - t0, 1), "timing": timing,
                "shown": [{"doc_key": sid, "passages": [{"node_id": r.node_id, "page": r.metadata.get("page_start"),
                                                         "score": round(r.score, 4), "text": r.text}
                                                        for r in rows[:PASSAGES_PER_STUDY]]}
                          for sid, rows in groups],
                "readings": [{"doc_key": r.study_id, "relevant": r.relevant, "quote": r.quote, "page": r.page,
                              "direction": r.direction, "cited": r.study_id in cited, "error": r.error}
                             for r in readings],
                "answer": result.answer,
            }
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"  {q['id']} {q['category']:14} read {len(readings):3} relevant "
                  f"{sum(r.relevant for r in readings):3} cited {len(cited):3} ({time.time() - t0:.0f}s)", flush=True)

    await asyncio.gather(*(one(q) for q in todo))


# ---------------------------------------------------------------- 4. analyse

class DocMap:
    """Word stream of one document with the paragraph of every word, to locate passages and quotes."""

    def __init__(self, units: List[Dict[str, Any]], labels: List[str]):
        self.units, self.labels = units, labels
        self.words: List[str] = []
        self.owner: List[int] = []
        for k, u in enumerate(units):
            for w in u["text"].split():
                self.words.append(w)
                self.owner.append(k)
        self.grams: Dict[tuple, List[int]] = defaultdict(list)
        for i in range(len(self.words) - 5):
            self.grams[tuple(self.words[i:i + 6])].append(i)
        self.norm_units = [_norm(u["text"]) for u in units]

    def passage_units(self, text: str) -> Counter:
        """Words of the passage by paragraph index."""
        ws = text.split()
        for start in self.grams.get(tuple(ws[:6]), []):
            return Counter(self.owner[start:start + len(ws)])
        for off in range(0, max(1, len(ws) - 6), 25):  # the start may differ (other item types)
            for start in self.grams.get(tuple(ws[off:off + 6]), []):
                return Counter(self.owner[max(0, start - off):start - off + len(ws)])
        return Counter()

    def quote_unit(self, quote: str, candidates: List[int]) -> int:
        q = _norm(quote)
        if len(q) < 8:
            return -1
        for k in candidates + list(range(len(self.units))):
            if q in self.norm_units[k]:
                return k
        head = q[:30]
        for k in candidates:
            if head in self.norm_units[k]:
                return k
        return -1


def cmd_analyse(args) -> None:
    d = out_dir(args.project_id)
    runs = [json.loads(x) for x in (d / "runs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    maps: Dict[str, DocMap] = {}
    stored = Counter()
    for f in (d / "labels").glob("*.json"):
        lab = json.loads(f.read_text(encoding="utf-8"))
        content = load_content(args.project_id, lab["doc_key"], d / "content")
        units = units_from_content(content)
        if len(units) != len(lab["labels"]):
            continue
        maps[lab["doc_key"]] = DocMap(units, lab["labels"])
        for u, l in zip(units, lab["labels"]):
            stored[l] += len(u["text"].split())

    shown_words, shown_passages, used_passages = Counter(), Counter(), Counter()
    quote_label, cited_label = Counter(), Counter()
    used_units: Dict[str, set] = defaultdict(set)
    by_cat: Dict[str, Counter] = defaultdict(Counter)
    unmapped = 0
    for run in runs:
        readings = {r["doc_key"]: r for r in run["readings"]}
        for group in run["shown"]:
            m = maps.get(group["doc_key"])
            reading = readings.get(group["doc_key"], {})
            if m is None:
                unmapped += len(group["passages"])
                continue
            p_units = []
            for p in group["passages"]:
                comp = m.passage_units(p["text"])
                if not comp:
                    unmapped += 1
                    p_units.append(None)
                    continue
                for k, n in comp.items():
                    shown_words[m.labels[k]] += n
                dominant = m.labels[comp.most_common(1)[0][0]]
                shown_passages[dominant] += 1
                p_units.append(comp)
            if reading.get("relevant") and reading.get("quote"):
                cands = [k for c in p_units if c for k in c]
                k = m.quote_unit(reading["quote"], cands)
                label = m.labels[k] if k >= 0 else "quote_not_found"
                quote_label[label] += 1
                by_cat[run["category"]][label] += 1
                if reading.get("cited"):
                    cited_label[label] += 1
                if k >= 0:
                    used_units[group["doc_key"]].add(k)
                    for c in p_units:
                        if c and k in c:
                            used_passages[m.labels[c.most_common(1)[0][0]]] += 1
                            break

    def pct(c: Counter, k: str) -> str:
        t = sum(c.values())
        return f"{100 * c[k] / t:.0f}%" if t else "-"

    order = ["abstract", "own_finding", "method", "intervention", "setting", "cost", "limitation",
             "other_study", "background", "boilerplate", "unlabelled", "quote_not_found"]
    lines = [f"# Usage study: what goes into an answer ({len(runs)} questions, {len(maps)} papers)", "",
             "| Role | Stored text | Shown to the reader | Passages shown | Used when shown | Supporting quotes | Cited in answers |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for k in order:
        if not (stored[k] or shown_words[k] or quote_label[k]):
            continue
        rate = f"{100 * used_passages[k] / shown_passages[k]:.0f}%" if shown_passages[k] else "-"
        lines.append(f"| {k} | {pct(stored, k)} | {pct(shown_words, k)} | {shown_passages[k]} | {rate} | "
                     f"{quote_label[k]} ({pct(quote_label, k)}) | {cited_label[k]} ({pct(cited_label, k)}) |")
    total_units = sum(len(m.units) for m in maps.values())
    lines += ["", f"Paragraphs ever used as a supporting quote: {sum(len(v) for v in used_units.values())} of "
              f"{total_units} ({100 * sum(len(v) for v in used_units.values()) / max(1, total_units):.1f}%).",
              f"Passages that could not be mapped to a paragraph: {unmapped}.", "",
              "## Supporting quotes by question category", "",
              "| Category | Quotes | " + " | ".join(order[:10]) + " |", "| --- | --- |" + " --- |" * 10]
    for cat, c in sorted(by_cat.items()):
        t = sum(c.values())
        lines.append(f"| {cat} | {t} | " + " | ".join(f"{100 * c[k] / t:.0f}%" if c[k] else "" for k in order[:10]) + " |")
    report = "\n".join(lines)
    (d / "report.md").write_text(report, encoding="utf-8")
    print(report)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["labels", "questions", "run", "analyse"])
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--per-category", type=int, default=10)
    ap.add_argument("--papers", type=int, default=40)
    ap.add_argument("--per-paper", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=3)
    args = ap.parse_args()
    if args.step == "analyse":
        cmd_analyse(args)
    else:
        asyncio.run({"labels": cmd_labels, "questions": cmd_questions, "run": cmd_run}[args.step](args))


if __name__ == "__main__":
    main()
