# Deploy on Render

## What this setup creates

- `reminder-bot-web`: Django admin and HTTP app
- `reminder-bot-worker`: Telegram bot long polling worker
- `reminder-bot-db`: Render Postgres database

## One important note about media files

The web service and the worker run as separate services on Render.
They do not share a local filesystem.

This means:

- SQLite is not suitable for production here, so this project is configured for `DATABASE_URL` and Postgres.
- Local media files are also not shared between services.

If you want uploaded files to work correctly in production for both services, set up S3-compatible storage and add these environment variables to both Render services:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_REGION_NAME`
- `AWS_S3_ENDPOINT_URL`

Optional:

- `AWS_S3_CUSTOM_DOMAIN`

If you skip S3 storage, text-only flows will work, but uploaded files and media shared between web and worker can break.

## Deploy steps

1. Push this repository to GitHub.
2. In Render, create a new Blueprint.
3. Point it to this repo so Render reads `render.yaml`.
4. During setup, enter `TELEGRAM_BOT_TOKEN` for both services.
5. After deploy, open the web service shell or local project and create an admin user:

```bash
python manage.py createsuperuser
```

## Useful paths

- Admin: `/admin/`
- Bot webhook path if you later switch from polling: `/bot/webhook/`
