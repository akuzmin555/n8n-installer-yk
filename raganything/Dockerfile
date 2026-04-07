FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/cache/huggingface \
    HUGGINGFACE_HUB_CACHE=/app/cache/huggingface/hub \
    TRANSFORMERS_CACHE=/app/cache/huggingface/transformers \
    TORCH_HOME=/app/cache/torch \
    XDG_CACHE_HOME=/app/cache/xdg \
    MPLCONFIGDIR=/app/cache/matplotlib

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        ffmpeg \
        git \
        libgl1 \
        libglib2.0-0 \
        libmagic1 \
        libreoffice \
        poppler-utils \
        tini \
        wget && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --index-url https://download.pytorch.org/whl/cu128 \
        "torch==2.11.0+cu128" \
        "torchvision==0.26.0+cu128" && \
    python -m pip install \
        "lightrag-hku[api]" \
        "raganything"

COPY process_document.py /app/process_document.py
COPY cleanup_runtime_files.py /app/cleanup_runtime_files.py

RUN mkdir -p \
    /app/cache/huggingface \
    /app/cache/matplotlib \
    /app/cache/torch \
    /app/cache/xdg \
    /app/data/input \
    /app/data/output \
    /app/data/rag_storage

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-c", "import time; time.sleep(3600)"]
