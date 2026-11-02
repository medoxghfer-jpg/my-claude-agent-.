"""قاعدة البيانات (SQLite) + تشفير كلمات المرور + بيانات تجريبية."""
import os, sqlite3, hashlib, hmac, secrets, datetime
from contextlib import contextmanager

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "travel.db"))

def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@contextmanager
def tx():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def rows(q, args=()):
    with tx() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]

def one(q, args=()):
    r = rows(q, args)
    return r[0] if r else None

# ---------- كلمات المرور ----------
def hash_password(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()
    return f"{salt}${h}"

def verify_password(pw, stored):
    try:
        salt, _ = stored.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(pw, salt), stored)

SCHEMA = """
CREATE TABLE IF NOT EXISTS trips(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL, destination TEXT NOT NULL, description TEXT DEFAULT '',
  price REAL NOT NULL, currency TEXT DEFAULT 'EGP',
  start_date TEXT, end_date TEXT, days INTEGER DEFAULT 1,
  seats_total INTEGER DEFAULT 0, seats_available INTEGER DEFAULT 0,
  hotel TEXT DEFAULT '', transport TEXT DEFAULT '', program TEXT DEFAULT '',
  active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL, role TEXT DEFAULT 'admin', created_at TEXT);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trip_id INTEGER NOT NULL, customer_name TEXT NOT NULL, phone TEXT NOT NULL,
  email TEXT DEFAULT '', persons INTEGER NOT NULL, notes TEXT DEFAULT '',
  total_price REAL NOT NULL, status TEXT DEFAULT 'new', source TEXT DEFAULT 'form',
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, is_read INTEGER DEFAULT 0, created_at TEXT);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, action TEXT, details TEXT, created_at TEXT);
"""

def _d(days_from_now):
    return (datetime.date.today() + datetime.timedelta(days=days_from_now)).isoformat()

SAMPLE_TRIPS = [
    ("شرم الشيخ - 4 أيام", "شرم الشيخ", "إقامة على البحر الأحمر مع رحلة سنوركلينج وسهرة بدوية.", 6500, 14, 4, 30, "فندق 4 نجوم - إفطار وعشاء", "أتوبيس سياحي مكيف", "اليوم 1: وصول وتسكين. اليوم 2: رحلة سنوركلينج. اليوم 3: سفاري وسهرة بدوية. اليوم 4: عودة."),
    ("الأقصر وأسوان - 5 أيام", "الأقصر وأسوان", "جولة في المعابد الفرعونية مع رحلة نيلية.", 9800, 21, 5, 25, "مركب نيلي 5 نجوم - إقامة كاملة", "طيران داخلي + أتوبيس", "زيارة الكرنك ووادي الملوك ومعبد فيلة والسد العالي."),
    ("الغردقة - 3 أيام", "الغردقة", "عطلة قصيرة على البحر مع رحلة جزيرة.", 4200, 10, 3, 40, "ريزورت 4 نجوم - أول إنكلوسف", "أتوبيس سياحي", "رحلة جزيرة الجفتون وغطس وحرية على البحر."),
    ("دهب - 4 أيام", "دهب", "هدوء وتخييم وغوص وسط الطبيعة.", 3900, 30, 4, 20, "كامب بحري - إفطار", "ميني باص", "يوم غوص في بلو هول وتسلق جبل وسهرة شاطئ."),
    ("مرسى مطروح - 3 أيام", "مرسى مطروح", "شواطئ فيروزية وهدوء صيفي.", 3300, 45, 3, 35, "فندق 3 نجوم - إفطار", "أتوبيس سياحي", "شاطئ عجيبة والجميلة وزيارة الأماكن الأثرية."),
]

def init_db():
    """ينشئ الجداول. يرجّع كلمة سر الأدمن لو اتعمل أدمن جديد."""
    with tx() as c:
        c.executescript(SCHEMA)
    new_pw = None
    if not one("SELECT id FROM users LIMIT 1"):
        new_pw = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(9)
        with tx() as c:
            c.execute("INSERT INTO users(username,pw_hash,role,created_at) VALUES(?,?,?,?)",
                      ("admin", hash_password(new_pw), "admin", now()))
    if not one("SELECT id FROM trips LIMIT 1"):
        with tx() as c:
            for t in SAMPLE_TRIPS:
                title, dest, desc, price, start, days, seats, hotel, transport, program = t
                c.execute("""INSERT INTO trips(title,destination,description,price,start_date,end_date,days,
                    seats_total,seats_available,hotel,transport,program,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (title, dest, desc, price, _d(start), _d(start + days - 1), days, seats, seats,
                     hotel, transport, program, now(), now()))
    return new_pw
