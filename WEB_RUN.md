# Run web site

1. Add env vars:
- `BOT_TOKEN`
- `DB_URL` (the same value used by bot)
- `SUPERADMIN_IDS` (comma-separated Telegram IDs)
- `WEB_SESSION_SECRET`

2. Install deps:

```bash
pip install -r requirements-web.txt
```

3. Start web app:

```bash
uvicorn web.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Open `http://localhost:8000` and login with Telegram code:
- enter `@username` (or numeric `tg_id`) on site,
- bot sends 6-digit code,
- enter code on site.

The web app and bot use the same DB schema and role sources (`SUPERADMIN_IDS` + `admins` table).
