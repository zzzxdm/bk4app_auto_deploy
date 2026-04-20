# Docker Deploy

## Behavior

- The container starts `scheduler.py`
- The scheduler reads `CRON_SCHEDULE` from `.env`
- Each scheduled run executes `python auto_redeploy.py`
- A health endpoint listens on port `7860`
- `.env` and `deploy_history.json` stay persisted through bind mounts

## Environment

- `CRON_SCHEDULE`: cron expression, default `*/1 * * * *`
- `RUN_ON_STARTUP`: run once immediately after container start, default `false`
- `APP_ID_MAP_JSON`: JSON mapping for multi-app usage, example `{"app1":"env1","app2":"env2"}`
- `PORT`: health port, default `7860`
- `SSL_VERIFY`: HTTPS certificate verification for Back4App API, default `false`
- `REQUEST_TIMEOUT`: request timeout in seconds, default `20`
- `LOG_LEVEL`: log level, default `INFO`

## Start

1. Copy `.env.example` to `.env`
2. Fill `BACK4APP_COOKIE` and related values
3. Run `docker compose up -d --build`

## Health Check

- `GET /`
- `GET /health`
- `GET /healthz`

## Logs

- `docker compose logs -f`

## Stop

- `docker compose down`
