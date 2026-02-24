# DEPLOY.md — развёртывание и запуск

## 1) PostgreSQL через Docker Compose

Пример `docker-compose.yml` (в корне проекта):

```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: usdt_exchange
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

Запуск:

```bash
docker compose up -d
```

Проверка:

```bash
docker compose ps
```

## 2) Конфигурация `.env`

Создать `.env` из шаблона:

```bash
cp .env.example .env
```

Заполнить `BOT_TOKEN` и параметры БД.  
Для CRM рекомендуется использовать нижний регистр переменных: `crm_mode`, `crm_base_url`, `crm_token`, `crm_timeout`.

## 3) Запуск в режиме разработки

В отдельных терминалах:

Telegram бот:

```bash
python -m app.main
```

Worker:

```bash
python -m app.worker_main
```

VK бот (опционально):

```bash
python -m app.vk_main
```

## 4) Запуск как сервис (Linux, systemd)

### 4.1 Telegram bot service

`/etc/systemd/system/usdt-bot.service`:

```ini
[Unit]
Description=USDT Exchange Telegram Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/usdt_exchange_bot
EnvironmentFile=/opt/usdt_exchange_bot/.env
ExecStart=/opt/usdt_exchange_bot/.venv/bin/python -m app.main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 4.2 Worker service

`/etc/systemd/system/usdt-worker.service`:

```ini
[Unit]
Description=USDT Exchange Nudge Worker
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/usdt_exchange_bot
EnvironmentFile=/opt/usdt_exchange_bot/.env
ExecStart=/opt/usdt_exchange_bot/.venv/bin/python -m app.worker_main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### 4.3 VK bot service (опционально)

`/etc/systemd/system/usdt-vk.service`:

```ini
[Unit]
Description=USDT Exchange VK Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/usdt_exchange_bot
EnvironmentFile=/opt/usdt_exchange_bot/.env
ExecStart=/opt/usdt_exchange_bot/.venv/bin/python -m app.vk_main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Применение:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now usdt-bot usdt-worker
# VK (если нужно)
sudo systemctl enable --now usdt-vk
```

Логи:

```bash
journalctl -u usdt-bot -f
journalctl -u usdt-worker -f
```

## 5) PM2 (опционально)

PM2 чаще используют для Node.js, но можно и для Python.

Пример:

```bash
pm2 start "python -m app.main" --name usdt-bot
pm2 start "python -m app.worker_main" --name usdt-worker
pm2 save
pm2 startup
```

Рекомендуемый вариант для Linux — systemd.

