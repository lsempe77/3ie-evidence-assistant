"""
Read every relevant study, then synthesise (prototype, November 2026).

The production agent writes answers from about ten studies' passages, so it cannot
see the pattern across a collection, reports facts study by study, and never says
when the evidence is thin. On the graduation-review benchmark it supported about
0.3 of the review's conclusions. This pipeline:

1. retrieves a wide pool for the question as asked (no LLM query rewriting) and
   reranks it;
2. sends every study with a passage above a low floor to a small "reader" model, in
   parallel, which says whether the study answers the question and what it found,
   with a quote and page;
3. has the answer model synthesise from all relevant findings: counts by direction,
   qualified magnitudes, explicit gaps, the question's language, a citation for
   every claim.

Model calls go straight to the OpenRouter chat API.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

import httpx

from src.retrieval.hybrid_retriever import HybridRetriever, RetrievalResult
from src.retrieval.reranker import CohereReranker
from src.agents.evidence_summary import summary_block
from src.retrieval.study_cards import embed_query
from src.vectorstore.chunk_store import ChunkStore

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_READER_MODEL = "anthropic/claude-haiku-5.5"
DEFAULT_ANSWER_MODEL = "anthropic/claude-sonnet-5.5"
POOL_SIZE = 300          # passage pool; 150 reached only ~28 of the 86 included studies
STUDY_CANDIDATES = 60    # studies ranked by their study card (src/retrieval/study_cards.py)
STUDY_FLOOR = 0.1        # lowest rerank score that still sends a study to the reader
MAX_STUDIES_READ = 80
PASSAGES_PER_STUDY = 4
READER_CONCURRENCY = 32   # 60+ studies per broad question since study cards (N1)

READER_PROMPT = """You are screening one study for a question about development evidence.

QUESTION: {question}

STUDY: {label}
Design: {design}. Countries: {countries}.

PASSAGES FROM THE STUDY (with page numbers):
{passages}

ESTIMATES EXTRACTED FROM THIS STUDY'S TABLES (closest to the question; id | outcome | arm |
subgroup | estimate (SE), stars | N | table, page):
{estimates}

Using ONLY these passages, return JSON:
{{"relevant": true or false,           // does the study report evidence that answers the question?
  "finding": "<one or two sentences: what this study found on the question, with direction and size as reported (units, %, SD), and the time point if given; empty if not relevant>",
  "direction": "positive" | "negative" | "null" | "mixed" | "not_applicable",
  "quote": "<a short exact quote from the passages that supports the finding>",
  "page": <page number of the quote, or null>,
  "programme": "<short name of the programme evaluated, with its country, e.g. 'BRAC TUP, Bangladesh' or 'Haku Wiñay, Peru'. At most eight words, no explanation. Empty if the passages do not say>",
  "estimate_ids": ["<ids of up to four extracted estimates above that directly answer the question, e.g. 'E2'; [] if none>"]}}
If extracted estimates answer the question, use them in the finding with their numbers, and prefer
them to vaguer statements in the passages. Never use an estimate that is not listed or quoted.
Do not use outside knowledge. If the passages only mention the topic without results, relevant is false.
If the passages are garbled or unreadable (for example a broken table), relevant is false: never report
on how the text looks."""

ANSWER_PROMPT = """You are an evidence synthesis assistant for development research. Answer the
question from the study findings below, which were read from a collection of studies.

QUESTION: {question}

STUDY FINDINGS ({n_relevant} relevant of {n_read} studies read):
{findings}

FIGURES COMPUTED ACROSS THE WHOLE COLLECTION (from each study's own reported figures, one figure
per programme, worked out in code; bracketed numbers are studies above):
{computed}

Write the answer:
- In the same language as the question.
- Lead with the overall pattern across the studies, then the important exceptions. Say how
  many studies point each way (e.g. "12 of 15 studies found…") and their designs where it
  matters (RCTs vs quasi-experimental).
- Where studies list estimates on the same outcome, compare them: how many are positive and
  statistically significant, how sizes compare (only within the same units), and whether
  subgroups such as women or the poorest differ. Say this is a comparison of reported
  estimates, not a meta-analysis, and never average numbers across studies.
- When the question is about typical costs, benefit-cost ratios, how widely the approach has
  been evaluated, or how gains differ between kinds of programme (such as those that put women
  first), use the computed figures above and give their medians, ranges and counts. Say they
  are computed from the figures the studies report, with currencies, price years, outcome
  definitions and horizons that differ, and that this is not a meta-analysis. Ignore the
  computed figures when they do not bear on the question.
- Count programmes as well as studies. Several studies often evaluate the same programme
  (for example many papers on BRAC's TUP in Bangladesh, also called CFPR or CFPR-TUP). Treat
  name variants of one programme as one programme. Say "N studies of M programmes" and do not
  present several papers on one programme as independent confirmations.
- Describe sizes as the studies report them and qualify them honestly ("modest", "small",
  "large"). Do not call an effect large, significant or sustained unless the findings say so.
- Distinguish short-term from long-term results when the findings give time points.
- If the findings do not answer the question, or only one or two studies do, say plainly
  that the evidence in this collection is limited or absent, and do not fill the gap with
  general knowledge.
- Cite every factual sentence with the study numbers in square brackets, e.g. [3] or [3, 7].
  Cite only studies listed above. When a sentence gives a count ("19 of 29 studies"), cite at
  most five representative studies, not all of them; the full list is shown beside the answer.
- Use short headings only if the answer is long. Aim for 200 to 450 words. No preamble."""


FOLLOWUP_PROMPT = """A researcher asked a question of a collection of development studies and got
the answer below. Suggest three follow-up questions they might ask next.

QUESTION: {question}

ANSWER:
{answer}

RELEVANT STUDIES (title | design | countries | programme):
{covered}

Rules:
- Each question must be answerable from studies like these: go deeper on an outcome,
  subgroup (women, youth, poorest), country, programme, time horizon, cost, or a gap the
  answer named. Do not suggest topics the studies do not cover.
- Write in the same language as the question. At most 15 words each. No numbering.
Return JSON: {{"questions": ["...", "...", "..."]}}"""


@dataclass
class StudyReading:
    number: int
    study_id: str
    label: str
    design: str
    countries: str
    relevant: bool
    finding: str
    direction: str
    quote: str
    page: Optional[int]
    best_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)  # title, authors, year, source, ...
    passage: str = ""            # best passage, for highlighting in the PDF viewer
    passage_page: Optional[int] = None
    programme: str = ""          # programme or intervention evaluated, as the reader names it
    error: str = ""              # set when the reader call or its JSON failed
    estimates: List[Dict[str, Any]] = field(default_factory=list)  # extracted estimates the reader used


@dataclass
class SynthesisResult:
    answer: str
    citations: List[Dict[str, Any]]
    readings: List[StudyReading] = field(default_factory=list)
    model_used: str = ""
    timings: Dict[str, float] = field(default_factory=dict)


async def _chat(client: httpx.AsyncClient, model: str, prompt: str, max_tokens: int,
                json_mode: bool = False, effort: str = "low") -> str:
    # Current models reason before answering, and reasoning tokens count against
    # max_tokens: with a 400-token cap the reader often returned empty or cut-off
    # JSON. Keep reasoning short and leave room for the answer.
    body: Dict[str, Any] = {"model": model, "temperature": 0, "max_tokens": max_tokens,
                            "reasoning": {"effort": effort, "exclude": True},
                            "messages": [{"role": "user", "content": prompt}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    for attempt in range(3):
        try:
            r = await client.post(OPENROUTER_URL, json=body)
            if r.status_code >= 500 or r.status_code == 429:
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError):
            if attempt == 2:
                raise
            await asyncio.sleep(2 * (attempt + 1))
    return ""


async def _chat_stream(client: httpx.AsyncClient, model: str, prompt: str, max_tokens: int,
                       effort: str = "low") -> AsyncIterator[str]:
    """Yield the answer text in pieces as the model writes it (OpenRouter SSE)."""
    body: Dict[str, Any] = {"model": model, "temperature": 0, "max_tokens": max_tokens, "stream": True,
                            "reasoning": {"effort": effort, "exclude": True},
                            "messages": [{"role": "user", "content": prompt}]}
    async with client.stream("POST", OPENROUTER_URL, json=body) as r:
        r.raise_for_status()
        async for line in r.aiter_lines():
            if not line.startswith("data: "):
                continue  # keep-alive comments and blank lines
            data = line[6:].strip()
            if data == "[DONE]":
                return
            try:
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
            except (ValueError, KeyError, IndexError):
                continue
            if delta:
                yield delta


def significance(e: Dict[str, Any]) -> Optional[bool]:
    """
    Significant at 5%? In order of reliability: the p-value, |estimate / SE| > 1.96, then
    stars (two or more; one star is often only 10%). None when nothing says.
    """
    if e.get("p_value") is not None:
        return e["p_value"] < 0.05
    if e.get("standard_error") and e.get("effect_size") is not None:
        return abs(e["effect_size"] / e["standard_error"]) > 1.96
    p_text = str(e.get("p_text") or "").strip()
    stars = p_text.count("*") if p_text and set(p_text) == {"*"} else 0
    if stars >= 2:
        return True
    return None


def _estimate_text(e: Dict[str, Any]) -> str:
    who = "; ".join(x for x in (e.get("treatment_arm"), e.get("subgroup")) if x)
    value = e.get("literal_text") or e.get("effect_size")
    sig = {True: "significant at 5%", False: "not significant", None: "significance not reported"}[significance(e)]
    where = ", ".join(x for x in (e.get("table_number"), f"p. {e['page']}" if e.get("page") else "") if x)
    n = f", N={e['sample_size']}" if e.get("sample_size") else ""
    return f"{e.get('outcome_name')}{f' ({who})' if who else ''}: {value} ({sig}{n}; {where})"


def _estimate_lines(estimates: List[Dict[str, Any]]) -> str:
    if not estimates:
        return "(none extracted)"
    return "\n".join(f"E{i + 1} | {_estimate_text(e)}" for i, e in enumerate(estimates))


def _chosen(estimates: List[Dict[str, Any]], ids: Any) -> List[Dict[str, Any]]:
    out = []
    for raw in ids or []:
        m = re.fullmatch(r"E?(\d+)", str(raw).strip(), re.I)
        if m and 1 <= int(m.group(1)) <= len(estimates):
            e = estimates[int(m.group(1)) - 1]
            if e not in out:
                out.append(e)
    return out[:4]


def _parse_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0) if m else text)


def _label(meta: Dict[str, Any]) -> str:
    authors = meta.get("authors") or []
    if isinstance(authors, list):
        first = str(authors[0]).split(",")[0].split()[-1] if authors else "Unknown"
        lead = f"{first} et al." if len(authors) > 2 else " and ".join(
            str(a).split(",")[0].split()[-1] for a in authors) if authors else "Unknown"
    else:
        lead = str(authors).split(",")[0] or "Unknown"
    return f"{lead} ({meta.get('year') or 'n.d.'}). {meta.get('title') or 'Untitled'}"


def _group_by_study(pool: List[RetrievalResult]) -> Dict[str, List[RetrievalResult]]:
    groups: Dict[str, List[RetrievalResult]] = {}
    for r in pool:  # pool is sorted best first
        groups.setdefault(r.study_id or r.node_id, []).append(r)
    return groups


class StudySynthesisPipeline:
    def __init__(self, project_id: str, reader_model: str = DEFAULT_READER_MODEL,
                 answer_model: str = DEFAULT_ANSWER_MODEL):
        self.project_id = project_id
        self.reader_model = reader_model
        self.answer_model = answer_model
        self.store = ChunkStore()
        self._query_embeddings: Dict[str, List[float]] = {}
        # Estimate lookups started as soon as the candidate studies are known, so they
        # overlap the passage fetch and rerank instead of delaying the reader (about 9 s).
        self._estimate_tasks: Dict[str, "asyncio.Task[Dict[str, List[Dict[str, Any]]]]"] = {}
        self.use_estimates = True
        # Study facts for the whole collection feed computed summaries in the answer (N6 step 3)
        self.use_facts = True
        self._facts: Dict[str, Dict[str, Any]] = {}
        self._facts_task: Optional["asyncio.Task[Dict[str, Dict[str, Any]]]"] = None
        self.reranker = CohereReranker()
        self.use_study_cards = True
        self._headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}

    async def _candidates(self, question: str) -> tuple[List[RetrievalResult], Dict[str, Any]]:
        """
        Passages for every candidate study: the passage pool for the question, plus the
        best passages of studies ranked highly by their study card but missed by the pool.
        """
        if self.use_facts and self._facts_task is None and not self._facts:
            self._facts_task = asyncio.create_task(self._load_facts())
        q_emb = await asyncio.to_thread(embed_query, question)
        self._query_embeddings[question] = q_emb
        pool_task = asyncio.to_thread(
            self.store.hybrid_search, self.project_id, question, q_emb,
            match_count=POOL_SIZE, candidate_count=POOL_SIZE)
        if self.use_study_cards:
            cards_task = asyncio.to_thread(self.store.search_study_cards, self.project_id, question, q_emb,
                                           STUDY_CANDIDATES)
            pool_rows, card_rows = await asyncio.gather(pool_task, cards_task)
        else:
            pool_rows, card_rows = await pool_task, []
        pool = [HybridRetriever._row_to_result(r) for r in pool_rows]
        if self.use_estimates:
            keys = list(dict.fromkeys([r.study_id for r in pool] + [c["doc_key"] for c in card_rows]))
            self._estimate_tasks[question] = asyncio.create_task(self._lookup_estimates(q_emb, keys))

        in_pool: Dict[str, int] = {}
        for r in pool:
            in_pool[r.study_id] = in_pool.get(r.study_id, 0) + 1
        missing = [c["doc_key"] for c in card_rows if in_pool.get(c["doc_key"], 0) < 2]
        extra_rows = await asyncio.to_thread(
            self.store.passages_for_studies, self.project_id, q_emb, missing, PASSAGES_PER_STUDY)
        extra = [HybridRetriever._row_to_result(r) for r in extra_rows]

        seen, merged = set(), []
        for r in pool + extra:
            if r.node_id not in seen:
                seen.add(r.node_id)
                merged.append(r)
        # Keep at most PASSAGES_PER_STUDY passages per study for reranking
        per_study: Dict[str, int] = {}
        kept = []
        for r in merged:
            if per_study.get(r.study_id, 0) < PASSAGES_PER_STUDY:
                per_study[r.study_id] = per_study.get(r.study_id, 0) + 1
                kept.append(r)
        info = {"pool_studies": len(in_pool), "card_studies": len(card_rows),
                "studies_added_by_cards": len({r.study_id for r in extra} - set(in_pool)),
                "passages_reranked": len(kept)}
        return kept, info

    async def read_studies(
        self, question: str,
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> tuple[List[StudyReading], Dict[str, float]]:
        """Find and read candidate studies. on_event receives progress events as they happen."""
        groups, timing = await self.candidate_groups(question)
        if on_event:
            await on_event({"type": "candidates", "total": len(groups)})
        t2 = time.time()
        readings = await self.read_groups(question, groups, on_event)
        timing.update(read_s=round(time.time() - t2, 1), studies_read=len(readings))
        if self._facts_task is not None:
            self._facts = await self._facts_task
            self._facts_task = None
        return readings, timing

    async def _load_facts(self) -> Dict[str, Dict[str, Any]]:
        try:
            return await asyncio.to_thread(self.store.study_facts, self.project_id)
        except Exception:
            return {}  # facts are an addition: never fail the answer over them

    async def candidate_groups(self, question: str) -> tuple[List[tuple], Dict[str, Any]]:
        """Candidate studies with their passages, reranked, best first: [(study_id, rows)]."""
        t0 = time.time()
        candidates, info = await self._candidates(question)
        t1 = time.time()
        pool = await self.reranker.rerank(query=question, results=candidates, top_n=len(candidates))
        t2 = time.time()
        groups = [(sid, rows) for sid, rows in _group_by_study(pool).items() if rows[0].score >= STUDY_FLOOR]
        return groups[:MAX_STUDIES_READ], {"retrieve_s": round(t1 - t0, 1), "rerank_s": round(t2 - t1, 1), **info}

    async def _lookup_estimates(self, q_emb: List[float], doc_keys: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        if not doc_keys:
            return {}
        try:
            rows = await asyncio.to_thread(self.store.estimates_for_studies, self.project_id, q_emb, doc_keys)
        except Exception:
            return {}  # estimates are an addition: never fail the answer over them
        by_doc: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            by_doc.setdefault(r["doc_key"], []).append(r)
        return by_doc

    async def _estimates_for(self, question: str, doc_keys: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """Each study's extracted estimates closest to the question; {} if none or switched off."""
        if not self.use_estimates or not doc_keys:
            return {}
        task = self._estimate_tasks.pop(question, None)
        if task is not None:
            # Started in _candidates for every candidate study, a superset of those read
            return await task
        try:
            q_emb = self._query_embeddings.get(question) or await asyncio.to_thread(embed_query, question)
        except Exception:
            return {}
        return await self._lookup_estimates(q_emb, doc_keys)

    async def read_groups(
        self, question: str, groups: List[tuple],
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        model: Optional[str] = None,
    ) -> List[StudyReading]:
        """Read each candidate study with the reader model (or `model`), in parallel."""
        reader_model = model or self.reader_model
        estimates_by_doc = await self._estimates_for(question, [sid for sid, _ in groups])
        sem = asyncio.Semaphore(READER_CONCURRENCY)
        async with httpx.AsyncClient(timeout=120, headers=self._headers) as client:
            async def read(number: int, sid: str, rows: List[RetrievalResult]) -> StudyReading:
                meta = rows[0].metadata
                countries = ", ".join(meta.get("countries") or []) or "not stated"
                design = meta.get("study_design") or "unknown"
                passages = "\n\n".join(
                    f"[page {r.metadata.get('page_start') or '?'}] {r.text.strip()}" for r in rows[:PASSAGES_PER_STUDY]
                )
                listed = estimates_by_doc.get(sid, [])
                prompt = READER_PROMPT.format(question=question, label=_label(meta), design=design,
                                              estimates=_estimate_lines(listed),
                                              countries=countries, passages=passages)
                async with sem:
                    # One retry: a failed or malformed reply used to drop the study silently
                    # (11 of ~800 Haiku readings in the reader comparison, 10 Nov 2026).
                    for attempt in range(2):
                        try:
                            data = _parse_json(await _chat(client, reader_model, prompt,
                                                           max_tokens=2000, json_mode=True))
                            break
                        except Exception as e:
                            data = {"relevant": False, "finding": "", "direction": "not_applicable",
                                    "quote": "", "page": None, "error": str(e)[:200]}
                return StudyReading(
                    number=number, study_id=sid, label=_label(meta), design=design, countries=countries,
                    relevant=bool(data.get("relevant")), finding=str(data.get("finding") or ""),
                    direction=str(data.get("direction") or ""), quote=str(data.get("quote") or ""),
                    page=data.get("page") if isinstance(data.get("page"), int) else None,
                    best_score=rows[0].score,
                    metadata=dict(meta),
                    passage=rows[0].text,
                    passage_page=rows[0].metadata.get("page_start"),
                    programme=str(data.get("programme") or ""),
                    estimates=_chosen(listed, data.get("estimate_ids")),
                    error=str(data.get("error") or ""),
                )

            tasks = [asyncio.create_task(read(i + 1, sid, rows)) for i, (sid, rows) in enumerate(groups)]
            readings = []
            for done, task in enumerate(asyncio.as_completed(tasks), start=1):
                reading = await task
                readings.append(reading)
                if on_event:
                    await on_event({"type": "study", "done": done, "total": len(groups), "reading": reading})
            readings.sort(key=lambda r: r.number)  # back to rerank order, which numbers the answer
        return readings

    def _answer_prompt(self, question: str, readings: List[StudyReading]) -> tuple[str, Dict[str, int], List[StudyReading]]:
        relevant = [r for r in readings if r.relevant and r.finding]
        # Renumber the relevant studies 1..n so citations are compact
        numbered = {r.study_id: i + 1 for i, r in enumerate(relevant)}
        findings = "\n".join(
            f"[{numbered[r.study_id]}] {r.label} | design: {r.design} | countries: {r.countries}"
            f" | programme: {r.programme or 'not stated'}\n"
            f"    finding ({r.direction}): {r.finding}"
            + ("".join(f"\n    estimate: {_estimate_text(e)}" for e in r.estimates) if r.estimates else "")
            for r in relevant
        ) or "(none of the studies read reports evidence on this question)"
        computed = summary_block(self._facts, numbered) if self.use_facts and self._facts else             "(no study facts for this collection)"
        prompt = ANSWER_PROMPT.format(question=question, n_relevant=len(relevant),
                                      n_read=len(readings), findings=findings, computed=computed)
        return prompt, numbered, relevant

    def _result(self, text: str, numbered: Dict[str, int], relevant: List[StudyReading],
                readings: List[StudyReading], seconds: float) -> SynthesisResult:
        cited_numbers = {int(n) for grp in re.findall(r"\[([\d,\s]+)\]", text) for n in re.findall(r"\d+", grp)}
        citations = [
            {"id": numbered[r.study_id], "study_id": r.study_id, "title": r.label, "quote": r.quote,
             "page": r.page, "design": r.design}
            for r in relevant if numbered[r.study_id] in cited_numbers
        ]
        return SynthesisResult(answer=text, citations=citations, readings=readings,
                               model_used=self.answer_model, timings={"answer_s": round(seconds, 1)})

    async def answer(self, question: str, readings: List[StudyReading]) -> SynthesisResult:
        prompt, numbered, relevant = self._answer_prompt(question, readings)
        t0 = time.time()
        async with httpx.AsyncClient(timeout=180, headers=self._headers) as client:
            text = await _chat(client, self.answer_model, prompt, max_tokens=6000, effort="medium")
        return self._result(text, numbered, relevant, readings, time.time() - t0)

    async def suggest_followups(self, question: str, answer: str, readings: List[StudyReading],
                                model: Optional[str] = None) -> List[str]:
        """
        Three follow-up questions a reader might ask next (roadmap N4), grounded in what the
        relevant studies cover. One cheap call made after the answer, so it adds no wait.
        """
        relevant = [r for r in readings if r.relevant and r.finding][:30]
        if not relevant:
            return []
        covered = "\n".join(f"- {r.label[:110]} | {r.design} | {r.countries} | {r.programme}" for r in relevant)
        prompt = FOLLOWUP_PROMPT.format(question=question, answer=answer[:2500], covered=covered)
        try:
            async with httpx.AsyncClient(timeout=60, headers=self._headers) as client:
                data = _parse_json(await _chat(client, model or self.reader_model, prompt,
                                               max_tokens=1200, json_mode=True))
        except Exception:
            return []
        questions = [str(q).strip() for q in (data.get("questions") or []) if str(q).strip()]
        return [q for q in questions if q.lower() != question.strip().lower()][:3]

    async def run_events(self, question: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Run the whole pipeline as a stream of events, for the live progress view:
        {"type": "stage"}, {"type": "candidates"}, one {"type": "study"} per study read,
        {"type": "delta"} pieces of the answer, then {"type": "result", "result": ...}.
        """
        queue: asyncio.Queue = asyncio.Queue()

        async def on_event(event: Dict[str, Any]) -> None:
            await queue.put(event)

        yield {"type": "stage", "stage": "searching"}
        reading_task = asyncio.create_task(self.read_studies(question, on_event))
        while not (reading_task.done() and queue.empty()):
            try:
                yield await asyncio.wait_for(queue.get(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
        readings, read_timing = reading_task.result()

        yield {"type": "stage", "stage": "writing"}
        prompt, numbered, relevant = self._answer_prompt(question, readings)
        t0 = time.time()
        parts: List[str] = []
        async with httpx.AsyncClient(timeout=180, headers=self._headers) as client:
            async for piece in _chat_stream(client, self.answer_model, prompt, max_tokens=6000, effort="medium"):
                parts.append(piece)
                yield {"type": "delta", "text": piece}
        result = self._result("".join(parts), numbered, relevant, readings, time.time() - t0)
        result.timings = {**read_timing, **result.timings}
        yield {"type": "result", "result": result}

    async def run(self, question: str) -> SynthesisResult:
        """Read, then answer. Timings for both steps are in result.timings."""
        readings, read_timing = await self.read_studies(question)
        result = await self.answer(question, readings)
        result.timings = {**read_timing, **result.timings}
        return result


def relevant_in_answer_order(readings: List[StudyReading]) -> List[StudyReading]:
    """Relevant readings in the order they were numbered for the answer ([1], [2], ...)."""
    return [r for r in readings if r.relevant and r.finding]
