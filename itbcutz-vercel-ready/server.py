import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import smtplib
import sqlite3
import ssl
import threading
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
UPLOADS = Path(os.getenv("ITBCUTZ_UPLOAD_DIR", str(STATIC / "uploads")))
DB_PATH = Path(os.getenv("ITBCUTZ_DB_PATH", str(ROOT / "data" / "itbcutz.sqlite3")))
SECRET = os.getenv("ITBCUTZ_SECRET", "dev-change-this-secret")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@itbcutz.nl").lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

UPLOADS.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def today_iso():
    return datetime.utcnow().date().isoformat()


def add_months(date_str, months):
    d = datetime.fromisoformat(date_str)
    month = d.month - 1 + int(months)
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return d.replace(year=year, month=month, day=day).date().isoformat()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 220000).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(password_hash(password, salt), stored)


def sign(value):
    sig = hmac.new(SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}.{sig}"


def unsign(value):
    if not value or "." not in value:
        return None
    raw, sig = value.rsplit(".", 1)
    expected = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return raw if hmac.compare_digest(sig, expected) else None


def rowdict(row):
    return dict(row) if row else None


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  first_name TEXT NOT NULL,
  last_name TEXT DEFAULT '',
  phone TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'customer',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS services (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name_nl TEXT NOT NULL,
  name_en TEXT NOT NULL,
  price_cents INTEGER NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS appointments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  phone TEXT NOT NULL,
  service_id INTEGER REFERENCES services(id),
  service_name TEXT NOT NULL,
  date TEXT NOT NULL,
  time TEXT NOT NULL,
  note TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'In afwachting',
  subscription_id INTEGER,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subscription_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name_nl TEXT NOT NULL,
  name_en TEXT NOT NULL,
  months INTEGER NOT NULL,
  price_cents INTEGER NOT NULL,
  featured INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS subscriptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  plan_id INTEGER NOT NULL REFERENCES subscription_plans(id),
  status TEXT NOT NULL DEFAULT 'Betaling in afwachting',
  start_date TEXT,
  end_date TEXT,
  created_at TEXT NOT NULL,
  accepted_at TEXT,
  expiry_notice_sent INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  appointment_id INTEGER UNIQUE NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
  text TEXT NOT NULL,
  photo_url TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'In afwachting',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gallery (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  image_url TEXT NOT NULL,
  alt_nl TEXT NOT NULL,
  alt_en TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contact (
  id INTEGER PRIMARY KEY CHECK(id = 1),
  snapchat TEXT DEFAULT '',
  whatsapp TEXT DEFAULT '',
  phone TEXT DEFAULT '',
  email TEXT DEFAULT '',
  location TEXT DEFAULT 'Amsterdam-West',
  text_nl TEXT DEFAULT '',
  text_en TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
        if not conn.execute("SELECT id FROM users WHERE role='admin'").fetchone():
            conn.execute(
                "INSERT INTO users(first_name,last_name,phone,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?,?)",
                ("Admin", "", "", ADMIN_EMAIL, password_hash(ADMIN_PASSWORD), "admin", now_iso()),
            )
        if conn.execute("SELECT COUNT(*) c FROM services").fetchone()["c"] == 0:
            services = [
                ("Fade / Taper / Overloop / Burst Fade etc.", "Fade / Taper / Blend / Burst Fade etc.", 1000, 1),
                ("Baard", "Beard", 250, 2),
                ("Knippen + Baard", "Haircut + Beard", 1250, 3),
                ("Design lijnen", "Design lines", 500, 4),
                ("Kinderen onder 13 jaar, inclusief alles", "Kids under 13, everything included", 500, 5),
            ]
            conn.executemany("INSERT INTO services(name_nl,name_en,price_cents,sort_order) VALUES(?,?,?,?)", services)
        if conn.execute("SELECT COUNT(*) c FROM subscription_plans").fetchone()["c"] == 0:
            plans = [("1 maand", "1 month", 1, 3000, 0), ("2 maanden", "2 months", 2, 5000, 1), ("3 maanden", "3 months", 3, 7000, 0)]
            conn.executemany("INSERT INTO subscription_plans(name_nl,name_en,months,price_cents,featured) VALUES(?,?,?,?,?)", plans)
        if not conn.execute("SELECT id FROM contact WHERE id=1").fetchone():
            conn.execute(
                "INSERT INTO contact(id,snapchat,whatsapp,phone,email,location,text_nl,text_en) VALUES(1,?,?,?,?,?,?,?)",
                ("itbcutz", "+31600000000", "+31600000000", "info@itbcutz.nl", "Amsterdam-West", "Stuur gerust een bericht voor vragen of om je afspraak af te stemmen.", "Send a message for questions or to coordinate your appointment."),
            )
        defaults = {
            "slogan_nl": "Strakke fades, scherpe lijnen, persoonlijke service.",
            "slogan_en": "Clean fades, sharp lines, personal service.",
            "about_nl": "ITBCUTZ is mijn barberbedrijf in Amsterdam-West. Ik werk vanuit mijn eigen barberruimte/schuur en focus vooral op fades, overgangen, lijnen en baarden. Persoonlijke service, goede sfeer en strak werk staan centraal. Alleen op afspraak.",
            "about_en": "ITBCUTZ is my barber business in Amsterdam-West. I work from my own private barber space and focus on fades, blends, line-ups and beards. Personal service, a good vibe and clean work come first. Appointment only.",
        }
        for key, value in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (key, value))
        if conn.execute("SELECT COUNT(*) c FROM gallery").fetchone()["c"] == 0:
            for i, cat in enumerate(["Taper Fade", "Burst Fade", "Overloop", "Baard", "Andere cuts"], start=1):
                conn.execute(
                    "INSERT INTO gallery(category,title,image_url,alt_nl,alt_en,sort_order,created_at) VALUES(?,?,?,?,?,?,?)",
                    (cat, cat, f"/static/images/cut-{i}.svg", f"ITBCUTZ voorbeeld: {cat}", f"ITBCUTZ example: {cat}", i, now_iso()),
                )


def current_user(handler):
    jar = cookies.SimpleCookie(handler.headers.get("Cookie", ""))
    token = jar.get("itb_session")
    uid = unsign(token.value) if token else None
    if not uid:
        return None
    with db() as conn:
        return rowdict(conn.execute("SELECT id,first_name,last_name,phone,email,role,created_at FROM users WHERE id=?", (uid,)).fetchone())


def send_email(to, subject, body):
    host = os.getenv("SMTP_HOST")
    if not host:
        print(f"[email pending config] to={to} subject={subject} body={body[:120]}")
        return False
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", "ITBCUTZ <noreply@itbcutz.nl>")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if user and password:
            smtp.login(user, password)
        smtp.send_message(msg)
    return True


def send_whatsapp(phone, message):
    api_url = os.getenv("WHATSAPP_API_URL")
    token = os.getenv("WHATSAPP_API_TOKEN")
    if not api_url or not token:
        print(f"[whatsapp pending config] to={phone} message={message[:120]}")
        return False
    import urllib.request
    payload = json.dumps({"to": phone, "message": message}).encode()
    req = urllib.request.Request(api_url, data=payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=15).read()
    return True


def save_data_url(data_url, prefix):
    if not data_url:
        return ""
    header, encoded = data_url.split(",", 1)
    ext = "jpg"
    if "png" in header:
        ext = "png"
    elif "webp" in header:
        ext = "webp"
    name = f"{prefix}-{secrets.token_hex(10)}.{ext}"
    path = UPLOADS / name
    path.write_bytes(base64.b64decode(encoded))
    return f"/static/uploads/{name}"


def public_data(user=None):
    with db() as conn:
        services = rows(conn.execute("SELECT * FROM services WHERE active=1 ORDER BY sort_order,id"))
        plans = rows(conn.execute("SELECT * FROM subscription_plans WHERE active=1 ORDER BY months"))
        gallery = rows(conn.execute("SELECT * FROM gallery ORDER BY sort_order,id"))
        contact = rowdict(conn.execute("SELECT * FROM contact WHERE id=1").fetchone())
        settings = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM settings")}
        reviews = rows(conn.execute(
            """SELECT reviews.*, users.first_name, users.last_name
               FROM reviews JOIN users ON users.id=reviews.user_id
               WHERE reviews.status='Goedgekeurd' ORDER BY reviews.created_at DESC"""
        ))
    for s in services:
        s["price"] = s["price_cents"] / 100
    for p in plans:
        p["price"] = p["price_cents"] / 100
    for r in reviews:
        last = (r.get("last_name") or "").strip()
        r["display_name"] = f"{r['first_name']} {last[:1]}.".strip() if last else r["first_name"]
    return {"services": services, "plans": plans, "gallery": gallery, "contact": contact, "settings": settings, "reviews": reviews, "user": user}


def require_user(handler, admin=False):
    user = current_user(handler)
    if not user or (admin and user["role"] != "admin"):
        handler.json({"error": "Unauthorized"}, 401)
        return None
    return user


def notify_appointment(conn, appointment_id, status):
    appt = rowdict(conn.execute(
        """SELECT appointments.*, users.email, users.first_name
           FROM appointments JOIN users ON users.id=appointments.user_id WHERE appointments.id=?""",
        (appointment_id,),
    ).fetchone())
    if not appt:
        return
    if status == "Bevestigd":
        body = f"Hi {appt['first_name']}, je afspraak bij ITBCUTZ op {appt['date']} om {appt['time']} is bevestigd. Tot dan."
        send_email(appt["email"], "ITBCUTZ afspraak bevestigd", body)
        send_whatsapp(appt["phone"], body)
    elif status == "Afgewezen":
        send_email(appt["email"], "ITBCUTZ afspraak afgewezen", f"Hi {appt['first_name']}, je afspraakaanvraag voor {appt['date']} om {appt['time']} is helaas afgewezen. Stuur gerust een bericht om een ander moment af te stemmen.")
    elif status == "Voltooid":
        send_email(appt["email"], "Hoe was je afspraak bij ITBCUTZ?", f"Hi {appt['first_name']}, bedankt voor je bezoek. Laat een review achter via je account: {BASE_URL}/account")


def active_subscription(conn, user_id):
    return rowdict(conn.execute(
        "SELECT * FROM subscriptions WHERE user_id=? AND status='Actief' AND date(end_date) >= date('now') ORDER BY end_date DESC LIMIT 1",
        (user_id,),
    ).fetchone())


def admin_payload():
    with db() as conn:
        stats = {
            "newAppointments": conn.execute("SELECT COUNT(*) c FROM appointments WHERE status='In afwachting'").fetchone()["c"],
            "confirmedAppointments": conn.execute("SELECT COUNT(*) c FROM appointments WHERE status='Bevestigd'").fetchone()["c"],
            "pendingSubscriptions": conn.execute("SELECT COUNT(*) c FROM subscriptions WHERE status='Betaling in afwachting'").fetchone()["c"],
            "activeSubscriptions": conn.execute("SELECT COUNT(*) c FROM subscriptions WHERE status='Actief'").fetchone()["c"],
            "newReviews": conn.execute("SELECT COUNT(*) c FROM reviews WHERE status='In afwachting'").fetchone()["c"],
            "openPayments": conn.execute("SELECT COUNT(*) c FROM subscriptions WHERE status='Betaling in afwachting'").fetchone()["c"],
        }
        appointments = rows(conn.execute("""SELECT appointments.*, users.first_name, users.last_name, users.email
          FROM appointments JOIN users ON users.id=appointments.user_id ORDER BY appointments.created_at DESC"""))
        subscriptions = rows(conn.execute("""SELECT subscriptions.*, users.first_name, users.last_name, users.email, subscription_plans.name_nl, subscription_plans.months,
          (SELECT COUNT(*) FROM appointments WHERE appointments.subscription_id=subscriptions.id) used_count
          FROM subscriptions JOIN users ON users.id=subscriptions.user_id JOIN subscription_plans ON subscription_plans.id=subscriptions.plan_id
          ORDER BY subscriptions.created_at DESC"""))
        customers = rows(conn.execute("""SELECT users.*, 
          (SELECT COUNT(*) FROM appointments WHERE appointments.user_id=users.id) appointment_count
          FROM users WHERE role='customer' ORDER BY created_at DESC"""))
        reviews = rows(conn.execute("""SELECT reviews.*, users.first_name, users.last_name, appointments.date
          FROM reviews JOIN users ON users.id=reviews.user_id JOIN appointments ON appointments.id=reviews.appointment_id
          ORDER BY reviews.created_at DESC"""))
    payload = public_data()
    payload.update({"stats": stats, "appointments": appointments, "subscriptions": subscriptions, "customers": customers, "adminReviews": reviews})
    return payload


def expire_and_remind():
    while True:
        try:
            with db() as conn:
                conn.execute("UPDATE subscriptions SET status='Verlopen' WHERE status='Actief' AND date(end_date) < date('now')")
                due = rows(conn.execute("""SELECT subscriptions.*, users.email, users.first_name FROM subscriptions
                  JOIN users ON users.id=subscriptions.user_id
                  WHERE subscriptions.status='Actief' AND expiry_notice_sent=0 AND date(end_date)=date('now','+3 day')"""))
                for sub in due:
                    send_email(sub["email"], "Je ITBCUTZ abonnement verloopt bijna", f"Hi {sub['first_name']}, je abonnement verloopt op {sub['end_date']}.")
                    conn.execute("UPDATE subscriptions SET expiry_notice_sent=1 WHERE id=?", (sub["id"],))
        except Exception as exc:
            print("[scheduler]", exc)
        time.sleep(60 * 60)


class App(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def json(self, payload, status=200, headers=None):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode())

    def do_GET(self):
        user = current_user(self)
        path = urlparse(self.path).path
        if path == "/api/bootstrap":
            self.json(public_data(user))
            return
        if path == "/api/account":
            user = require_user(self)
            if not user:
                return
            with db() as conn:
                appointments = rows(conn.execute("SELECT * FROM appointments WHERE user_id=? ORDER BY date DESC,time DESC", (user["id"],)))
                subscriptions = rows(conn.execute("""SELECT subscriptions.*, subscription_plans.name_nl, subscription_plans.name_en, subscription_plans.months, subscription_plans.price_cents,
                  (SELECT COUNT(*) FROM appointments WHERE subscription_id=subscriptions.id) used_count
                  FROM subscriptions JOIN subscription_plans ON subscription_plans.id=subscriptions.plan_id
                  WHERE user_id=? ORDER BY created_at DESC""", (user["id"],)))
                reviewable = rows(conn.execute("""SELECT appointments.* FROM appointments LEFT JOIN reviews ON reviews.appointment_id=appointments.id
                  WHERE appointments.user_id=? AND appointments.status='Voltooid' AND reviews.id IS NULL ORDER BY appointments.date DESC""", (user["id"],)))
            self.json({"user": user, "appointments": appointments, "subscriptions": subscriptions, "reviewable": reviewable})
            return
        if path == "/api/admin":
            if not require_user(self, admin=True):
                return
            self.json(admin_payload())
            return
        if path == "/sitemap.xml":
            urls = ["", "prijzen", "galerij", "abonnementen", "contact", "afspraak-maken", "login"]
            xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">" + "".join([f"<url><loc>{BASE_URL}/{u}</loc></url>" for u in urls]) + "</urlset>"
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(xml.encode())
            return
        self.serve_static(path)

    def serve_static(self, path):
        if path.startswith("/static/uploads/") and (UPLOADS / Path(path).name).exists():
            file_path = UPLOADS / Path(path).name
        elif path.startswith("/static/"):
            file_path = (ROOT / path.lstrip("/")).resolve()
            if not str(file_path).startswith(str(STATIC.resolve())) or not file_path.exists():
                self.send_error(404)
                return
        else:
            file_path = STATIC / "index.html"
        data = file_path.read_bytes()
        ctype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "public, max-age=3600" if path.startswith("/static/") else "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/register":
                data = self.read_json()
                with db() as conn:
                    cur = conn.execute("INSERT INTO users(first_name,last_name,phone,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?,?)",
                        (data["first_name"].strip(), data.get("last_name", "").strip(), data["phone"].strip(), data["email"].lower().strip(), password_hash(data["password"]), "customer", now_iso()))
                self.json({"ok": True}, 201, {"Set-Cookie": f"itb_session={sign(str(cur.lastrowid))}; HttpOnly; SameSite=Lax; Path=/"})
                return
            if path == "/api/login":
                data = self.read_json()
                with db() as conn:
                    user = rowdict(conn.execute("SELECT * FROM users WHERE email=?", (data["email"].lower().strip(),)).fetchone())
                if not user or not verify_password(data["password"], user["password_hash"]):
                    self.json({"error": "Ongeldige login"}, 401)
                    return
                self.json({"ok": True, "role": user["role"]}, 200, {"Set-Cookie": f"itb_session={sign(str(user['id']))}; HttpOnly; SameSite=Lax; Path=/"})
                return
            if path == "/api/logout":
                self.json({"ok": True}, 200, {"Set-Cookie": "itb_session=; Max-Age=0; Path=/; SameSite=Lax; HttpOnly"})
                return
            if path == "/api/profile":
                user = require_user(self)
                if not user:
                    return
                data = self.read_json()
                with db() as conn:
                    conn.execute("UPDATE users SET first_name=?, last_name=?, phone=?, email=? WHERE id=?",
                        (data["first_name"].strip(), data.get("last_name", "").strip(), data["phone"].strip(), data["email"].lower().strip(), user["id"]))
                self.json({"ok": True})
                return
            if path == "/api/appointments":
                user = require_user(self)
                if not user:
                    return
                data = self.read_json()
                with db() as conn:
                    service = rowdict(conn.execute("SELECT * FROM services WHERE id=?", (data["service_id"],)).fetchone())
                    if not service:
                        self.json({"error": "Service niet gevonden"}, 400)
                        return
                    sub_id = None
                    if data.get("pay_with_subscription"):
                        sub = active_subscription(conn, user["id"])
                        if not sub:
                            self.json({"error": "Geen actief abonnement"}, 400)
                            return
                        sub_id = sub["id"]
                    conn.execute("""INSERT INTO appointments(user_id,phone,service_id,service_name,date,time,note,status,subscription_id,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?)""", (user["id"], data["phone"].strip(), service["id"], service["name_nl"], data["date"], data["time"], data.get("note", ""), "In afwachting", sub_id, now_iso()))
                self.json({"ok": True}, 201)
                return
            if path == "/api/subscriptions":
                user = require_user(self)
                if not user:
                    return
                data = self.read_json()
                with db() as conn:
                    if active_subscription(conn, user["id"]):
                        self.json({"error": "Je hebt al een actief abonnement"}, 400)
                        return
                    conn.execute("INSERT INTO subscriptions(user_id,plan_id,status,created_at) VALUES(?,?,?,?)",
                        (user["id"], data["plan_id"], "Betaling in afwachting", now_iso()))
                self.json({"ok": True}, 201)
                return
            if path == "/api/reviews":
                user = require_user(self)
                if not user:
                    return
                data = self.read_json()
                with db() as conn:
                    appt = rowdict(conn.execute("SELECT * FROM appointments WHERE id=? AND user_id=? AND status='Voltooid'", (data["appointment_id"], user["id"])).fetchone())
                    if not appt:
                        self.json({"error": "Afspraak niet beschikbaar voor review"}, 400)
                        return
                    photo = save_data_url(data.get("photo", ""), "review")
                    conn.execute("INSERT INTO reviews(appointment_id,user_id,stars,text,photo_url,status,created_at) VALUES(?,?,?,?,?,?,?)",
                        (appt["id"], user["id"], int(data["stars"]), data["text"].strip(), photo, "In afwachting", now_iso()))
                self.json({"ok": True}, 201)
                return
            if path.startswith("/api/admin/"):
                self.admin_post(path)
                return
            self.send_error(404)
        except sqlite3.IntegrityError as exc:
            self.json({"error": "Deze actie kon niet worden opgeslagen. Controleer dubbele gegevens of bestaande records."}, 400)
        except Exception as exc:
            self.json({"error": str(exc)}, 500)

    def admin_post(self, path):
        user = require_user(self, admin=True)
        if not user:
            return
        data = self.read_json()
        with db() as conn:
            if path == "/api/admin/appointment-status":
                status = data["status"]
                if status == "Bevestigd":
                    appt = rowdict(conn.execute("SELECT * FROM appointments WHERE id=?", (data["id"],)).fetchone())
                    clash = conn.execute("SELECT id FROM appointments WHERE status='Bevestigd' AND date=? AND time=? AND id<>?", (appt["date"], appt["time"], appt["id"])).fetchone()
                    if clash:
                        self.json({"error": "Er is al een bevestigde afspraak op dit tijdstip."}, 409)
                        return
                conn.execute("UPDATE appointments SET status=? WHERE id=?", (status, data["id"]))
                notify_appointment(conn, data["id"], status)
            elif path == "/api/admin/subscription-accept":
                sub = rowdict(conn.execute("SELECT * FROM subscriptions WHERE id=?", (data["id"],)).fetchone())
                if active_subscription(conn, sub["user_id"]):
                    self.json({"error": "Deze klant heeft al een actief abonnement."}, 409)
                    return
                plan = rowdict(conn.execute("SELECT * FROM subscription_plans WHERE id=?", (sub["plan_id"],)).fetchone())
                start = today_iso()
                end = add_months(start, plan["months"])
                conn.execute("UPDATE subscriptions SET status='Actief', start_date=?, end_date=?, accepted_at=? WHERE id=?", (start, end, now_iso(), sub["id"]))
                customer = rowdict(conn.execute("SELECT * FROM users WHERE id=?", (sub["user_id"],)).fetchone())
                send_email(customer["email"], "ITBCUTZ abonnement actief", f"Hi {customer['first_name']}, je abonnement is actief van {start} tot {end}.")
            elif path == "/api/admin/subscription-status":
                conn.execute("UPDATE subscriptions SET status=? WHERE id=?", (data["status"], data["id"]))
            elif path == "/api/admin/review":
                conn.execute("UPDATE reviews SET status=?, stars=?, text=? WHERE id=?", (data["status"], int(data["stars"]), data["text"].strip(), data["id"]))
            elif path == "/api/admin/review-delete":
                conn.execute("DELETE FROM reviews WHERE id=?", (data["id"],))
            elif path == "/api/admin/gallery-save":
                image_url = data.get("image_url") or save_data_url(data.get("image", ""), "gallery")
                if data.get("id"):
                    if data.get("image"):
                        conn.execute("UPDATE gallery SET category=?, title=?, image_url=?, alt_nl=?, alt_en=?, sort_order=? WHERE id=?", (data["category"], data["title"], image_url, data["alt_nl"], data["alt_en"], int(data["sort_order"]), data["id"]))
                    else:
                        conn.execute("UPDATE gallery SET category=?, title=?, alt_nl=?, alt_en=?, sort_order=? WHERE id=?", (data["category"], data["title"], data["alt_nl"], data["alt_en"], int(data["sort_order"]), data["id"]))
                else:
                    conn.execute("INSERT INTO gallery(category,title,image_url,alt_nl,alt_en,sort_order,created_at) VALUES(?,?,?,?,?,?,?)", (data["category"], data["title"], image_url, data["alt_nl"], data["alt_en"], int(data["sort_order"]), now_iso()))
            elif path == "/api/admin/gallery-delete":
                conn.execute("DELETE FROM gallery WHERE id=?", (data["id"],))
            elif path == "/api/admin/service-save":
                if data.get("id"):
                    conn.execute("UPDATE services SET name_nl=?, name_en=?, price_cents=?, sort_order=?, active=? WHERE id=?", (data["name_nl"], data["name_en"], int(float(data["price"]) * 100), int(data["sort_order"]), int(data.get("active", 1)), data["id"]))
                else:
                    conn.execute("INSERT INTO services(name_nl,name_en,price_cents,sort_order,active) VALUES(?,?,?,?,?)", (data["name_nl"], data["name_en"], int(float(data["price"]) * 100), int(data["sort_order"]), 1))
            elif path == "/api/admin/service-delete":
                conn.execute("UPDATE services SET active=0 WHERE id=?", (data["id"],))
            elif path == "/api/admin/contact":
                conn.execute("UPDATE contact SET snapchat=?, whatsapp=?, phone=?, email=?, location=?, text_nl=?, text_en=? WHERE id=1", (data["snapchat"], data["whatsapp"], data["phone"], data["email"], data["location"], data["text_nl"], data["text_en"]))
            elif path == "/api/admin/settings":
                for key, value in data.items():
                    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))
            elif path == "/api/admin/featured-plan":
                conn.execute("UPDATE subscription_plans SET featured=CASE WHEN id=? THEN 1 ELSE 0 END", (data["id"],))
            else:
                self.send_error(404)
                return
        self.json({"ok": True})


if __name__ == "__main__":
    init_db()
    threading.Thread(target=expire_and_remind, daemon=True).start()
    port = int(os.getenv("PORT", "8000"))
    print(f"ITBCUTZ running at http://localhost:{port}")
    ThreadingHTTPServer(("localhost", port), App).serve_forever()
