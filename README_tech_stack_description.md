## 📋 Описание ключевых файлов n8n-installer

### 🐳 **docker-compose.yml**
**За что отвечает:** Главный файл конфигурации Docker. Описывает ВСЕ контейнеры, их зависимости, переменные окружения, volumes и профили.

**Ключевые моменты:**
- Каждый сервис имеет параметр `profiles: ["имя-профиля"]` — это определяет, запустится ли контейнер
- Контейнер `caddy` получает переменные окружения для всех hostname'ов сервисов
- Если сервиса нет в этом файле — Docker его не увидит

**Что нужно добавить для нового сервиса:**
```yaml
myservice:
  image: myservice/myservice:latest
  container_name: myservice
  profiles: ["myservice"]  # ← Обязательно!
  restart: unless-stopped
  # НЕ добавляйте ports:, используйте Caddy для проксирования
```

---

### 🌐 **Caddyfile**
**За что отвечает:** Конфигурация обратного прокси-сервера Caddy. Маршрутизирует внешние запросы к внутренним контейнерам и управляет SSL-сертификатами.

**Ключевые моменты:**
- Caddy автоматически получает Let's Encrypt сертификаты для доменов
- Использует переменные окружения вида `{$MYSERVICE_HOSTNAME}`
- Может добавлять Basic Auth через bcrypt-хеши паролей
- Последняя строка `import /etc/caddy/addons/*.conf` позволяет добавлять кастомные конфигурации

**Что нужно добавить для нового сервиса:**
```caddyfile
{$MYSERVICE_HOSTNAME} {
    basic_auth {
        {$MYSERVICE_USERNAME} {$MYSERVICE_PASSWORD_HASH}
    }
    reverse_proxy myservice:8080
}
```

---

### 📄 **.env.example**
**За что отвечает:** Шаблон для файла `.env`. Содержит ВСЕ переменные окружения, которые используются в проекте.

**Ключевые моменты:**
- Это **НЕ** рабочий файл, это шаблон
- Скрипт `03_generate_secrets.sh` использует его для создания `.env`
- Должен содержать все hostname'ы и credentials
- Значения с `yourdomain.com` автоматически заменяются на реальный домен

**Что нужно добавить для нового сервиса:**
```bash
# В секции HOSTNAMES:
MYSERVICE_HOSTNAME=myservice.yourdomain.com

# В секции CREDENTIALS (если нужен Basic Auth):
MYSERVICE_USERNAME=
MYSERVICE_PASSWORD=
MYSERVICE_PASSWORD_HASH=
```

---

### 🔐 **scripts/03_generate_secrets.sh**
**За что отвечает:** Генерирует все секреты, пароли, API ключи и bcrypt-хеши. Создаёт рабочий файл `.env` из `.env.example`.

**Ключевые моменты:**
- Читает существующий `.env` и **сохраняет** уже установленные значения
- Генерирует новые значения только для пустых переменных
- Создаёт bcrypt-хеши для паролей (для Basic Auth в Caddy)
- **ВАЖНО:** Если переменной нет в массиве `VARS_TO_GENERATE`, она не будет сгенерирована автоматически

**Что нужно добавить для нового сервиса:**
```bash
# В массив VARS_TO_GENERATE (строка ~23):
["MYSERVICE_PASSWORD"]="password:32"

# Для username (строка ~259):
generated_values["MYSERVICE_USERNAME"]="$USER_EMAIL"

# Для генерации bcrypt-хеша (после строки ~602):
MYSERVICE_PLAIN_PASS="${generated_values["MYSERVICE_PASSWORD"]}"
FINAL_MYSERVICE_HASH="${generated_values[MYSERVICE_PASSWORD_HASH]}"
if [[ -z "$FINAL_MYSERVICE_HASH" && -n "$MYSERVICE_PLAIN_PASS" ]]; then
    NEW_HASH=$(_generate_and_get_hash "$MYSERVICE_PLAIN_PASS")
    if [[ -n "$NEW_HASH" ]]; then
        FINAL_MYSERVICE_HASH="$NEW_HASH"
        generated_values["MYSERVICE_PASSWORD_HASH"]="$NEW_HASH"
    fi
fi
_update_or_add_env_var "MYSERVICE_PASSWORD_HASH" "$FINAL_MYSERVICE_HASH"

# В массив found_vars (строка ~280):
found_vars["MYSERVICE_USERNAME"]=0

# В массив user_input_vars (строка ~344):
user_input_vars=("... существующие..." "MYSERVICE_USERNAME")

# В цикл добавления кастомных переменных (строка ~426):
for var in "... существующие..." "MYSERVICE_USERNAME"; do
```

---

### 🧙 **scripts/04_wizard.sh**
**За что отвечает:** Интерактивное окно выбора сервисов при установке/обновлении. Записывает выбранные профили в переменную `COMPOSE_PROFILES` в `.env`.

**Ключевые моменты:**
- **ЭТО КЛЮЧЕВОЙ МОМЕНТ!** Если сервиса нет в массиве `base_services_data`, его нельзя выбрать в визарде
- Сервисы с `status="ON"` будут предварительно выбраны
- Результат записывается в `COMPOSE_PROFILES` в `.env`
- Запускается при каждом `install.sh` и `update.sh` (через `apply_update.sh`)

**Что нужно добавить для нового сервиса:**
```bash
# В массив base_services_data (строка ~52):
base_services_data=(
    # ... существующие сервисы ...
    "myservice" "MyService (Краткое описание)"
)
```

**❗ ВАЖНО:** Если вы добавили сервис в `docker-compose.yml`, `.env.example` и `Caddyfile`, но **НЕ** добавили его в `04_wizard.sh` — при следующем запуске визарда он **НЕ** будет в списке выбора, и если пользователь не выберет его вручную (а не сможет, т.к. его там нет), он будет удалён из `COMPOSE_PROFILES`.

---

### 🎯 **scripts/07_final_report.sh**
**За что отвечает:** Выводит итоговый отчёт с URL-адресами, логинами и паролями всех активных сервисов после установки.

**Ключевые моменты:**
- Читает `.env` и проверяет, какие профили активны через функцию `is_profile_active`
- Только информационная функция, не влияет на работу сервисов
- Помогает пользователю не забыть свои credentials

**Что нужно добавить для нового сервиса:**
```bash
# После строки ~326:
if is_profile_active "myservice"; then
  echo
  echo "================================= MyService ==========================="
  echo
  echo "Host: ${MYSERVICE_HOSTNAME:-<hostname_not_set>}"
  echo "User: ${MYSERVICE_USERNAME:-<not_set_in_env>}"
  echo "Password: ${MYSERVICE_PASSWORD:-<not_set_in_env>}"
  echo "API (external): https://${MYSERVICE_HOSTNAME:-<hostname_not_set>}"
  echo "API (internal): http://myservice:8080"
fi
```

---

### 🔄 **scripts/update.sh**
**За что отвечает:** Главный скрипт обновления. Делает `git pull`, обновляет систему и передаёт управление `apply_update.sh`.

**Ключевые моменты:**
- Выполняет `git reset --hard HEAD` и `git pull` — **ВОТ ПРОБЛЕМА!**
- Если вы изменили файлы локально (не закомитили), они будут **затёрты**
- После git pull обновляет системные пакеты
- Затем запускает `apply_update.sh`

**❗ КРИТИЧНО:** Если вы вручную редактировали файлы без коммита, `git reset --hard HEAD` **удалит все ваши изменения**!

---

### 🔄 **scripts/install.sh**
**За что отвечает:** Главный скрипт первичной установки. Последовательно запускает все скрипты от 01 до 07.

**Ключевые моменты:**
- Запускается только один раз при первой установке
- Проходит все этапы: подготовка системы → Docker → генерация секретов → визард → конфигурация → запуск → отчёт
- Не использует git (т.к. предполагается, что репозиторий уже склонирован)
