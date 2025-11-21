Итоговый отчёт: Настройка VLM режима для Docling

  ✅ Что сделали:

  1. Настроили прокси-сервер (91.218.140.191):
    - Добавили upstream для cas-bridge.xethub.hf.co (XetHub CDN для Hugging Face)
    - Обновили nginx.conf с правильными маппингами
  2. Обновили docker-compose.override.yml:
    - Добавили cas-bridge.xethub.hf.co в extra_hosts для docling
    - Включили DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true
  3. Попытки загрузки SmolVLM:
    - Пробовали скачать через прокси - зависает на больших .onnx файлах
    - Пробовали зеркало hf-mirror.com - та же проблема
  4. Тестировали Ollama VLM:
    - Предзагрузили llama3.2-vision и granite3.2-vision
    - Настроили Docling для использования Ollama API

  ❌ Текущая проблема:

  Баг в Docling 1.8.0: Несовместимость с Ollama API
  - Ollama возвращает ответ как tuple: ('описание изображения', 5185)
  - Docling ожидает строку для DescriptionAnnotation.text
  - Вызывает Pydantic validation error

  Ошибка:
  Input should be a valid string [type=string_type, input_value=('текст...', число), input_type=tuple]

  ---
  Решения:

  Вариант 1: Дождаться фикса в Docling ⏳

  Создать issue на GitHub: https://github.com/docling-project/docling-serve/issues

  Описать проблему с tuple response от Ollama.

  Вариант 2: Использовать другой VLM сервер 🔄

  Попробовать vLLM вместо Ollama (если доступен), он может возвращать правильный формат.

  Вариант 3: Использовать Docling без VLM (текущее состояние) ✅

  Docling работает отлично для:
  - Извлечения текста из PDF
  - OCR (распознавание текста на изображениях через RapidOCR)
  - Определение структуры документа
  - Извлечение таблиц

  Просто без описания изображений через VLM.

  ---
  Рекомендация:

  На данный момент VLM режим не работает из-за бага в Docling. Рекомендую:

  1. Использовать Docling без VLM - основной функционал работает отлично
  2. Следить за updates Docling - баг известен, может быть исправлен в следующих версиях
  3. Создать issue на GitHub, если хотите ускорить фикс

  Docling готов к работе для обработки документов, просто пока без VLM описания изображений.