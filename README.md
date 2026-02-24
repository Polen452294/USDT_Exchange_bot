# USDT Exchange Bot (Telegram + VK) + Nudge Worker

Бот собирает заявку на обмен (USDT ↔ наличные), сохраняет её в PostgreSQL и создаёт заявку в CRM.  
Отдельный worker-процесс отвечает за «дожимы» (nudge 1–7) по таймерам и условиям из ТЗ.

## Возможности

- Telegram бот (aiogram): пошаговый сценарий 1–6, сводка, подтверждение/возврат на старт.
- VK бот (LongPoll): аналогичный сценарий на той же БД и сервисном слое.
- PostgreSQL + SQLAlchemy (async).
- Интеграция с CRM (режим `mock` или `real`).
- Worker-процесс: планирование/отправка dожимов 1–7, учёт ответов, защита от повторов.

## Архитектура

- `app/main.py` — Telegram бот
- `app/vk_main.py` — VK бот
- `app/worker_main.py` — worker дожимов
- `app/services/*` — бизнес-логика (draft/request/nudges)
- `app/repositories/*` — доступ к БД
- `app/infrastructure/*` — CRM клиент, отправка сообщений
- `app/models.py` — модели БД

## Требования

- Python 3.12+
- PostgreSQL 14+
- (Опционально) Docker / Docker Compose для удобного старта

## Быстрый старт

### 1) Создать и заполнить `.env`

Скопируйте шаблон:

```bash
cp .env.example .env
```

Заполните минимум:

- `BOT_TOKEN` — токен Telegram бота
- `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`
- `VK_TOKEN` и `VK_GROUP_ID` — если запускаете VK-бота

> Важно: текущая конфигурация приложения читает **нижний регистр** для CRM:  
> `crm_mode`, `crm_base_url`, `crm_token`, `crm_timeout`.  
> В `.env.example` есть и верхний регистр (`CRM_MODE` и т.д.) — используйте нижний регистр, либо продублируйте значения.

### 2) Установить зависимости

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Поднять PostgreSQL

Если Postgres уже есть — пропустите.  
Если используете Docker Compose — смотрите `DEPLOY.md`.

### 4) Запустить процессы

**Telegram бот:**

```bash
python -m app.main
```

**Worker (дожимы):**

```bash
python -m app.worker_main
```

**VK бот (опционально):**

```bash
python -m app.vk_main
```

## Тест-режимы дожимов

В `app/config.py` есть флаги и задержки для быстрого тестирования:

- `nudge2_test_mode`, `nudge2_test_delay_seconds`
- `nudge5_test_mode`, `nudge5_test_delay_seconds`
- `nudge6_test_mode`, `nudge6_test_delay_seconds`
- `nudge7_test_mode`, `nudge7_test_delay_seconds`

Также:
- `nudge_worker_interval_seconds` — период прохода воркера.

Рекомендуемый режим для приёмки:
- тест-режимы включить (для быстрых проверок),
- затем выключить и прогнать сценарий с реальными таймингами/датами.

## Быстрая проверка работоспособности (3–5 шагов)

1) Запустите Postgres, Telegram бот и worker.
2) В Telegram: `/start` → пройти все шаги до сводки → нажать «Да, все отлично».
3) Убедиться, что заявка создалась (по логам) и записалась в БД.
4) Включить тест-режимы dожимов и убедиться, что приходят nudge-сообщения и обрабатываются кнопки.
5) (Опционально) Запустить VK-бота и пройти один полный сценарий.

## Переменные окружения (основные)

Из `.env.example`:

- Telegram:
  - `BOT_TOKEN`

- База данных:
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

- CRM:
  - `crm_mode` (`mock` / `real`)
  - `crm_base_url`
  - `crm_token`
  - `crm_timeout`

- Логи:
  - `LOG_LEVEL`

- Админы:
  - `ADMIN_IDS` — список через запятую/точку с запятой

- VK:
  - `VK_TOKEN`
  - `VK_GROUP_ID`

