# docker-compose.override.yml example

Sanitized copy of local docker-compose.override.yml. Replace YOUR_PROXY_IP with your actual proxy IP before use.

```yaml
# Прокси настройки для обхода географических ограничений AI API
# Proxy IP: YOUR_PROXY_IP

services:
  # Open WebUI
  open-webui:
    shm_size: 2g  # Fix SEGFAULT: PyTorch/ChromaDB need shared memory
    environment:
      - RAG_EMBEDDING_ENGINE=ollama
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"

  # n8n main service
  n8n:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"

  # n8n workers (worker-1)
  n8n-worker-1:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"

  # n8n workers (worker-2)
  n8n-worker-2:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"

  # Docling service (GPU + VLM support)
  docling:
    runtime: nvidia  # GPU support (NVIDIA)
    shm_size: 4g  # Increased for GPU models (override base 1g)
    environment:
      # Path where models are stored (must match volume mount path)
      - DOCLING_SERVE_ARTIFACTS_PATH=/opt/app-root/src/models  # Temporarily disabled for initial model download
      - NVIDIA_VISIBLE_DEVICES=all
      - DOCLING_DEVICE=cuda:0
      - EASYOCR_MODULE_PATH=/opt/app-root/src/.cache/easyocr
      - DOCLING_SERVE_LOAD_MODELS_AT_BOOT=true
      - DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true
      # Debug logging (detailed logs for troubleshooting)
      # - DOCLING_DEBUG_PROFILE_PIPELINE_TIMINGS=true
      # - PYTHONUNBUFFERED=1
      # HuggingFace Hub download timeouts (increase for slow connections/proxies)
      - HF_HUB_DOWNLOAD_TIMEOUT=3600
      - HF_HUB_ETAG_TIMEOUT=1800
      # HuggingFace Mirror для быстрой загрузки (раскомментируйте если нужно)
      - HF_ENDPOINT=https://hf-mirror.com
    volumes:
      # Persistent volume for pre-downloaded models (temporarily disabled)
      - docling_models:/opt/app-root/src/models
    healthcheck:
      start_period: 120s  # Increased for GPU image and model loading
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      # HuggingFace main domains
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"
      # HuggingFace CDN hosts (CRITICAL for model downloads!)
      - "cdn-lfs.hf.co:YOUR_PROXY_IP"
      - "cdn-lfs-us-1.hf.co:YOUR_PROXY_IP"
      - "cdn-lfs-eu-1.hf.co:YOUR_PROXY_IP"
      - "cdn-lfs-eu-2.hf.co:YOUR_PROXY_IP"
      - "cdn-lfs-ap-1.hf.co:YOUR_PROXY_IP"
      # Xet Storage CDN for Docling models
      - "cas-bridge.xethub.hf.co:YOUR_PROXY_IP"
      - "cas-bridge-direct.xethub.hf.co:YOUR_PROXY_IP"
      - "cas-server.xethub.hf.co:YOUR_PROXY_IP"
      - "transfer.xethub.hf.co:YOUR_PROXY_IP"

  # Flowise (если используется)
  flowise:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"

  # RAGFlow (если используется)
  ragflow:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "generativelanguage.googleapis.com:YOUR_PROXY_IP"
      - "aiplatform.googleapis.com:YOUR_PROXY_IP"
      - "oauth2.googleapis.com:YOUR_PROXY_IP"
      - "content-generativelanguage.googleapis.com:YOUR_PROXY_IP"

  # LightRAG
  lightrag:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
    environment:
      LLM_BINDING: openai
      LLM_MODEL: gpt-5.4-nano
      LLM_BINDING_HOST: https://api.openai.com/v1
      LLM_BINDING_API_KEY: ${OPENAI_API_KEY}
      EMBEDDING_BINDING: openai
      EMBEDDING_MODEL: text-embedding-3-large
      EMBEDDING_DIM: 3072
      EMBEDDING_BINDING_HOST: https://api.openai.com/v1
      EMBEDDING_BINDING_API_KEY: ${OPENAI_API_KEY}
      SUMMARY_MAX_TOKENS: 1000
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "python -c 'import urllib.request; urllib.request.urlopen(\"http://localhost:9621/health\", timeout=5)' || exit 1",
        ]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  # RAG-Anything internal ingestion runner
  raganything:
    build:
      context: ./raganything
      dockerfile: Dockerfile
    container_name: raganything
    profiles: ["raganything"]
    restart: unless-stopped
    runtime: nvidia
    shm_size: 4g
    command: ["python", "/app/cleanup_runtime_files.py", "watch"]
    environment:
      HTTP_PROXY: ${GOST_PROXY_URL:-}
      HTTPS_PROXY: ${GOST_PROXY_URL:-}
      http_proxy: ${GOST_PROXY_URL:-}
      https_proxy: ${GOST_PROXY_URL:-}
      NO_PROXY: ${GOST_NO_PROXY:-}
      no_proxy: ${GOST_NO_PROXY:-}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      NVIDIA_VISIBLE_DEVICES: all
      NVIDIA_DRIVER_CAPABILITIES: compute,utility
      PYTHONUNBUFFERED: "1"
    volumes:
      - raganything_cache:/app/cache
      - lightrag_data:/app/data/rag_storage
      - ./raganything/input:/app/data/input
      - ./raganything/output:/app/data/output
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    extra_hosts:
      - "host.docker.internal:host-gateway"
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"
      - "huggingface.co:YOUR_PROXY_IP"
      - "api-inference.huggingface.co:YOUR_PROXY_IP"
      - "cdn-lfs.hf.co:YOUR_PROXY_IP"
      - "cdn-lfs-us-1.hf.co:YOUR_PROXY_IP"
      - "cdn-lfs-eu-1.hf.co:YOUR_PROXY_IP"
      - "cdn-lfs-eu-2.hf.co:YOUR_PROXY_IP"
      - "cdn-lfs-ap-1.hf.co:YOUR_PROXY_IP"
      - "cas-bridge.xethub.hf.co:YOUR_PROXY_IP"
      - "cas-bridge-direct.xethub.hf.co:YOUR_PROXY_IP"
      - "cas-server.xethub.hf.co:YOUR_PROXY_IP"
      - "transfer.xethub.hf.co:YOUR_PROXY_IP"

  # Letta
  letta:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"

  # ComfyUI
  comfyui:
    extra_hosts:
      - "api.openai.com:YOUR_PROXY_IP"
      - "api.anthropic.com:YOUR_PROXY_IP"

  # Ollama port exposure for host machine access
  ollama-gpu:
    ports:
      - "11434:11434"
    environment:
      # Enable both GPUs (comma-separated list of GPU IDs or use UUIDs)
      - CUDA_VISIBLE_DEVICES=0,1
      # Alternatively, you can use GPU UUIDs for more reliability:
      # - CUDA_VISIBLE_DEVICES=GPU-4380c357-82c7-26fb-e6d0-9168ff90208f,GPU-c1183c01-35ec-bed5-2556-7b26d606d46f
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all  # Changed from '1' to 'all' to reserve both GPUs
              capabilities: [gpu]
      
# Volumes for persistent model storage
volumes:
  docling_models:
    name: localai_docling_models
  raganything_cache:
    name: localai_raganything_cache
```
