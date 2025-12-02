# Fix для crash loop: open-webui и flowise

## 🔍 Анализ проблемы

### open-webui: SEGFAULT (Exit 139)
**Причина:** Segmentation fault в `libtorch_cpu.so` (PyTorch)

**Возможные причины:**
1. Недостаток shared memory для PyTorch операций
2. Конфликт между GPU и CPU версиями PyTorch
3. Проблемы с векторными инструкциями процессора (AVX/AVX2)

### flowise: Поврежденные файлы
**Причина:** Файлы в `~/.flowise` повреждены из-за crash loop open-webui

**Доказательство:** `Error parsing .../is-wsl/package.json: Unexpected non-whitespace character`

---

## ✅ РЕШЕНИЕ

### Шаг 1: НЕМЕДЛЕННО ОСТАНОВИТЬ ПРОБЛЕМНЫЕ КОНТЕЙНЕРЫ

```bash
# Остановить оба контейнера
docker stop open-webui flowise

# Запретить автоперезапуск (чтобы защитить файловую систему)
docker update --restart=no open-webui flowise
```

---

### Шаг 2: ИСПРАВИТЬ FLOWISE (Поврежденные файлы)

**Вариант A: Очистить поврежденную директорию**
```bash
# Сделать бэкап на всякий случай
sudo mv ~/.flowise ~/.flowise.corrupted.backup

# Удалить контейнер
docker rm flowise

# Пересоздать контейнер (он создаст новую чистую директорию)
docker compose -p localai up -d flowise

# Проверить логи
docker compose -p localai logs -f flowise
```

**Вариант B: Переключить на Docker volume (рекомендуется)**

Нужно изменить `docker-compose.yml`:
```yaml
# БЫЛО:
volumes:
  - ~/.flowise:/root/.flowise

# СТАЛО:
volumes:
  - flowise:/root/.flowise  # Использует Docker volume (уже есть в списке volumes)
```

Затем:
```bash
# Удалить старый контейнер
docker rm flowise

# Пересоздать с новым volume
docker compose -p localai up -d flowise
```

---

### Шаг 3: ИСПРАВИТЬ OPEN-WEBUI (SEGFAULT)

**Проблема:** Недостаток shared memory для PyTorch

**Решение:** Добавить `shm_size` в `docker-compose.override.yml`

Добавьте в секцию `open-webui`:
```yaml
services:
  open-webui:
    shm_size: 2g  # Увеличить shared memory для PyTorch/векторных операций
    environment:
      - RAG_EMBEDDING_ENGINE=ollama
      # Добавьте эти переменные для стабильности:
      - VECTOR_DB=chroma  # Или другая база
      - ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION=false
```

**Альтернатива:** Если проблема с GPU, попробуйте CPU-only режим:
```yaml
services:
  open-webui:
    shm_size: 2g
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - RAG_EMBEDDING_ENGINE=ollama
      - USE_CUDA_DOCKER=false  # Отключить CUDA если проблема с GPU
```

Затем:
```bash
# Удалить старый контейнер
docker rm open-webui

# Пересоздать с новыми настройками
docker compose -p localai up -d open-webui

# Следить за логами в реальном времени
docker compose -p localai logs -f open-webui
```

---

### Шаг 4: ПРОВЕРКА РАБОТОСПОСОБНОСТИ

```bash
# Проверить статус контейнеров
docker ps -a --filter "name=open-webui" --filter "name=flowise"

# Проверить логи flowise
docker compose -p localai logs --tail=100 flowise

# Проверить логи open-webui
docker compose -p localai logs --tail=100 open-webui

# Проверить healthchecks (если есть)
docker inspect open-webui --format='{{.State.Health.Status}}'
docker inspect flowise --format='{{.State.Health.Status}}'
```

---

## 🔧 ДОПОЛНИТЕЛЬНАЯ ДИАГНОСТИКА

### Если open-webui продолжает крашиться:

**Проверить ограничения памяти:**
```bash
# Проверить доступную память
free -h

# Проверить Docker stats в реальном времени
docker stats open-webui flowise
```

**Проверить логи ядра (для segfault):**
```bash
# Последние segfault в системных логах
dmesg | grep -i "segfault\|killed\|oom" | tail -50

# Или через journalctl
journalctl -xe | grep -i "segfault"
```

**Попробовать другой образ open-webui:**
```yaml
services:
  open-webui:
    # Вместо :main попробуйте stable версию
    image: ghcr.io/open-webui/open-webui:latest  # Стабильная версия
    # или
    image: ghcr.io/open-webui/open-webui:0.3.32  # Конкретная версия
```

---

## 📝 ИТОГОВАЯ ПОСЛЕДОВАТЕЛЬНОСТЬ КОМАНД

```bash
# 1. ОСТАНОВИТЬ И ЗАПРЕТИТЬ ПЕРЕЗАПУСК
docker stop open-webui flowise
docker update --restart=no open-webui flowise

# 2. БЭКАП ПОВРЕЖДЕННЫХ ДАННЫХ FLOWISE
sudo mv ~/.flowise ~/.flowise.corrupted.backup

# 3. УДАЛИТЬ СТАРЫЕ КОНТЕЙНЕРЫ
docker rm open-webui flowise

# 4. ПРИМЕНИТЬ ИСПРАВЛЕНИЯ в docker-compose.override.yml
# (см. Шаг 3 выше - добавить shm_size для open-webui)

# 5. ПЕРЕСОЗДАТЬ КОНТЕЙНЕРЫ
docker compose -p localai up -d open-webui flowise

# 6. СЛЕДИТЬ ЗА ЛОГАМИ
docker compose -p localai logs -f open-webui flowise
```

---

## ⚠️ ВАЖНО

1. **НЕ ЗАПУСКАЙТЕ** update.sh или install.sh до исправления - это может затереть ваши изменения!
2. **СДЕЛАЙТЕ КОММИТ** всех изменений перед запуском update.sh
3. Если проблема повторяется, возможно нужно:
   - Обновить образ open-webui
   - Проверить совместимость с вашим GPU
   - Увеличить shm_size до 4g или больше
