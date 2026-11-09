"""
Modal MinerU / MonkeyOCR Library

Modular components for PDF processing pipeline.

Modules:
- config: Modal app, images (MinerU + MonkeyOCR), secrets, volumes
- utils: Helper functions (R2 client, sanitization)
- extraction: MinerU & MonkeyOCR PDF extraction
- metadata: CrossRef, OpenAlex, LLM enrichment
- embedding: Chunking, embedding, writing chunks to Supabase
- chunks: Supabase chunk-store helpers (shared client in src/vectorstore)
- processing: PDF processing functions (GPU)
- orchestration: Batch processing orchestration
"""

from .config import (
    app,
    base_image,
    docling_image,
    monkeyocr_image,
    model_cache,
    r2_secret,
    cohere_secret,
    openrouter_secret,
    supabase_secret,
    DEFAULT_PDF_PARSER,
)

from .utils import (
    get_r2_client,
    get_bucket_name,
    sanitize_text,
    sanitize_dict,
)

from .extraction import (
    run_mineru,
    run_docling,
    run_monkeyocr,
    post_process_content,
    extract_title,
    extract_abstract,
)

from .metadata import (
    resolve_metadata,
    classify_study_design_llm,
)

from .embedding import (
    embed_and_index,
    chunk_content,
    chunk_content_with_pages,
)

from .processing import (
    process_pdf,
    process_pdf_monkeyocr,
    process_pdf_rag,
    process_pdf_rag_docling,
    parse_pdf_docling,
    process_rag_document,
    sync_to_postgres,
    sync_to_supabase_rag,
)

from .refresh import (
    refresh_document_metadata,
    refresh_project_metadata,
)

from .chunks import (
    check_chunks_indexed,
    delete_doc_chunks,
)

from .orchestration import (
    orchestrate,
    orchestrate_rag,
    list_pdfs,
    check_vector_store_status,
)

__all__ = [
    # Config
    "app",
    "base_image",
    "docling_image",
    "monkeyocr_image",
    "model_cache",
    "r2_secret",
    "cohere_secret",
    "openrouter_secret",
    "supabase_secret",
    # Utils
    "get_r2_client",
    "get_bucket_name",
    "sanitize_text",
    "sanitize_dict",
    # Extraction
    "run_mineru",
    "run_docling",
    "run_monkeyocr",
    "post_process_content",
    "extract_title",
    "extract_abstract",
    # Metadata
    "resolve_metadata",
    "classify_study_design_llm",
    # Embedding
    "embed_and_index",
    "chunk_content",
    "chunk_content_with_pages",
    # Processing
    "process_pdf",
    "process_pdf_monkeyocr",
    "process_pdf_rag",
    "process_pdf_rag_docling",
    "parse_pdf_docling",
    "process_rag_document",
    "check_chunks_indexed",
    "delete_doc_chunks",
    "sync_to_postgres",
    "sync_to_supabase_rag",
    # Orchestration
    "orchestrate",
    "orchestrate_rag",
    "list_pdfs",
    "check_vector_store_status",
    # Metadata refresh
    "refresh_document_metadata",
    "refresh_project_metadata",
]
