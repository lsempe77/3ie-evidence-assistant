# 3ie Evidence Assistant - Retrieval Module
#
# Names load on first use (PEP 562), so importing a light submodule such as
# src.retrieval.study_cards does not pull in LlamaIndex. The Modal image has no
# LlamaIndex, and the eager imports made the study-card rebuild fail there.
from importlib import import_module

_EXPORTS = {
    "QueryProcessor": "src.retrieval.query_processor",
    "QueryClassification": "src.retrieval.query_processor",
    "HybridRetriever": "src.retrieval.hybrid_retriever",
    "CohereReranker": "src.retrieval.reranker",
    "Reranker": "src.retrieval.reranker",
    "ContextBuilder": "src.retrieval.context_builder",
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    if name in _EXPORTS:
        return getattr(import_module(_EXPORTS[name]), name)
    raise AttributeError(f"module 'src.retrieval' has no attribute {name!r}")
