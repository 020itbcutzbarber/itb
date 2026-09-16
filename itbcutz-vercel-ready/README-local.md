# ITBCUTZ website

Full-stack website for ITBCUTZ with customer accounts, appointments, subscriptions, reviews, gallery management, services/prices, contact/settings and a private admin dashboard.

## Run locally

Use the bundled Python from Codex if normal `python` is not installed:

```powershell
$env:ITBCUTZ_SECRET="replace-with-a-long-random-secret"
$env:ADMIN_EMAIL="admin@itbcutz.nl"
$env:ADMIN_PASSWORD="Admin123!"
& "C:\Users\balta\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\server.py
```

Open `http://localhost:8000`.

Default admin login, unless overridden by env vars:

- Email: `admin@itbcutz.nl`
- Password: `Admin123!`

## External integrations

No secrets are stored in frontend code. Configure these environment variables on the server when available:

- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` for email.
- `WHATSAPP_API_URL`, `WHATSAPP_API_TOKEN` for WhatsApp confirmations.
- `BASE_URL` for sitemap and email links.

SQLite data is stored at `data/itbcutz.sqlite3`; uploads are stored in `static/uploads`.
