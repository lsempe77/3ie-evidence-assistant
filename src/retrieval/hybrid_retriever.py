"""
3ie Evidence Assistant - Hybrid Retriever

Implements hybrid search over Supabase Postgres (pgvector), combining:
- Dense vectors (semantic similarity, HNSW cosine)
- Postgres full-text search (keyword matching)
- Metadata filtering
- Reciprocal Rank Fusion (RRF), inside the hybrid_search SQL function
- MMR diversity filtering
- Multi-Query RAG-Fusion (query variants with RRF)
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np

from src.config.settings import settings
from src.ingestion.embeddings import EmbeddingGenerator
from src.retrieval.query_processor import ExtractedFilters
from src.utils.logging import get_logger
from src.vectorstore import ChunkStore, legacy_collection_to_project_id

logger = get_logger(__name__)


def mmr_diversity_filter(
    results: List["RetrievalResult"],
    query_embedding: List[float],
    embeddings: List[List[float]],
    lambda_param: float = 0.7,
    top_k: Optional[int] = None,
) -> List["RetrievalResult"]:
    """
    Apply Maximal Marginal Relevance (MMR) to diversify results.
    
    MMR balances relevance to query with diversity from already-selected items.
    This reduces redundant chunks that say similar things.
    
    MMR score = lambda * similarity(doc, query) - (1-lambda) * max(similarity(doc, selected))
    
    Args:
        results: Retrieved results sorted by relevance
        query_embedding: Query embedding vector
        embeddings: Embedding vectors for each result (same order as results)
        lambda_param: Balance between relevance (1.0) and diversity (0.0). Default 0.7
        top_k: Number of results to return (default: all)
        
    Returns:
        Reordered results with more diversity
        
    Reference: "The Use of MMR, Diversity-Based Reranking..." (Carbonell & Goldstein, 1998)
    """
    if len(results) <= 1 or len(embeddings) != len(results):
        return results
    
    top_k = top_k or len(results)
    
    # Convert to numpy for efficiency
    query_vec = np.array(query_embedding)
    doc_vecs = np.array(embeddings)
    
    # Normalize vectors for cosine similarity
    query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    doc_norms = np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-9
    doc_vecs = doc_vecs / doc_norms
    
    # Compute query-document similarities
    query_sims = doc_vecs @ query_vec
    
    # Compute document-document similarities (for diversity penalty)
    doc_doc_sims = doc_vecs @ doc_vecs.T
    
    # Greedy MMR selection
    selected_indices = []
    remaining = set(range(len(results)))
    
    # First: select highest relevance
    first_idx = int(np.argmax(query_sims))
    selected_indices.append(first_idx)
    remaining.remove(first_idx)
    
    # Iteratively select based on MMR score
    while len(selected_indices) < top_k and remaining:
        best_score = -float('inf')
        best_idx = None
        
        for idx in remaining:
            # Relevance to query
            relevance = query_sims[idx]
            
            # Max similarity to already selected (diversity penalty)
            max_sim_to_selected = max(doc_doc_sims[idx, s] for s in selected_indices)
            
            # MMR score
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim_to_selected
            
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx
        
        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining.remove(best_idx)
    
    # Return reordered results
    reordered = [results[i] for i in selected_indices]
    
    if len(reordered) < len(results):
        logger.debug(f"MMR diversity: {len(results)} → {len(reordered)} results (lambda={lambda_param})")
    else:
        logger.debug(f"MMR diversity reordering applied to {len(reordered)} results")
    
    return reordered


@dataclass
class RetrievalResult:
    """A single retrieval result."""
    node_id: str
    text: str
    score: float
    metadata: Dict[str, Any]
    
    # For parent-child retrieval
    parent_text: Optional[str] = None
    
    @property
    def study_id(self) -> Optional[str]:
        """Get study ID, falling back to doc_id or pdf_name for Modal-indexed docs."""
        return (
            self.metadata.get("study_id") or 
            self.metadata.get("doc_id") or 
            self.metadata.get("pdf_name") or
            self.metadata.get("document_id")
        )
    
    @property
    def title(self) -> Optional[str]:
        return self.metadata.get("title")
    
    @property
    def year(self) -> Optional[int]:
        return self.metadata.get("year")


class HybridRetriever:
    """
    Hybrid retrieval over one project's chunks.

    Features:
    - Dense vector search (Cohere embed-v4, pgvector HNSW)
    - Keyword search (Postgres full-text, English stemming)
    - Metadata filtering (year, sector, target population)
    - Reciprocal Rank Fusion of the two rankings
    - MMR diversity filtering
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        store: Optional[ChunkStore] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        mmr_enabled: bool = True,
        mmr_lambda: float = 0.7,  # Balance: 1.0 = pure relevance, 0.0 = pure diversity
        collection_name: Optional[str] = None,  # Legacy 'rag_<hex>' name, mapped to project_id
    ):
        self.project_id = project_id or legacy_collection_to_project_id(collection_name)
        if not self.project_id:
            raise ValueError(
                "HybridRetriever needs a project_id (or a legacy 'rag_<id>' collection name)"
            )
        self.store = store or ChunkStore()
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self.mmr_enabled = mmr_enabled
        self.mmr_lambda = mmr_lambda

    async def retrieve(
        self,
        query: str,
        top_k: int = settings.retrieval_top_k,
        filters: Optional[ExtractedFilters] = None,
        alpha: float = settings.hybrid_alpha,
    ) -> List[RetrievalResult]:
        """
        Perform hybrid retrieval with optional MMR diversity filtering.

        Keyword search joins the fusion when hybrid search is enabled and alpha < 1,
        matching the previous Qdrant behaviour (unweighted RRF of the two rankings).
        MMR (Maximal Marginal Relevance) then promotes diversity by balancing
        relevance to the query against similarity to already-selected chunks.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Metadata filters
            alpha: Hybrid switch: 1.0 = dense only, < 1.0 = dense + keyword

        Returns:
            List of retrieval results
        """
        query_embedding = self.embedding_generator.embed_query(query)

        # MMR needs a larger candidate pool to select diverse results from
        fetch_k = top_k * 2 if self.mmr_enabled else top_k
        use_keyword = settings.hybrid_enabled and alpha < 1.0

        rows = await asyncio.to_thread(
            self.store.hybrid_search,
            self.project_id,
            query,
            query_embedding,
            match_count=fetch_k,
            candidate_count=max(fetch_k, settings.retrieval_top_k),
            full_text_weight=1.0 if use_keyword else 0.0,
            semantic_weight=1.0,
            with_embeddings=self.mmr_enabled,
            **(filters.to_search_params() if filters else {}),
        )
        results = [self._row_to_result(r) for r in rows]
        embeddings = [r.get("embedding") or [] for r in rows] if self.mmr_enabled else None

        if self.mmr_enabled and len(results) > top_k and embeddings and all(embeddings):
            logger.debug(f"Applying MMR diversity filter (lambda={self.mmr_lambda}) to {len(results)} candidates")
            results = mmr_diversity_filter(
                results=results,
                embeddings=embeddings,
                query_embedding=query_embedding,
                top_k=top_k,
                lambda_param=self.mmr_lambda,
            )
            logger.info(f"MMR selected {len(results)} diverse results from {fetch_k} candidates")
        elif len(results) > top_k:
            results = results[:top_k]

        logger.info(f"Retrieved {len(results)} results for query: '{query[:50]}...'")
        return results

    @staticmethod
    def _row_to_result(row: Dict[str, Any]) -> RetrievalResult:
        """Convert a hybrid_search row to a RetrievalResult.

        Metadata keeps the keys the Qdrant payload used (doc_id, page_start, page_end,
        chunk_index, contextual_prefix, ...) so downstream code is unchanged.
        """
        metadata = dict(row.get("metadata") or {})
        metadata.setdefault("doc_id", row.get("doc_key"))
        metadata.setdefault("chunk_index", row.get("chunk_index"))
        for key in ("page_start", "page_end", "section"):
            if row.get(key) is not None:
                metadata.setdefault(key, row[key])
        if row.get("context_prefix"):
            metadata.setdefault("contextual_prefix", row["context_prefix"])
        metadata["semantic_rank"] = row.get("semantic_rank")
        metadata["keyword_rank"] = row.get("keyword_rank")
        return RetrievalResult(
            node_id=str(row["id"]),
            text=row.get("content") or "",
            score=float(row.get("score") or 0.0),
            metadata=metadata,
            parent_text=row.get("parent_text") or None,
        )

    async def retrieve_multi_query(
        self,
        queries: List[str],
        top_k: int = settings.retrieval_top_k,
        filters: Optional[ExtractedFilters] = None,
        alpha: float = settings.hybrid_alpha,
        rrf_k: int = 60,
    ) -> List[RetrievalResult]:
        """
        Perform multi-query retrieval with Reciprocal Rank Fusion.
        
        RAG-Fusion technique: retrieve for multiple query variants and fuse
        results using RRF to capture documents that match different phrasings.
        
        Args:
            queries: List of query variants (first is typically the original)
            top_k: Number of final results to return
            filters: Metadata filters
            alpha: Weight for dense vs sparse
            rrf_k: RRF ranking constant (higher = more weight to lower ranks)
            
        Returns:
            Fused results from all queries
            
        Reference: RAG-Fusion paper (https://arxiv.org/abs/2402.03367)
        """
        import asyncio
        
        if len(queries) == 1:
            # Single query - use standard retrieval
            return await self.retrieve(queries[0], top_k, filters, alpha)
        
        logger.info(f"Multi-query retrieval with {len(queries)} variants")
        
        # Retrieve for each query variant in parallel
        # Fetch more results per query since we'll deduplicate
        per_query_k = top_k * 2
        
        retrieval_tasks = [
            self.retrieve(q, per_query_k, filters, alpha)
            for q in queries
        ]
        
        all_results = await asyncio.gather(*retrieval_tasks)
        
        # Apply Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion(
            all_results,
            k=rrf_k,
            top_k=top_k,
        )
        
        logger.info(
            f"RRF fused {sum(len(r) for r in all_results)} results from "
            f"{len(queries)} queries into {len(fused_results)} final results"
        )
        
        return fused_results

    async def retrieve_with_decomposition(
        self,
        query: str,
        sub_queries: List[str],
        top_k: int = settings.retrieval_top_k,
        filters: Optional[ExtractedFilters] = None,
        alpha: float = settings.hybrid_alpha,
    ) -> List[RetrievalResult]:
        """
        Retrieve using query decomposition.
        
        For complex queries that have been decomposed, retrieves for each
        sub-query and merges results using RRF. This improves recall for
        comparisons and multi-aspect questions.
        
        Args:
            query: Original query (for fallback/context)
            sub_queries: Decomposed sub-queries
            top_k: Number of final results
            filters: Metadata filters
            alpha: Dense/sparse weight
            
        Returns:
            Merged results from all sub-queries
        """
        if not sub_queries:
            # No decomposition - use standard retrieval
            return await self.retrieve(query, top_k, filters, alpha)
        
        logger.info(f"Query decomposition retrieval with {len(sub_queries)} sub-queries")
        
        # Retrieve for each sub-query
        all_queries = sub_queries + [query]  # Include original as fallback
        
        return await self.retrieve_multi_query(
            queries=all_queries,
            top_k=top_k,
            filters=filters,
            alpha=alpha,
        )

    async def retrieve_with_step_back(
        self,
        query: str,
        step_back_query: str,
        top_k: int = settings.retrieval_top_k,
        filters: Optional[ExtractedFilters] = None,
        alpha: float = settings.hybrid_alpha,
    ) -> List[RetrievalResult]:
        """
        Retrieve using step-back prompting strategy.
        
        First retrieves for the broader step-back query to get context,
        then retrieves for the specific query. Results are merged with RRF,
        giving the specific query higher weight.
        
        Args:
            query: Original specific query
            step_back_query: Broader context query
            top_k: Number of final results
            filters: Metadata filters
            alpha: Dense/sparse weight
            
        Returns:
            Merged results prioritizing specific query matches
        """
        logger.info(f"Step-back retrieval: general='{step_back_query[:50]}...'")
        
        # Retrieve for both queries
        # Give specific query more weight by putting it first (RRF favors earlier results)
        return await self.retrieve_multi_query(
            queries=[query, step_back_query],
            top_k=top_k,
            filters=filters,
            alpha=alpha,
        )

    def _reciprocal_rank_fusion(
        self,
        result_lists: List[List[RetrievalResult]],
        k: int = 60,
        top_k: int = 10,
    ) -> List[RetrievalResult]:
        """
        Fuse multiple result lists using Reciprocal Rank Fusion.
        
        RRF score = sum(1 / (k + rank)) for each list where document appears.
        
        Args:
            result_lists: List of result lists from different queries
            k: RRF constant (default 60, from original paper)
            top_k: Number of results to return
            
        Returns:
            Fused and deduplicated results
        """
        # Track scores and keep first occurrence of each document
        doc_scores: Dict[str, float] = {}
        doc_results: Dict[str, RetrievalResult] = {}
        
        for results in result_lists:
            for rank, result in enumerate(results):
                doc_id = result.node_id
                
                # RRF formula: 1 / (k + rank)
                # rank is 0-indexed, so rank 0 gets 1/(k+0) = 1/k
                rrf_score = 1.0 / (k + rank)
                
                doc_scores[doc_id] = doc_scores.get(doc_id, 0.0) + rrf_score
                
                # Keep first occurrence (typically highest score from individual query)
                if doc_id not in doc_results:
                    doc_results[doc_id] = result
        
        # Sort by RRF score descending
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Build final result list with RRF scores
        fused = []
        for doc_id, rrf_score in sorted_docs[:top_k]:
            result = doc_results[doc_id]
            # Update score to RRF score for transparency
            result.score = rrf_score
            fused.append(result)
        
        return fused
    
    def retrieve_sync(
        self,
        query: str,
        top_k: int = settings.retrieval_top_k,
        filters: Optional[ExtractedFilters] = None,
    ) -> List[RetrievalResult]:
        """Synchronous retrieval."""
        import asyncio
        return asyncio.run(self.retrieve(query, top_k, filters))


class HierarchicalRetriever(HybridRetriever):
    """
    Hierarchical retrieval with study-level grouping.
    
    1. Retrieve broadly (top 50-100 chunks)
    2. Group by study
    3. Select top N studies
    4. Return top M chunks per study
    """
    
    def __init__(
        self,
        num_studies: int = 6,
        chunks_per_study: int = 3,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.num_studies = num_studies
        self.chunks_per_study = chunks_per_study
    
    async def retrieve(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[ExtractedFilters] = None,
        alpha: float = settings.hybrid_alpha,
    ) -> List[RetrievalResult]:
        """Hierarchical retrieval with study grouping."""
        # Get broad initial set
        broad_results = await super().retrieve(
            query=query,
            top_k=settings.retrieval_top_k,  # Get more initially
            filters=filters,
            alpha=alpha,
        )
        
        # Group by study
        by_study: Dict[str, List[RetrievalResult]] = {}
        for result in broad_results:
            study_id = result.study_id or "unknown"
            if study_id not in by_study:
                by_study[study_id] = []
            by_study[study_id].append(result)
        
        # Rank studies by best chunk score
        ranked_studies = sorted(
            by_study.items(),
            key=lambda kv: max(r.score for r in kv[1]),
            reverse=True,
        )
        
        # Select top studies and chunks
        selected = []
        for study_id, chunks in ranked_studies[:self.num_studies]:
            # Sort chunks by score
            sorted_chunks = sorted(chunks, key=lambda r: r.score, reverse=True)
            selected.extend(sorted_chunks[:self.chunks_per_study])
        
        logger.info(
            f"Hierarchical retrieval: {len(by_study)} studies → "
            f"{min(len(by_study), self.num_studies)} studies, "
            f"{len(selected)} chunks"
        )
        
        return selected
