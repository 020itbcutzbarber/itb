# ITBCUTZ Vercel map

Upload deze hele map naar GitHub en importeer die repo in Vercel.

## Belangrijk

Deze map is klaar om de site makkelijk op Vercel te zetten, maar Vercel bewaart zelf geen SQLite database en uploads blijvend.

Dat betekent:

- De website kan online openen.
- Login/admin/API kunnen als demo werken.
- Echte klantgegevens, afspraken, uploads en reviews moeten voor live gebruik naar een vaste database/opslag.

Voor live gebruik heb je later nodig:

- Database: Vercel Postgres, Supabase of Neon.
- Foto-opslag: Vercel Blob, Supabase Storage of Cloudinary.
- E-mail: SMTP gegevens.
- WhatsApp: WhatsApp Business API gegevens.

## Environment variables in Vercel

Zet minimaal:

- `ITBCUTZ_SECRET`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `BASE_URL`

Voor e-mail:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

Voor WhatsApp:

- `WHATSAPP_API_URL`
- `WHATSAPP_API_TOKEN`

## Lokaal testen

```powershell
python server.py
```

Open daarna `http://localhost:8000`.
