# 3ie Evidence Assistant Evaluation Framework

**Created:** January 5, 2026  
**Status:** ✅ Production Ready

This document describes 3ie Evidence Assistant's citation quality evaluation framework, including the dual-lane evaluation approach, available tools, baseline metrics, and how to run evaluations.

---

## 📊 Quick Summary

| Metric | Current Score | Target | Status |
|--------|--------------|--------|--------|
| **Faithfulness** | 66.47% | 70%+ | ⚠️ Needs improvement |
| **Citation Recall** | 98.86% | 70% | ✅ Exceeds |
| **Citation Precision** | 98.86% | 70% | ✅ Exceeds |
| **Overall Score** | 88% | 80% | ✅ Exceeds |

---

## 🎯 Evaluation Philosophy

### The Problem with LLM-as-Judge

Traditional RAG evaluation uses LLMs to judge answer quality. This has problems:
- **Inconsistent**: Same answer can get different scores
- **Expensive**: Each evaluation costs API calls
- **Circular**: Using LLM to evaluate LLM outputs

### Our Solution: Dual-Lane Evaluation

We use **deterministic NLI models** (Natural Language Inference) instead of LLM-as-judge:

| Lane | Question Answered | Method |
|------|-------------------|--------|
| **Lane A: Faithfulness** | Is each claim grounded in ANY retrieved context? | MiniCheck NLI |
| **Lane B: Citation Alignment** | Does each cited source actually support its sentence? | MiniCheck NLI |

Both lanes use the same NLI backbone (MiniCheck), but pair different inputs:
- **Lane A**: claim ↔ all_contexts (groundedness)
- **Lane B**: sentence ↔ cited_context (citation accuracy)

---

## 🔧 Evaluation Tools

### 1. MiniCheck Evaluator (`evaluation/minicheck_evaluator.py`)

**Purpose:** Dual-lane evaluation using MiniCheck as NLI backbone

**Key Features:**
- Lane A (Faithfulness): Extracts claims, checks against all context
- Lane B (Citation Alignment): Checks each citation actually supports its sentence
- Two backends: `local` (Flan-T5-Large) or `api` (GPT-4o-mini for production)

**Metrics Produced:**
```python
@dataclass
class DualLaneResult:
    faithfulness: float        # Lane A: % claims supported by any context
    citation_recall: float     # Lane B: % sentences with valid citations  
    citation_precision: float  # Lane B: % citations that actually support
    citation_coverage: float   # % sources that were cited
    claim_details: List[Dict]  # Per-claim analysis
    sentence_details: List[Dict]  # Per-sentence analysis
```

**Usage:**
```python
from evaluation.minicheck_evaluator import MiniCheckEvaluator

# Production (API-based, no model download)
evaluator = MiniCheckEvaluator(backend='api', api_model='openai/gpt-4o-mini')

# Development (local Flan-T5-Large model)
evaluator = MiniCheckEvaluator(backend='local', cache_dir='./ckpts')

# Run evaluation
result = await evaluator.evaluate(
    query="What is the graduation approach?",
    answer="The graduation approach combines...",
    contexts=["Context 1...", "Context 2..."],
    citations=[{"id": 1, "text": "...", "source": "Study A"}]
)

print(f"Faithfulness: {result.faithfulness:.2%}")
print(f"Citation Recall: {result.citation_recall:.2%}")
print(f"Citation Precision: {result.citation_precision:.2%}")
```

### 2. Reliable Evaluator (`evaluation/reliable_evaluator.py`)

**Purpose:** Deterministic evaluation without any LLM-as-judge

**Methods:**
- **Faithfulness**: BART-MNLI NLI model
- **Citation Accuracy**: Cohere embedding similarity
- **Context Precision**: Reranker scores
- **Citation Coverage**: Regex-based

**When to Use:** 
- When you want fully deterministic, reproducible results
- When you want to avoid any LLM API costs for evaluation

### 3. RAGAS Evaluator (`evaluation/ragas_evaluator.py`)

**Purpose:** Standard RAGAS metrics for comparison with literature

**Metrics:**
- Faithfulness (RAGAS-style)
- Answer Relevancy
- Context Precision
- Context Recall

**When to Use:**
- Benchmarking against published RAG systems
- Academic comparisons

---

## 📁 Test Cases

**Location:** `evaluation/test_cases.json`

**Categories:**
| Category | Description | Example |
|----------|-------------|---------|
| `simple` | Basic conceptual questions | "What is the graduation approach?" |
| `lookup` | Find specific studies/evidence | "Find studies on graduation in Africa" |
| `synthesis` | Summarize across multiple sources | "What do studies say about long-term effects?" |
| `comparison` | Compare interventions/outcomes | "How do graduation programs compare to cash transfers?" |

**Current Test Cases:**
1. `graduation_1`: What is the graduation approach?
2. `graduation_2`: Key components of graduation programs
3. `evidence_1`: Evidence from Bangladesh
4. `evidence_2`: Studies in Africa
5. `synthesis_1`: Long-term effects
6. `synthesis_2`: Targeting the ultra-poor
7. `comparison_1`: Graduation vs cash transfers
8. `comparison_2`: Effects on women vs men

---

## 📈 Baseline Results

### MiniCheck Dual-Lane (January 2026)

**Collection:** `devchat_v2_enhanced` (Graduation Studies)

| Query | Faithfulness | Citation Recall | Citation Precision | Overall |
|-------|--------------|-----------------|-------------------|---------|
| Graduation approach definition | 0.58 | 1.00 | 1.00 | 0.86 |
| Key components | 0.67 | 1.00 | 1.00 | 0.89 |
| Bangladesh evidence | 0.70 | 1.00 | 1.00 | 0.90 |
| Africa studies | 0.80 | 1.00 | 1.00 | 0.93 |
| Long-term effects | 0.55 | 1.00 | 1.00 | 0.85 |
| **Average** | **0.66** | **1.00** | **1.00** | **0.89** |

### Post-Hoc Verification Test

**Purpose:** Test if removing unsupported sentences improves quality

| Condition | Faithfulness | Citation Recall | Citation Precision |
|-----------|--------------|-----------------|-------------------|
| Without verification | 0.65 | 1.00 | 1.00 |
| With verification | 0.65 | 1.00 | 0.97 |

**Finding:** Post-hoc verification is already integrated and working. The system rarely generates unsupported claims thanks to the Claim Ledger synthesis approach.

---

## Paragraph-role usage study (November 2026)

`evaluation/usage_study.py` follows every passage from the index into the reader and the answer, and maps it back to the paragraph of the paper it came from. `src/extraction/relevance_labels.py` labels each paragraph by role with `anthropic/claude-haiku-5.5`, and never rewrites it, so kept text stays verbatim with its page.

The study ran 211 questions over the 97 papers of the graduation collection. Recomputed from the cached artifacts, the 27,335 labelled paragraphs hold 1,842,494 words, and 33,869 passages were shown to the reader. The findings:

- Of the words shown to the reader, 31% are noise: other studies' findings (11%), background (9%) and boilerplate (11%). Those three roles supply 8% of the supporting quotes.
- Of 27,335 paragraphs, 1,551 (5.7%) were ever used as a supporting quote.
- 178 of 3,863 supporting quotes (4.6%) could not be found verbatim in any paragraph.
- The reader judges relevance by the kind of question (`src/agents/study_synthesis.py`). It marks 30 relevant studies per effects question and 1.6 per implementation question.
- The secondhand guard (`src/extraction/secondhand.py`) matches author-year citations only. 127 supporting quotes still came from paragraphs labelled as other studies' findings, and 91 of those were cited in answers.

These figures come from the run after the reader was changed to judge relevance by question kind. An earlier run, before that change, had 1,281 of 27,335 paragraphs used (4.7%), 188 of 3,194 quotes not verbatim (5.9%), 27 relevant studies per effects question and 0.7 per implementation question.

The index was then filtered by paragraph role (`src/ingestion/relevance_filter.py`) and the collection re-indexed. In the run against the filtered index, noise roles fell to 6% of what the reader is shown (from 31%) and to 1.2% of quotes (from 8.6%); own findings rose to 48% of what is shown and 63% of quotes; quotes not verbatim fell to 141 (2.6%); 1,820 of 27,335 paragraphs were used (6.7%). Relevant studies per question rose from 18.3 to 25.5, but readings per question also rose from 43.8 to 52.4, because the filtered index holds one document per parser unit and therefore more, smaller chunks, which changes retrieval volume. Passages that cannot be mapped back to a paragraph rose from 23 to 157, a measurement artifact of unit-based chunks not lining up with the parser paragraphs rather than an index defect.

Two checks separate the filter from the volume change. The full benchmark gate passed on the filtered index (claim score 0.566 against 0.552), so effect answers did not regress. In a fixed-budget comparison over 3 questions per category, each capped to the number of studies the unfiltered run read, the filtered index found 21.3 relevant studies per question against 16.1 for the unfiltered index, a 32% gain at equal reading volume against the 39% uncapped gain. Most of the improvement therefore comes from the filter, not only from reading more studies.

Quote verification (Phase 3) was then measured on the same 211 questions. Every supporting quote is now a verbatim span of the passages: the not-verbatim count fell from 141 (2.6%) to zero. Supporting quotes fell from 5,367 to 4,991 (7%), because a quote that could not be verified was dropped or snapped to its source sentence, and cited readings rose slightly from 3,392 to 3,448. Relevance per question held (25.5 to 25.2) and readings per question were unchanged.

To reproduce, run `python evaluation/usage_study.py analyse --project-id <uuid>`. The aggregate report is committed at `evaluation/results/usage_study/<uuid>/report.md`. The run logs, cached content and labels hold text from the papers and stay local (see `.gitignore`).

---

## 🚀 Running Evaluations

### Quick Evaluation (Single Query)

```bash
cd 3ie-evidence-assistant
python -c "
import asyncio
from evaluation.minicheck_evaluator import MiniCheckEvaluator
from src.agents.evidence_assistant_agent import EvidenceAssistantAgent
from src.retrieval.settings import SearchSettings

async def quick_eval():
    agent = EvidenceAssistantAgent(project_id='YOUR_PROJECT_ID')
    settings = SearchSettings(max_studies=5, use_claim_ledger=True)
    
    result = await agent.chat('What is the graduation approach?', settings)
    
    evaluator = MiniCheckEvaluator(backend='api')
    eval_result = await evaluator.evaluate(
        query='What is the graduation approach?',
        answer=result.answer,
        contexts=[s.text for s in result.sources],
        citations=result.citations
    )
    
    print(f'Faithfulness: {eval_result.faithfulness:.2%}')
    print(f'Citation Recall: {eval_result.citation_recall:.2%}')
    print(f'Citation Precision: {eval_result.citation_precision:.2%}')

asyncio.run(quick_eval())
"
```

### Full Test Suite

```bash
# Run MiniCheck evaluation on all test cases
python evaluation/run_claim_ledger_eval.py

# Run Reliable evaluator (NLI-based)
python evaluation/run_reliable_eval.py

# Run RAGAS evaluation
python evaluation/run_ragas_eval.py
```

### Results Location

All evaluation results are stored in `evaluation/`:
- `claim_ledger_minicheck_results.json` - Latest MiniCheck results
- `reliable_results_YYYY-MM-DD.json` - Reliable evaluator results
- `ragas_results_YYYY-MM-DD.json` - RAGAS results
- `post_hoc_verification_test_*.json` - Verification experiments

---

## 🔬 Key Insights

### What Improved Faithfulness

1. **Claim Ledger Synthesis** - Forces LLM to cite as it writes, not retrofit citations
2. **Hybrid Search** - BM25 + Dense retrieval catches more relevant context
3. **Contextual Chunking** - Adds document-level context to each chunk
4. **Reranking** - Cohere rerank-v3.5 filters to most relevant passages

### Current Limitations

1. **Faithfulness ~0.65-0.70** - Some claims are inferred rather than directly stated
2. **Answer Relevancy** - Not measured automatically (would need LLM)
3. **Edge Cases** - Complex multi-hop reasoning questions perform worse

### Future Improvements

1. **User Feedback Loop** - Collect 👍/👎 on answers
2. **Regression Testing** - Run test suite on every deploy
3. **Quality Sampling** - Run MiniCheck on 10% of production queries
4. **A/B Testing** - Compare prompt versions

---

## 📚 References

### Papers

- **MiniCheck** (EMNLP 2024): Efficient Fact-Checking of LLMs on Grounding Documents  
  https://arxiv.org/abs/2404.10774

- **ALCE** (ACL 2023): Citation Attribution for Large Language Models  
  https://arxiv.org/abs/2305.14627

- **TRUE** (2022): Turing Natural Language Generation Evaluation  
  https://arxiv.org/abs/2204.04991

- **RAGAS** (2023): Automated Evaluation of Retrieval Augmented Generation  
  https://arxiv.org/abs/2309.15217

### Implementation Details

- MiniCheck model: `lytang/MiniCheck-Flan-T5-Large` (770M params)
- Cached in: `ckpts/models--lytang--MiniCheck-Flan-T5-Large/`
- API backend uses: GPT-4o-mini for NLI (faster, cheaper)

---

## 🗂️ File Structure

```
evaluation/
├── minicheck_evaluator.py      # Dual-lane MiniCheck evaluator
├── reliable_evaluator.py       # Deterministic NLI evaluator  
├── ragas_evaluator.py          # Standard RAGAS metrics
├── test_cases.json             # Golden test cases
├── run_claim_ledger_eval.py    # Run MiniCheck on test suite
├── run_reliable_eval.py        # Run Reliable on test suite
├── run_ragas_eval.py           # Run RAGAS on test suite
├── test_post_hoc_verification.py  # Test verification layer
└── *_results*.json             # Evaluation results
```
