#!/usr/bin/env python3
"""
Альтернативный скрипт для загрузки SmolVLM
Загружает файлы НАПРЯМУЮ по HTTP, минуя Git LFS и XetHub CDN
"""

import os
import sys
import requests
from pathlib import Path
from tqdm import tqdm

# Базовый URL для прямых загрузок с Hugging Face
BASE_URL = "https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct/resolve/main"

# Список файлов для загрузки (все необходимые файлы модели)
FILES_TO_DOWNLOAD = [
    # Конфигурационные файлы (маленькие)
    "config.json",
    "generation_config.json",
    "preprocessor_config.json",
    "processor_config.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",

    # Основной файл модели (большой ~513MB)
    "model.safetensors",

    # Vision encoder файлы
    "vision_encoder/config.json",
    "vision_encoder/preprocessor_config.json",
]

def download_file(url, dest_path, use_mirror=False):
    """
    Загрузка файла с прогресс-баром

    Args:
        url: URL файла
        dest_path: Путь для сохранения
        use_mirror: Использовать ли hf-mirror.com
    """
    if use_mirror:
        # Заменяем домен на зеркало
        url = url.replace("https://huggingface.co", "https://hf-mirror.com")

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"📥 Downloading: {dest_path.name}")
    print(f"   URL: {url}")

    try:
        # Проверяем, не загружен ли файл уже
        if dest_path.exists():
            print(f"   ⏭️  File already exists, skipping")
            return True

        # Загружаем с поддержкой возобновления
        headers = {}
        mode = 'wb'
        downloaded_size = 0

        if dest_path.with_suffix(dest_path.suffix + '.partial').exists():
            downloaded_size = dest_path.with_suffix(dest_path.suffix + '.partial').stat().st_size
            headers['Range'] = f'bytes={downloaded_size}-'
            mode = 'ab'
            print(f"   ↻ Resuming from {downloaded_size / (1024*1024):.2f} MB")

        response = requests.get(url, headers=headers, stream=True, timeout=30)

        # Проверяем статус
        if response.status_code not in [200, 206]:  # 206 = Partial Content
            print(f"   ❌ HTTP Error: {response.status_code}")
            return False

        total_size = int(response.headers.get('content-length', 0)) + downloaded_size

        # Загружаем с прогресс-баром
        temp_path = dest_path.with_suffix(dest_path.suffix + '.partial')

        with open(temp_path, mode) as f:
            with tqdm(
                total=total_size,
                initial=downloaded_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc=f"   {dest_path.name}"
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        # Переименовываем после успешной загрузки
        temp_path.rename(dest_path)
        print(f"   ✅ Successfully downloaded")
        return True

    except requests.exceptions.Timeout:
        print(f"   ⏱️  Timeout - connection too slow")
        return False
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Download error: {e}")
        return False
    except KeyboardInterrupt:
        print(f"\n   ⚠️  Download interrupted by user")
        raise
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False

def main():
    """Главная функция"""
    print("="*70)
    print("🚀 SmolVLM Direct HTTP Downloader (без Git LFS)")
    print("="*70)
    print()

    # Выбор метода загрузки
    print("📥 Choose download method:")
    print("  1) Direct Hugging Face (https://huggingface.co)")
    print("  2) HF-Mirror (https://hf-mirror.com)")
    print()

    choice = input("Enter your choice [1/2] (default: 1): ").strip()
    use_mirror = (choice == "2")

    local_dir = Path("/tmp/smolvlm_model")
    local_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 Download directory: {local_dir}")
    print(f"📊 Total files to download: {len(FILES_TO_DOWNLOAD)}")
    print()

    # Загружаем каждый файл
    success_count = 0
    failed_files = []

    for filename in FILES_TO_DOWNLOAD:
        url = f"{BASE_URL}/{filename}"
        dest_path = local_dir / filename

        if download_file(url, dest_path, use_mirror=use_mirror):
            success_count += 1
        else:
            failed_files.append(filename)

        print()

    # Итоговая статистика
    print("="*70)
    print("📊 Download Summary")
    print("="*70)
    print(f"✅ Successfully downloaded: {success_count}/{len(FILES_TO_DOWNLOAD)}")

    if failed_files:
        print(f"❌ Failed to download: {len(failed_files)}")
        for filename in failed_files:
            print(f"   - {filename}")
        print()
        print("💡 Tip: You can run this script again to resume failed downloads")
        return 1
    else:
        print()
        print("🎉 All files downloaded successfully!")
        print()
        print("="*70)
        print("📋 NEXT STEP: Copy model to Docker volume")
        print("="*70)
        print("""
# Create volume:
docker volume create docling_models

# Copy model:
docker run --rm \\
  -v /tmp/smolvlm_model:/host_model:ro \\
  -v docling_models:/container_models \\
  alpine sh -c "cp -r /host_model /container_models/smolvlm"

# Verify:
docker run --rm -v docling_models:/models alpine ls -lah /models/smolvlm
""")
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
        print("💡 You can run this script again to resume")
        sys.exit(130)
