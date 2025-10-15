# Карта чистоты — MVP

Telegram-бот + небольшой веб-сервис (карта) для сбора и отображения обращений о проблемах благоустройства.

## Состав

- `bot/` — aiogram 3 (бот: старт, жалоба, профиль, акции)
- `web/` — FastAPI: `/map` (шаблон Leaflet), `/api/reports`
- `db/` — модели и CRUD (SQLite на MVP)
- `services/` — общие сервисы: `mail.py` (SMTP 465/SSL Timeweb), `storage.py`, `crypto.py`
- `ops/` — systemd-юниты и скрипт деплоя
- `docs/` — концепция и дизайн-гайд (для истории)

## Требования

- Python **3.12**
- Git, make (опц.)
- Linux/WSL/macOS
- Порт 465 для исходящей почты открыт на хостинге (SMTP Timeweb по SSL)

## Быстрый старт (локально)

```bash
git clone <repo-url> karta-clean
cd karta-clean

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
mkdir -p data/photos

# Отредактируй .env (BOT_TOKEN, SMTP_*, DB_URL и т.д.)

# Инициализация БД (создаст SQLite-файл)
python -m db.init_db

# Запуск бота (polling)
python -m bot.main

# Запуск веб-сервиса (в другом терминале)
uvicorn web.main:app --reload --host 0.0.0.0 --port 8000
```

Открой:
- Бот — в Telegram по своему токену
- Карту — http://127.0.0.1:8000/map

## Деплой на VPS (Timeweb Cloud)

1. Установи системные зависимости:
   ```bash
   sudo apt update && sudo apt install -y python3.12 python3.12-venv git
   ```
2. Клонируй репозиторий в `/opt/karta-clean`, создай `.venv`, установи зависимости, подготовь `.env` и папку `data/photos`.
3. Инициализируй БД:
   ```bash
   /opt/karta-clean/.venv/bin/python -m db.init_db
   ```
4. Скопируй `ops/systemd/tg-bot.service` и `ops/systemd/karta-web.service` в `/etc/systemd/system/`, заполни `User`, `WorkingDirectory`, пути к питону и т.д.
5. Запусти сервисы:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now tg-bot
   sudo systemctl enable --now karta-web
   ```
6. Для обновлений используй `ops/deploy.sh` (git pull → pip install → restart).

## Ветки и коммиты

- `main` — прод (мы работаем сразу здесь на MVP).
- `feature/<...>` — фичи через PR приветствуются.

**Conventional Commits**:
- `feat:`, `fix:`, `docs:`, `refactor:`, `chore:` и т.д.  
Пример: `feat(bot): report flow (photo+text+address)`

## Замечания по почте

Предыдущая проблема была связана с `SMTPConnectTimeoutError` на `smtp.yandex.com:587`.  
В этом проекте используем **Timeweb SMTP по 465/SSL** и прямое соединение через `smtplib.SMTP_SSL`, чтобы избежать таймаутов и требований STARTTLS.

## Лицензия

MIT (опционально).
