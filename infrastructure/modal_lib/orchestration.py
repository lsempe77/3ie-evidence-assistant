"""
Orchestration functions for batch PDF processing.

Contains:
- orchestrate: Process all PDFs in global input-pdfs folder
- orchestrate_rag: Process all PDFs for a specific RAG project
- list_pdfs: List PDFs and processing status
- check_vector_store_status: Check the Supabase chunk store
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import (
    DEFAULT_PDF_PARSER,
    app,
    base_image,
    r2_secret,
    cohere_secret,
    supabase_secret,
)
from .utils import get_r2_client, get_bucket_name
from .processing import process_pdf, process_pdf_rag, process_pdf_rag_docling
from .chunks import check_chunks_indexed, get_store, indexed_doc_keys


# ============================================================================
# Global Orchestrator
# ============================================================================

@app.function(
    image=base_image,
    secrets=[r2_secret, supabase_secret],
    timeout=300,
)
def orchestrate(force_reprocess: bool = False, check_qdrant: bool = True, max_documents: int = 0) -> dict:
    """
    Scan R2 for new PDFs and queue them for processing.
    
    Smart deduplication:
    1. Checks if JSON output exists in R2 (fast)
    2. Optionally checks if chunks exist in the chunk store (thorough)
    3. Can force reprocess with force_reprocess=True
    
    Args:
        force_reprocess: If True, reprocess all PDFs even if outputs exist
        check_qdrant: If True, also verify chunks exist (name kept for API compatibility)
        max_documents: Maximum number of PDFs to queue (0 = unlimited)
        
    Returns:
        dict with counts of queued, skipped, and failed PDFs
    """
    
    # Duplicate chunks are impossible: (project, doc_key, chunk_index) is unique in the chunks table.
    
    s3 = get_r2_client()
    bucket = get_bucket_name()
    
    # List input PDFs with pagination
    input_prefix = "input-pdfs/"
    pdf_keys = []
    continuation_token = None
    
    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=input_prefix, ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=input_prefix)
        
        if "Contents" in response:
            pdf_keys.extend([obj["Key"] for obj in response["Contents"] if obj["Key"].lower().endswith(".pdf")])
        
        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break
    
    if not pdf_keys:
        return {"message": "No PDFs found in input-pdfs/", "queued": 0}
    
    print(f"Found {len(pdf_keys)} PDFs in R2")
    
    # Detect duplicates by base name
    def extract_base_name(pdf_key: str) -> str:
        stem = Path(pdf_key).stem
        if "_" in stem and len(stem.split("_")[0]) == 8:
            return "_".join(stem.split("_")[1:])
        return stem
    
    base_name_to_keys = {}
    for pdf_key in pdf_keys:
        base = extract_base_name(pdf_key)
        if base not in base_name_to_keys:
            base_name_to_keys[base] = []
        base_name_to_keys[base].append(pdf_key)
    
    duplicates = {base: keys for base, keys in base_name_to_keys.items() if len(keys) > 1}
    if duplicates:
        print(f"⚠ Found {len(duplicates)} duplicate base names")
    
    # Check existing outputs
    output_prefix = "outputs/json/"
    existing_outputs = set()
    continuation_token = None
    
    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=output_prefix, ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=output_prefix)
        
        if "Contents" in response:
            existing_outputs.update(Path(obj["Key"]).stem for obj in response["Contents"])
        
        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break
    
    print(f"Found {len(existing_outputs)} existing JSON outputs")
    
    indexed_base_names = set()
    for output_name in existing_outputs:
        indexed_base_names.add(extract_base_name(f"{output_name}.pdf"))
    
    # Queue processing
    queued = []
    skipped_r2 = []
    skipped_qdrant = []
    needs_reindex = []
    skipped_limit = []
    skipped_errors = []
    skipped_duplicates = []
    
    for pdf_key in pdf_keys:
        pdf_name = Path(pdf_key).stem
        base_name = extract_base_name(pdf_key)
        
        if base_name in indexed_base_names and pdf_name not in existing_outputs:
            skipped_duplicates.append(pdf_key)
            print(f"  🔄 Skipping duplicate: {pdf_key}")
            continue
        
        has_r2_output = pdf_name in existing_outputs
        
        if has_r2_output and not force_reprocess:
            if check_qdrant:
                is_indexed, chunk_count, qdrant_error = check_chunks_indexed(pdf_name)
                
                if qdrant_error:
                    skipped_errors.append({"key": pdf_key, "error": qdrant_error})
                    print(f"  ❌ Skipping (chunk check error): {pdf_key}")
                    continue
                
                if is_indexed:
                    skipped_qdrant.append({"key": pdf_key, "chunks": chunk_count})
                    print(f"  ✓ Skipping (R2 output + chunks OK): {pdf_key}")
                    continue
                else:
                    if max_documents > 0 and (len(queued) + len(needs_reindex)) >= max_documents:
                        skipped_limit.append(pdf_key)
                        continue
                    needs_reindex.append(pdf_key)
                    print(f"  ⚠ Re-indexing: {pdf_key}")
                    process_pdf.spawn(pdf_key=pdf_key, skip_extraction=True)
                    continue
            else:
                skipped_r2.append(pdf_key)
                continue
        
        if max_documents > 0 and (len(queued) + len(needs_reindex)) >= max_documents:
            skipped_limit.append(pdf_key)
            continue
        
        print(f"  Queuing: {pdf_key}")
        process_pdf.spawn(pdf_key=pdf_key, skip_extraction=False)
        queued.append(pdf_key)
    
    return {
        "queued": len(queued),
        "skipped_r2_only": len(skipped_r2),
        "skipped_fully_indexed": len(skipped_qdrant),
        "skipped_qdrant_errors": len(skipped_errors),
        "skipped_duplicates": len(skipped_duplicates),
        "needs_reindex": len(needs_reindex),
        "skipped_limit": len(skipped_limit),
        "max_documents": max_documents,
        "total": len(pdf_keys),
        "duplicate_groups": len(duplicates),
        "queued_files": queued[:10],
        "reindex_files": needs_reindex[:10],
    }


# ============================================================================
# RAG Project Orchestrator
# ============================================================================

@app.function(
    image=base_image,
    secrets=[r2_secret, cohere_secret, supabase_secret],
    timeout=3600,
)
def orchestrate_rag(
    project_id: str,
    qdrant_collection: Optional[str] = None,  # ignored; kept for callers of the old signature
    force_reprocess: bool = False,
    max_documents: int = 0,
    parser: Optional[str] = None,
) -> dict:
    """
    Process all documents for a specific RAG project.

    parser: "docling" (CPU) or "mineru" (GPU); defaults to DEFAULT_PDF_PARSER.
    
    Called from the backend API when user clicks "Process Documents".
    
    Args:
        project_id: The RAG project UUID
        qdrant_collection: Ignored; kept for callers of the old signature
        force_reprocess: If True, reprocess all PDFs
        max_documents: Max docs to process (0 = unlimited)
        
    Returns:
        dict with processing stats
    """
    from supabase import create_client
    
    s3 = get_r2_client()
    bucket = get_bucket_name()
    
    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    
    input_prefix = f"rags/{project_id}/input-pdfs/"
    output_prefix = f"rags/{project_id}/outputs/"
    
    print(f"Processing RAG project: {project_id}")
    print(f"  Input prefix: {input_prefix}")
    print(f"  Chunks go to project: {project_id}")
    
    # List input PDFs
    pdf_keys = []
    continuation_token = None
    
    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=input_prefix, ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=input_prefix)
        
        if "Contents" in response:
            pdf_keys.extend([obj["Key"] for obj in response["Contents"] if obj["Key"].lower().endswith(".pdf")])
        
        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break
    
    if not pdf_keys:
        return {"message": "No PDFs found", "queued": 0, "project_id": project_id}
    
    print(f"Found {len(pdf_keys)} PDFs")
    
    # Check existing outputs
    existing_outputs = set()
    json_prefix = f"{output_prefix}json/"
    continuation_token = None
    
    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=json_prefix, ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=bucket, Prefix=json_prefix)
        
        if "Contents" in response:
            for obj in response["Contents"]:
                existing_outputs.add(Path(obj["Key"]).stem)
        
        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break
    
    print(f"Found {len(existing_outputs)} existing outputs")
    
    # Documents that already have chunks
    qdrant_indexed = set()
    try:
        qdrant_indexed = indexed_doc_keys(project_id)
        print(f"Found {len(qdrant_indexed)} documents with chunks")
    except Exception as e:
        print(f"  Chunk store check failed: {e}")
    
    # Determine what to process
    to_process = []
    to_reindex = []
    skipped = []
    
    for pdf_key in pdf_keys:
        pdf_name = Path(pdf_key).stem
        doc_id = pdf_name
        
        has_r2_output = doc_id in existing_outputs
        has_qdrant = doc_id in qdrant_indexed
        
        if not force_reprocess:
            if has_r2_output and has_qdrant:
                skipped.append(pdf_key)
                print(f"  ✓ Skipping (R2 output + chunks OK): {pdf_name}")
                continue
            elif has_r2_output and not has_qdrant:
                if max_documents > 0 and (len(to_process) + len(to_reindex)) >= max_documents:
                    skipped.append(pdf_key)
                    continue
                to_reindex.append(pdf_key)
                print(f"  ⚠ Re-indexing: {pdf_name}")
                continue
        
        if max_documents > 0 and (len(to_process) + len(to_reindex)) >= max_documents:
            skipped.append(pdf_key)
            continue
        
        print(f"  Queuing: {pdf_name}")
        to_process.append(pdf_key)
    
    all_to_process = to_process + to_reindex
    
    if not all_to_process:
        return {
            "project_id": project_id,
            "processed": 0,
            "skipped": len(skipped),
            "total": len(pdf_keys),
            "results": [],
        }
    
    print(f"\nProcessing {len(all_to_process)} PDFs...")
    
    # Create processing job
    job_id = None
    try:
        job_result = supabase.table("processing_jobs").insert({
            "rag_project_id": project_id,
            "job_type": "ingest",
            "status": "running",
            "progress": 0,
            "message": f"Processing 0/{len(all_to_process)} documents",
            "started_at": datetime.now().isoformat(),
        }).execute()
        if job_result.data:
            job_id = job_result.data[0]["id"]
            print(f"  Created job: {job_id}")
    except Exception as e:
        print(f"  ⚠ Failed to create job: {e}")
    
    def update_job_progress(completed: int, total: int, status: str = "running", error: str = None):
        if not job_id:
            return
        try:
            progress = int((completed / total) * 100) if total > 0 else 0
            update_data = {
                "progress": progress,
                "message": f"Processed {completed}/{total} documents",
                "status": status,
            }
            if status == "completed":
                update_data["completed_at"] = datetime.now().isoformat()
            if error:
                update_data["error_message"] = error
            supabase.table("processing_jobs").update(update_data).eq("id", job_id).execute()
        except Exception:
            pass
    
    # Process with starmap
    results = []
    success = 0
    failed = 0
    processed_count = 0
    
    parser = parser or DEFAULT_PDF_PARSER
    worker = process_pdf_rag_docling if parser == "docling" else process_pdf_rag
    print(f"Parser: {parser}")
    for result in worker.starmap(
        [(pdf_key, project_id) for pdf_key in all_to_process],
        return_exceptions=True,
    ):
        processed_count += 1
        if isinstance(result, Exception):
            print(f"  ✗ Error: {result}")
            failed += 1
            results.append({"error": str(result)})
        elif isinstance(result, dict) and result.get("success") is False:
            # The worker catches its own errors and returns them, so count them here.
            print(f"  ✗ Failed: {result.get('doc_id', 'unknown')}: {result.get('error')}")
            failed += 1
            results.append(result)
        else:
            print(f"  ✓ Completed: {result.get('pdf_name', result.get('doc_id', 'unknown'))}")
            success += 1
            results.append(result)
        
        update_job_progress(processed_count, len(all_to_process))
    
    final_status = "completed"
    error_msg = f"{failed} documents failed" if failed > 0 else None
    update_job_progress(processed_count, len(all_to_process), status=final_status, error=error_msg)
    
    print(f"\nComplete: {success} succeeded, {failed} failed")

    # Study cards rank whole studies at question time (src/retrieval/study_cards.py).
    # Rebuild them for the whole project, so new documents are found at study level.
    try:
        from src.retrieval.study_cards import build_study_cards

        print(f"Study cards: {build_study_cards(project_id)} written")
    except Exception as e:
        print(f"  ⚠ Study cards not built: {e}")
    
    return {
        "project_id": project_id,
        "job_id": job_id,
        "processed": success,
        "failed": failed,
        "skipped": len(skipped),
        "total": len(pdf_keys),
        "results": results[:10],
    }


# ============================================================================
# Status Functions
# ============================================================================

@app.function(
    image=base_image,
    secrets=[r2_secret],
    timeout=60,
)
def list_pdfs() -> dict:
    """List PDFs in R2 and their processing status."""
    s3 = get_r2_client()
    bucket = get_bucket_name()
    
    # Count input PDFs
    input_count = 0
    continuation_token = None
    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=bucket, Prefix="input-pdfs/", ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=bucket, Prefix="input-pdfs/")
        
        if "Contents" in response:
            input_count += sum(1 for obj in response["Contents"] if obj["Key"].lower().endswith(".pdf"))
        
        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break
    
    # Count processed
    output_count = 0
    continuation_token = None
    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=bucket, Prefix="outputs/json/", ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=bucket, Prefix="outputs/json/")
        
        if "Contents" in response:
            output_count += len(response["Contents"])
        
        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break
    
    return {
        "total_input": input_count,
        "processed": output_count,
        "pending": max(0, input_count - output_count),
    }


@app.function(
    image=base_image,
    secrets=[supabase_secret],
    timeout=30,
)
def check_vector_store_status() -> dict:
    """Check the Supabase chunk store."""
    try:
        total = get_store().total_chunks()
        return {"status": "connected", "points_count": total, "vectors_count": total}
    except Exception as e:
        return {"status": "error", "message": str(e)}
