"""
Metadata Resolution Module

Handles metadata enrichment via CrossRef, OpenAlex, and LLM extraction.
"""

import asyncio
import json
import os
import re
from typing import Optional, Dict, Any

import httpx


# ============================================================================
# Metadata Resolution
# ============================================================================

def resolve_metadata(
    content: str,
    title: Optional[str] = None,
    authors: Optional[list] = None,
    year: Optional[int] = None,
    pdf_filename: Optional[str] = None,
) -> dict:
    """
    Resolve rich metadata using CrossRef, OpenAlex, and LLM.
    
    Flow:
    1. Collect DOIs from the first pages. Try each in Crossref and accept the first
       whose title appears on those pages (a paper's first pages also cite other
       papers, and the first DOI found is often one of theirs).
    2. No accepted DOI: search OpenAlex by title and accept a hit only on the same check.
    3. One LLM call reads the first pages for the study countries (where the
       intervention ran or the data were collected), sectors and intervention, and
       for title, authors and year when no record was accepted.

    Countries never come from OpenAlex author affiliations: those say where the
    authors work, and put a Bangladesh study down as "US". They are kept separately
    as `author_countries`.
    """
    import asyncio
    import httpx
    
    # Default metadata
    metadata = {
        "title": title or "Unknown Title",
        "authors": authors or [],
        "year": year,
        "doi": None,
        "item_type": None,
        "journal": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "publisher": None,
        "abstract": None,
        "cited_by_count": None,
        "is_open_access": False,
        "countries": [],
        "author_countries": [],
        "sectors": [],
        "study_type": None,
        "intervention_type": None,
        "sdgs": [],
        "keywords": [],
        "metadata_source": "extraction",
        "metadata_confidence": 0.3,
        "needs_review": True,
        "pdf_name": pdf_filename,
    }
    
    first_pages = (content or "")[:FIRST_PAGES_CHARS]
    record_accepted = False

    # The LLM reads the paper's own title page first. A looked-up record must match
    # that title, which stops generic hits ("Journal of Development Economics",
    # "How to Make Your Research & Publications Visible") that share common words
    # with the first pages.
    llm_result = {}
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            llm_result = asyncio.run(llm_extract_paper_fields(first_pages, api_key=openrouter_key)) or {}
        except Exception as e:
            print(f"  LLM enrichment error: {e}")
    own_title = str(llm_result.get("title") or "").strip()
    search_title = own_title or title

    def is_this_paper(candidate_title: str) -> bool:
        if own_title:
            return titles_agree(candidate_title, own_title)
        return title_matches_document(candidate_title, first_pages)

    async def lookup_apis():
        headers = {"User-Agent": "3ie-Evidence-Assistant/2.0"}
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            # Step 1: DOIs found on the first pages, checked against those pages
            for candidate in extract_dois_from_text(first_pages)[:MAX_DOI_CANDIDATES]:
                try:
                    resp = await client.get(f"https://api.crossref.org/works/{candidate}")
                except Exception as e:
                    print(f"  CrossRef error: {e}")
                    continue
                if resp.status_code != 200:
                    continue
                crossref = resp.json().get("message", {})
                cr_title = (crossref.get("title") or [""])[0]
                if not is_this_paper(cr_title):
                    print(f"  Rejected DOI {candidate}: title does not match the paper ({cr_title[:60]!r})")
                    continue
                print(f"  CrossRef: accepted DOI {candidate}")
                openalex = None
                try:
                    resp = await client.get(f"https://api.openalex.org/works/https://doi.org/{candidate}")
                    if resp.status_code == 200:
                        openalex = resp.json()
                except Exception as e:
                    print(f"  OpenAlex error: {e}")
                return crossref, openalex

            # Step 2: title search, same check
            if search_title and len(search_title) > 10:
                try:
                    resp = await client.get(
                        "https://api.openalex.org/works",
                        params={"search": search_title[:200].replace('"', ""), "per_page": 3},
                    )
                    if resp.status_code == 200:
                        for hit in resp.json().get("results", []):
                            if is_this_paper(hit.get("title") or ""):
                                print("  OpenAlex: accepted title search hit")
                                return None, hit
                        print("  OpenAlex: no title search hit matched the paper")
                except Exception as e:
                    print(f"  OpenAlex search error: {e}")
            return None, None

    try:
        crossref_data, openalex_data = asyncio.run(lookup_apis())
        if crossref_data:
            metadata = _merge_crossref_data(metadata, crossref_data)
            record_accepted = True
        if openalex_data:
            metadata = _merge_openalex_data(metadata, openalex_data, is_primary=not crossref_data)
            record_accepted = True
    except Exception as e:
        print(f"  Metadata lookup error: {e}")

    # Step 3: one LLM call for study countries and domain fields, and for title,
    # authors and year when no bibliographic record was accepted
    if llm_result:
        try:
            metadata["countries"] = _clean_list(llm_result.get("countries"))
            if llm_result.get("sectors"):
                metadata["sectors"] = _clean_list(llm_result["sectors"])
            if llm_result.get("study_type"):
                metadata["study_type"] = llm_result["study_type"]
            if llm_result.get("intervention_type"):
                metadata["intervention_type"] = llm_result["intervention_type"]
            if not record_accepted:
                if own_title:
                    metadata["title"] = own_title
                if llm_result.get("authors"):
                    metadata["authors"] = _clean_list(llm_result["authors"])
                year_val = llm_result.get("year")
                if isinstance(year_val, int) or (isinstance(year_val, str) and year_val.isdigit()):
                    metadata["year"] = int(year_val)
                metadata["metadata_source"] = "llm"
                metadata["metadata_confidence"] = 0.5
                metadata["needs_review"] = True
            print(f"  LLM fields: countries={metadata['countries']}, sectors={metadata['sectors']}")
        except Exception as e:
            print(f"  LLM enrichment error: {e}")

    return metadata


def _merge_crossref_data(metadata: dict, crossref_data: dict) -> dict:
    """Merge CrossRef API response into metadata."""
    metadata["title"] = crossref_data.get("title", [metadata["title"]])[0] if crossref_data.get("title") else metadata["title"]
    
    # Extract authors
    cr_authors = crossref_data.get("author", [])
    if cr_authors:
        metadata["authors"] = [
            f"{a.get('given', '')} {a.get('family', '')}".strip()
            for a in cr_authors
        ]
    
    # Extract year from published date
    published = crossref_data.get("published-print") or crossref_data.get("published-online") or {}
    date_parts = published.get("date-parts", [[]])[0]
    if date_parts:
        metadata["year"] = date_parts[0]
    
    metadata["journal"] = crossref_data.get("container-title", [None])[0] if crossref_data.get("container-title") else None
    metadata["publisher"] = crossref_data.get("publisher")
    metadata["cited_by_count"] = crossref_data.get("is-referenced-by-count")
    metadata["doi"] = crossref_data.get("DOI") or metadata["doi"]
    metadata["volume"] = crossref_data.get("volume")
    metadata["issue"] = crossref_data.get("issue")
    metadata["pages"] = crossref_data.get("page")
    
    # Map CrossRef type to our item_type
    crossref_type = crossref_data.get("type", "")
    item_type_map = {
        "journal-article": "journalArticle",
        "book-chapter": "bookSection",
        "book": "book",
        "proceedings-article": "conferencePaper",
        "report": "report",
        "report-series": "report",
        "dissertation": "thesis",
        "posted-content": "preprint",
        "dataset": "dataset",
        "monograph": "book",
        "reference-book": "book",
        "edited-book": "book",
    }
    metadata["item_type"] = item_type_map.get(crossref_type, "document")
    
    metadata["metadata_source"] = "crossref"
    metadata["metadata_confidence"] = 0.8
    metadata["needs_review"] = False
    
    return metadata


def _merge_openalex_data(metadata: dict, openalex_data: dict, is_primary: bool = False) -> dict:
    """Merge OpenAlex API response into metadata."""
    if is_primary:
        metadata["title"] = openalex_data.get("title") or metadata["title"]
        
        authorships = openalex_data.get("authorships", [])
        if authorships and not metadata["authors"]:
            metadata["authors"] = [
                a.get("author", {}).get("display_name", "")
                for a in authorships
            ]
        
        metadata["year"] = openalex_data.get("publication_year") or metadata["year"]
        
        primary_loc = openalex_data.get("primary_location", {}) or {}
        source = primary_loc.get("source", {}) or {}
        metadata["journal"] = source.get("display_name") or metadata["journal"]
        
        metadata["doi"] = openalex_data.get("doi", "").replace("https://doi.org/", "") if openalex_data.get("doi") else metadata["doi"]
        metadata["cited_by_count"] = openalex_data.get("cited_by_count") or metadata["cited_by_count"]
        
        biblio = openalex_data.get("biblio", {}) or {}
        metadata["volume"] = biblio.get("volume") or metadata.get("volume")
        metadata["issue"] = biblio.get("issue") or metadata.get("issue")
        first_page = biblio.get("first_page")
        last_page = biblio.get("last_page")
        if first_page and last_page:
            metadata["pages"] = f"{first_page}-{last_page}"
        elif first_page:
            metadata["pages"] = first_page
        
        openalex_type = openalex_data.get("type", "")
        oa_type_map = {
            "article": "journalArticle",
            "book": "book",
            "book-chapter": "bookSection",
            "dissertation": "thesis",
            "dataset": "dataset",
            "preprint": "preprint",
            "report": "report",
            "review": "journalArticle",
            "paratext": "document",
        }
        metadata["item_type"] = oa_type_map.get(openalex_type, "journalArticle")
        
        metadata["metadata_source"] = "openalex"
        metadata["metadata_confidence"] = 0.7
        metadata["needs_review"] = False
    
    # Always use OpenAlex for enrichment
    oa = openalex_data.get("open_access", {}) or {}
    metadata["is_open_access"] = oa.get("is_oa", False)
    
    sdgs = openalex_data.get("sustainable_development_goals", [])
    metadata["sdgs"] = [s.get("display_name") for s in sdgs if s.get("display_name")]
    
    concepts = openalex_data.get("concepts", [])
    metadata["keywords"] = [
        c.get("display_name") for c in concepts[:10]
        if c.get("display_name") and c.get("score", 0) > 0.3
    ]
    
    authorships = openalex_data.get("authorships", [])
    countries = set()
    for a in authorships:
        for inst in a.get("institutions", []):
            if inst.get("country_code"):
                countries.add(inst["country_code"])
    # Where the authors work, not where the study took place (see resolve_metadata)
    metadata["author_countries"] = sorted(countries)

    return metadata


# ============================================================================
# DOI Extraction
# ============================================================================

def extract_doi_from_text(text: str) -> Optional[str]:
    """Extract DOI from text using regex patterns."""
    if not text:
        return None
    
    patterns = [
        r'10\.\d{4,}/[^\s\]>)\'"]+',
        r'(?:doi\.org/|doi:)\s*(10\.\d{4,}/[^\s\]>)\'"]+)',
        r'DOI[:\s]+\[?(10\.\d{4,}/[^\s\]>)\'"]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            doi = match.group(1) if match.lastindex else match.group(0)
            doi = re.sub(r'[.,;:\'")\]]+$', '', doi)
            return doi
    
    return None


FIRST_PAGES_CHARS = 6000
MAX_DOI_CANDIDATES = 3
TITLE_MATCH_THRESHOLD = 0.75

_STOPWORDS = {
    "the", "and", "for", "from", "with", "into", "that", "this", "its", "are", "was", "were",
    "how", "what", "does", "can", "evidence", "study", "analysis", "effects", "effect", "impact",
    "impacts", "evaluation", "programme", "program", "paper", "working",
}


def _significant_words(text: str) -> list:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if len(w) >= 3 and w not in _STOPWORDS]


def title_matches_document(candidate_title: str, first_pages: str,
                           threshold: float = TITLE_MATCH_THRESHOLD) -> bool:
    """
    True when most significant words of `candidate_title` appear on the first pages.

    Guards against accepting a cited paper's DOI or an unrelated search hit:
    "Interpretation and machine translation towards google translate" shares almost
    no words with a BRAC evaluation's title page.
    """
    words = set(_significant_words(candidate_title))
    if len(words) < 2:
        return False
    page_words = set(_significant_words(first_pages))
    return len(words & page_words) / len(words) >= threshold


def _normalise_title(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def titles_agree(candidate: str, own_title: str, threshold: float = 0.85) -> bool:
    """
    True when a looked-up title is the paper's own title: near-identical, or one
    contains the other (subtitles are often dropped).
    """
    from difflib import SequenceMatcher

    a, b = _normalise_title(candidate), _normalise_title(own_title)
    if len(a) < 12 or len(b) < 12:
        return False
    if a in b or b in a:
        return min(len(a), len(b)) / max(len(a), len(b)) >= 0.5
    return SequenceMatcher(None, a, b).ratio() >= threshold


def extract_dois_from_text(text: str) -> list:
    """Every DOI in `text`, in order of appearance, without duplicates."""
    found = []
    for match in re.finditer(r'10\.\d{4,}/[^\s\]>)\'"]+', text or ""):
        doi = re.sub(r'[.,;:\'")\]]+$', '', match.group(0))
        if len(doi) > 10 and doi.lower() not in (d.lower() for d in found):
            found.append(doi)
    return found


def _clean_list(value) -> list:
    if not value:
        return []
    if isinstance(value, str):
        value = [v.strip() for v in value.split(",")]
    return [str(v).strip() for v in value if str(v).strip()]


METHOD_KEYWORDS = (
    "random", "control group", "treatment group", "difference-in-difference",
    "difference in difference", "regression discontinuity", "instrumental variable",
    "propensity score", "matching", "identification strategy", "empirical strategy",
    "quasi-experiment", "baseline", "endline", "panel data", "cross-section", "qualitative",
    "interviews", "focus group", "mixed method", "case study", "systematic review", "meta-analysis",
)


def build_design_excerpt(content: str, abstract: str = None, max_chars: int = 7000) -> str:
    """
    Text for the study design classifier: the abstract or opening, then paragraphs
    that describe the method. Reports often open with a cover and contents pages, so
    the first few thousand characters alone left six papers "unknown".
    """
    content = content or ""
    head = (abstract or content[:2500]).strip()
    picked, used = [], len(head)
    for para in re.split(r"\n\s*\n", content[2500:]):
        low = para.lower()
        if any(k in low for k in METHOD_KEYWORDS):
            para = para.strip()[:800]
            if used + len(para) > max_chars:
                break
            picked.append(para)
            used += len(para)
    return head + ("\n\n[Method passages]\n" + "\n\n".join(picked) if picked else "")


# ============================================================================
# LLM Extraction
# ============================================================================

async def llm_extract_paper_fields(first_pages: str, api_key: str) -> Optional[dict]:
    """
    Read a paper's first pages and return title, authors, year, study countries,
    sectors, study_type and intervention_type as a dict.
    """
    import httpx
    import json

    prompt = f"""Below are the first pages of a development research paper or report.

{first_pages[:FIRST_PAGES_CHARS]}

Return JSON with these keys:
- title: the paper's own title, as printed on its first page, in title case (not all capitals)
- authors: list of author names, as printed
- year: publication year as an integer, or null
- countries: countries where the intervention ran or the data were collected, as official
  English names (e.g. "Bangladesh"). Do NOT list countries of the authors' universities or of
  funders. Empty list if the paper names none.
- sectors: list of sectors (e.g. "social protection", "agriculture", "health", "education", "finance")
- study_type: one of "RCT", "quasi-experimental", "systematic-review", "meta-analysis",
  "observational", "qualitative", "mixed-methods", "other"
- intervention_type: the intervention studied, in a few words

Return ONLY valid JSON."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {
                        "role": "system",
                        "content": "You extract bibliographic and study metadata. Respond with valid JSON only."
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 600,
                "response_format": {"type": "json_object"},
            },
        )

        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        return json.loads(content)


async def classify_study_design_llm(
    title: str,
    abstract_or_content: str,
    api_key: str,
) -> dict:
    """
    Classify study design using LLM with OpenRouter.
    
    Returns dict with study_design, study_design_confidence, study_design_reasoning.
    """
    import httpx
    import json
    
    prompt = f"""Analyze this research document and classify its primary study design.

DOCUMENT TITLE: {title or "Unknown"}

ABSTRACT/CONTENT:
{abstract_or_content[:7000] if abstract_or_content else "No abstract available"}

STUDY DESIGN CATEGORIES:

EXPERIMENTAL (randomized assignment):
- rct: Randomized Controlled Trial - random assignment to treatment/control
- cluster_rct: Cluster RCT - randomization at group/community level

QUASI-EXPERIMENTAL (exploits natural variation):
- regression_discontinuity: Uses a cutoff/threshold for assignment
- difference_in_differences: Compares before/after with treatment/control groups
- instrumental_variable: Uses exogenous variation to identify causal effects
- propensity_score_matching: Statistically matches treatment/control groups
- interrupted_time_series: Analyzes trend changes after intervention
- synthetic_control: Constructs synthetic counterfactual from donor pool

OBSERVATIONAL (no experimental manipulation):
- cohort: Follows groups over time
- cross_sectional: Point-in-time measurement
- case_control: Compares cases with controls retrospectively
- panel: Repeated observations of same units over time

QUALITATIVE (non-numerical analysis):
- qualitative: Interviews, focus groups, thematic analysis
- mixed_methods: Combines quantitative and qualitative approaches
- case_study: In-depth analysis of specific case(s)
- ethnography: Immersive observation of communities/cultures

SYNTHESIS:
- systematic_review: Systematic literature review
- meta_analysis: Statistical synthesis of multiple studies

OTHER:
- modeling: Simulations, economic modeling, theoretical models
- descriptive: Describes patterns without causal claims
- theory: Theoretical/conceptual paper

Return JSON:
{{
    "study_design": "one of the codes above (e.g., 'rct', 'difference_in_differences')",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation"
}}

If you cannot determine, return {{"study_design": "unknown", "confidence": 0.0, "reasoning": "Could not determine"}}
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a research methodology expert. Classify study designs accurately. Return only valid JSON."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 400,
                },
            )
            
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            
            result = json.loads(content)
            return {
                "study_design": result.get("study_design", "unknown"),
                "study_design_confidence": float(result.get("confidence", 0.5)),
                "study_design_reasoning": result.get("reasoning", ""),
            }
            
    except Exception as e:
        print(f"  ⚠ Study design classification failed: {e}")
        return {
            "study_design": "unknown",
            "study_design_confidence": 0.0,
            "study_design_reasoning": f"Classification error: {str(e)}",
        }
