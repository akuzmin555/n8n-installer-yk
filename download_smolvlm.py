#!/usr/bin/env python3
"""
Скрипт для загрузки модели SmolVLM-256M-Instruct на хост-машину
После загрузки модель можно скопировать в Docker volume для Docling
"""

import os
import sys
from pathlib import Path

def check_and_install_dependencies():
    """Проверка и установка необходимых зависимостей"""
    print("🔍 Checking dependencies...")

    try:
        import huggingface_hub
        print("   ✅ huggingface_hub installed")
    except ImportError:
        print("   ⚠️  huggingface_hub not found. Installing...")
        os.system("pip install -q huggingface_hub")
        import huggingface_hub

    try:
        import hf_transfer
        print("   ✅ hf_transfer installed")
    except ImportError:
        print("   ⚠️  hf_transfer not found. Installing...")
        os.system("pip install -q hf_transfer")

def download_model(method="direct"):
    """
    Загрузка модели SmolVLM

    Args:
        method: "direct" (напрямую) или "mirror" (через hf-mirror.com)
    """
    from huggingface_hub import snapshot_download

    # Настройки окружения
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "600"
    os.environ["HF_HUB_ETAG_TIMEOUT"] = "600"

    if method == "mirror":
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        print("🌐 Using HF-Mirror endpoint")
    else:
        print("🌐 Using direct Hugging Face connection")

    repo_id = "HuggingFaceTB/SmolVLM-256M-Instruct"
    local_dir = "/tmp/smolvlm_model"

    print(f"\n🔄 Starting download...")
    print(f"📦 Repository: {repo_id}")
    print(f"📂 Download to: {local_dir}")
    print(f"💾 Size: ~513 MB (model.safetensors)")
    print("\n⏳ This may take several minutes depending on your connection...\n")

    try:
        model_path = snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False,  # Копировать файлы, не делать симлинки
            resume_download=True,
            max_workers=2,
        )

        print(f"\n✅ Model successfully downloaded to: {model_path}")
        print(f"\n📊 Downloaded files:")

        # Показываем размеры файлов
        for file_path in Path(local_dir).rglob("*"):
            if file_path.is_file():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                print(f"   - {file_path.name}: {size_mb:.2f} MB")

        return model_path

    except Exception as e:
        print(f"\n❌ Error during download: {e}")
        return None

def show_copy_instructions(model_path):
    """Показать инструкции по копированию модели в Docker volume"""
    if not model_path:
        return

    print("\n" + "="*70)
    print("📋 NEXT STEPS: Copy model to Docling container")
    print("="*70)

    print("\n🔹 Option 1: Copy to Docker volume (Recommended)")
    print("""
# Create volume if not exists:
docker volume create docling_models

# Copy model to volume:
docker run --rm \\
  -v /tmp/smolvlm_model:/host_model:ro \\
  -v docling_models:/container_models \\
  alpine sh -c "cp -r /host_model /container_models/smolvlm"

# Verify:
docker run --rm -v docling_models:/models alpine ls -lah /models/smolvlm
""")

    print("\n🔹 Option 2: Mount directly to Docling container")
    print("""
# Add to docker-compose.override.yml:
  docling:
    volumes:
      - /tmp/smolvlm_model:/models/smolvlm:ro
    environment:
      - DOCLING_SERVE_ARTIFACTS_PATH=/models
""")

    print("\n🔹 Option 3: Copy to container directly")
    print(f"""
docker cp /tmp/smolvlm_model docling:/opt/app-root/src/models/smolvlm
""")

def main():
    """Главная функция"""
    print("="*70)
    print("🚀 SmolVLM-256M-Instruct Downloader")
    print("="*70)
    print()

    # Проверка зависимостей
    check_and_install_dependencies()
    print()

    # Выбор метода загрузки
    print("📥 Choose download method:")
    print("  1) Direct (huggingface.co)")
    print("  2) Mirror (hf-mirror.com)")
    print()

    choice = input("Enter your choice [1/2] (default: 1): ").strip()

    method = "mirror" if choice == "2" else "direct"

    # Загрузка модели
    model_path = download_model(method=method)

    # Инструкции по копированию
    show_copy_instructions(model_path)

    if model_path:
        print("\n✅ Download completed successfully!")
        return 0
    else:
        print("\n❌ Download failed. Please check your internet connection.")
        print("💡 Try using method 2 (Mirror) if you're having connectivity issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
