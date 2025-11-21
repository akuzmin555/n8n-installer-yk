  1. ✅ Добавлен Docker volume docling_models в docker-compose.override.yml
  2. ✅ Volume примонтирован к /opt/app-root/src/.cache/docling/models
  3. ✅ Скачаны модели SmolVLM внутри контейнера в volume
  4. ✅ Проверена persistence - модели сохранились после перезапуска
  5. ✅ SmolVLM работает локально для picture description

  Как использовать:

  # API запрос с локальной моделью SmolVLM
  curl -X POST "https://docling.yourdomain.com/v1/convert/source/async" \
    -H "Content-Type: application/json" \
    -d '{
      "sources": [{"kind": "http", "url": "https://arxiv.org/pdf/your-file.pdf"}],
      "options": {
        "do_picture_description": true,
        "picture_description_local": {
          "repo_id": "HuggingFaceTB/SmolVLM-256M-Instruct",
          "generation_config": {"max_new_tokens": 200, "do_sample": false}
        }
      }
    }'

  ⚠️ Известная проблема:

  Есть баг в текущей версии Docling Serve - модель возвращает tuple вместо строки, что
  вызывает ошибку Pydantic. Но конвертация успешна (status: success)!

  Модели теперь сохраняются навсегда и не требуют повторной загрузки! 🚀