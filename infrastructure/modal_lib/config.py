"""
Modal App Configuration

Defines the Modal app, images, secrets, volumes, and constants.
This module must be imported by all other modules that use @app.function decorators.
"""

import modal

# ============================================================================
# Modal App
# ============================================================================

app = modal.App("evidence-assistant-mineru")

# ============================================================================
# Constants
# ============================================================================

# ============================================================================
# Docker Image
# ============================================================================

# Base image with system dependencies
base_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "libgl1-mesa-glx",
        "libglib2.0-0",
        "libsm6",
        "libxext6",
        "libxrender-dev",
    )
    .pip_install(
        "mineru[core]>=2.6.0",
        "boto3",
        "cohere>=5.0.0",
        "httpx",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "supabase>=2.0.0",
    )
    .add_local_python_source("modal_lib", "src")  # Include modal_lib package in container
)

# MonkeyOCR image — uses PyTorch+CUDA official image as base to guarantee
# GPU-accelerated VLM inference without manual wheel management.
# Model: echo-miao/MonkeyOCR (HuggingFace)
# Outputs markdown comparable to MinerU, enabling side-by-side comparison.
# Docling (CPU) image: default parser candidate after the TVET bake-off.
# Pinned to the version validated locally (docling 2.141.0). Model weights download from
# Hugging Face on first use and are cached in the shared model volume.
docling_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "docling==2.141.0",
        "boto3",
        "cohere>=5.0.0",
        "httpx",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "supabase>=2.0.0",
    )
    .env({"HF_HOME": "/cache/huggingface", "OMP_NUM_THREADS": "8"})
    .add_local_python_source("modal_lib", "src")
)

# Parser used when a caller does not choose one ("mineru" or "docling")
DEFAULT_PDF_PARSER = "mineru"

monkeyocr_image = (
    modal.Image.from_registry(
        # runtime is sufficient — flash-attn installed via pre-built wheel below
        "pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime",
        add_python="3.11",
    )
    .apt_install(
        "git",            # Required for pip install from GitHub
        "libgl1-mesa-glx",
        "libglib2.0-0",
        "libsm6",
        "libxext6",
        "libxrender-dev",
        "poppler-utils",  # pdf2image backend
        "build-essential", # gcc — required by Triton JIT for CUDA kernel compilation
    )
    .pip_install(
        # MonkeyOCR from GitHub (no PyPI release yet)
        "git+https://github.com/Yuliang-Liu/MonkeyOCR.git",
        "transformers>=4.40.0",
        "huggingface_hub>=0.23.0",
        "accelerate>=0.30.0",
        "pdf2image",
        "Pillow>=10.0.0",
        "pymupdf",  # fitz — fast PDF → image conversion
        # Shared pipeline deps
        "boto3",
        "cohere>=5.0.0",
        "httpx",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "supabase>=2.0.0",
        "beautifulsoup4",
        "pyyaml",          # required for model_configs.yaml generation
        "einops",          # required by flash-attn/bert_padding.py (installed --no-deps)
    )
    # flash-attn has no manylinux wheel; install from pre-built GitHub release.
    # Tries cxx11abiFALSE (conda torch default) and falls back to TRUE.
    .run_commands(
        "pip install --no-deps "
        "https://github.com/Dao-AILab/flash-attention/releases/download/v2.6.3/"
        "flash_attn-2.6.3+cu123torch2.3cxx11abiFALSE-cp310-cp310-linux_x86_64.whl"
        " || "
        "pip install --no-deps "
        "https://github.com/Dao-AILab/flash-attention/releases/download/v2.6.3/"
        "flash_attn-2.6.3+cu123torch2.3cxx11abiTRUE-cp310-cp310-linux_x86_64.whl"
    )
    .add_local_python_source("modal_lib", "src")
)

# ============================================================================
# Volumes
# ============================================================================

# Volume for caching HuggingFace models (persists across runs)
model_cache = modal.Volume.from_name("mineru-model-cache", create_if_missing=True)

# ============================================================================
# Secrets
# ============================================================================

r2_secret = modal.Secret.from_name("r2-credentials")
cohere_secret = modal.Secret.from_name("cohere-credentials")
openrouter_secret = modal.Secret.from_name("openrouter-credentials")
supabase_secret = modal.Secret.from_name("SUPABASE")
