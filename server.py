"""السيرفر: بيقدّم صفحات الموقع وواجهة الـ API. مكتبات بايثون الأساسية فقط."""
import os, sys, json, time, secrets, datetime, mimetypes
from collections import defaultdict, deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))

def load_env():
    p = os.path.join(BASE, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
load_env()

import db, agents  # بعد تحميل .env

STATIC = os.path.join(BASE, "static")
SESSION_HOURS = 12
SECURE_COOKIE = os.environ.get("SECURE_COOKIE") == "1"
TRUST_PROXY = os.environ.get("TRUST_PROXY") == "1"
hits = defaultdict(deque)

def limited(key, limit, window):
    now, q = time.time(), hits[key]
    while q and q[0] < now - window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False

class Handler(BaseHTTPRequestHandler):
    server_version = "TravelAI"

    def log_message(self, fmt, *a):
        pass

    # ---------- أدوات ----------
    def ip(self):
        if TRUST_PROXY and self.headers.get("X-Forwarded-For"):
            return self.headers["X-Forwarded-For"].split(",")[-1].strip()
        return self.client_address[0]

    def send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:; frame-ancestors 'none'")
        if ctype.startswith("application/json"):
            self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def err(self, code, msg):
        self.send(code, {"error": msg})

    def body(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n > 20000:
                return None
            if "application/json" not in self.headers.get("Content-Type", ""):
                return None
            data = json.loads(self.rfile.read(n) or b"{}")
            return data if isinstance(data, dict) else None
        except (ValueError, json.JSONDecodeError):
            return None

    def user(self):
        cookie = self.headers.get("Cookie", "")
        tok = next((p.split("=", 1)[1] for p in (x.strip() for x in cookie.split(";")) if p.startswith("sid=")), None)
        if not tok:
            return None
        return db.one("""SELECT u.id, u.username, u.role FROM sessions s JOIN users u ON u.id=s.user_id
                         WHERE s.token=? AND s.expires_at>?""", (tok, db.now()))

    # ---------- التوجيه ----------
    def do_GET(self):
        self.route("GET")
    def do_POST(self):
        self.route("POST")
    def do_PUT(self):
        self.route("PUT")

    def route(self, method):
        try:
            u = urlparse(self.path)
            path, qs = u.path.rstrip("/") or "/", parse_qs(u.query)
            if path.startswith("/api/"):
                return self.api(method, path[5:], qs)
            if method != "GET":
                return self.err(405, "غير مسموح")
            return self.static(path)
        except agents.ToolError as e:
            self.err(400, str(e))
        except Exception as e:
            print("ERROR:", repr(e))
            self.err(500, "حصل خطأ في السيرفر")

    def static(self, path):
        name = {"/": "index.html", "/admin": "admin.html"}.get(path)
        if not name and path.startswith("/static/"):
            name = path[8:]
        if not name:
            return self.err(404, "الصفحة مش موجودة")
        full = os.path.realpath(os.path.join(STATIC, name))
        if not full.startswith(STATIC + os.sep) or not os.path.isfile(full):
            return self.err(404, "الصفحة مش موجودة")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self.send(200, open(full, "rb").read(), ctype)

    # ---------- الـ API ----------
    def api(self, method, path, qs):
        parts = path.split("/")
        # ===== عام (للعملاء) =====
        if method == "GET" and path == "config":
            return self.send(200, {"company": agents.COMPANY, "agent": agents.AGENT_NAME, "ai": agents.AI_ENABLED})
        if method == "GET" and path == "trips":
            return self.send(200, db.rows(f"SELECT {agents.PUBLIC_FIELDS} FROM trips WHERE active=1 ORDER BY start_date"))
        if method == "GET" and parts[0] == "trips" and len(parts) == 2 and parts[1].isdigit():
            return self.send(200, agents.get_trip({}, int(parts[1])))
        if method == "POST" and path == "orders":
            if limited(("order", self.ip()), 5, 600):
                return self.err(429, "طلبات كتير، جرّب بعد شوية")
            b = self.body()
            if b is None:
                return self.err(400, "بيانات غير صحيحة")
            allowed = {k: b.get(k) for k in ("trip_id", "customer_name", "phone", "persons", "email", "notes")}
            return self.send(200, agents.create_booking_request({}, source="form", **{k: v for k, v in allowed.items() if v is not None}))
        if method == "POST" and path == "chat":
            if limited(("chat", self.ip()), 20, 60):
                return self.err(429, "رسائل كتير، استنى شوية")
            b = self.body()
            msg = (b or {}).get("message")
            sid = str((b or {}).get("session_id", ""))[:64]
            if not isinstance(msg, str) or not msg.strip() or len(msg) > 1000 or len(sid) < 8:
                return self.err(400, "رسالة غير صحيحة")
            return self.send(200, {"reply": agents.run_agent("customer", "c:" + sid, msg.strip())})
        if method == "POST" and path == "login":
            if limited(("login", self.ip()), 8, 300):
                return self.err(429, "محاولات كتير، استنى 5 دقائق")
            b = self.body() or {}
            usr = db.one("SELECT * FROM users WHERE username=?", (str(b.get("username", ""))[:50],))
            ok = usr and db.verify_password(str(b.get("password", ""))[:200], usr["pw_hash"])
            if not ok:
                return self.err(401, "اسم المستخدم أو كلمة المرور غلط")
            tok = secrets.token_urlsafe(32)
            exp = (datetime.datetime.now() + datetime.timedelta(hours=SESSION_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
            with db.tx() as c:
                c.execute("DELETE FROM sessions WHERE expires_at<?", (db.now(),))
                c.execute("INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)", (tok, usr["id"], exp))
            agents.audit({"username": usr["username"]}, "login", {})
            cookie = f"sid={tok}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_HOURS * 3600}" + ("; Secure" if SECURE_COOKIE else "")
            return self.send(200, {"ok": True, "username": usr["username"]}, headers={"Set-Cookie": cookie})
        if method == "POST" and path == "logout":
            cookie = self.headers.get("Cookie", "")
            for p in cookie.split(";"):
                if p.strip().startswith("sid="):
                    with db.tx() as c:
                        c.execute("DELETE FROM sessions WHERE token=?", (p.strip()[4:],))
            return self.send(200, {"ok": True}, headers={"Set-Cookie": "sid=; Max-Age=0; Path=/"})

        # ===== للموظفين فقط =====
        if parts[0] != "admin":
            return self.err(404, "غير موجود")
        usr = self.user()
        if not usr:
            return self.err(401, "لازم تسجّل دخول")
        ctx = {"username": usr["username"]}
        sub = "/".join(parts[1:])
        if method == "GET" and sub == "me":
            return self.send(200, usr)
        if method == "GET" and sub == "trips":
            return self.send(200, agents.admin_list_trips(ctx)["trips"])
        if method == "POST" and sub == "trips":
            b = self.body()
            if b is None: return self.err(400, "بيانات غير صحيحة")
            return self.send(200, agents.add_trip(ctx, **b))
        if method == "PUT" and parts[1:2] == ["trips"] and len(parts) == 3 and parts[2].isdigit():
            b = self.body()
            if b is None: return self.err(400, "بيانات غير صحيحة")
            b.pop("trip_id", None)
            return self.send(200, agents.update_trip(ctx, int(parts[2]), **b))
        if method == "GET" and sub == "orders":
            return self.send(200, agents.list_orders(ctx, qs.get("status", [""])[0], 100)["orders"])
        if method == "PUT" and parts[1:2] == ["orders"] and len(parts) == 4 and parts[2].isdigit() and parts[3] == "status":
            b = self.body() or {}
            return self.send(200, agents.update_order_status(ctx, int(parts[2]), b.get("status")))
        if method == "GET" and sub == "report":
            return self.send(200, agents.report(ctx, qs.get("period", ["daily"])[0]))
        if method == "GET" and sub == "notifications":
            return self.send(200, agents.list_notifications(ctx, True)["notifications"])
        if method == "POST" and sub == "notifications/read":
            with db.tx() as c:
                c.execute("UPDATE notifications SET is_read=1")
            return self.send(200, {"ok": True})
        if method == "GET" and sub == "audit":
            return self.send(200, db.rows("SELECT * FROM audit_log ORDER BY id DESC LIMIT 50"))
        if method == "POST" and sub == "chat":
            if limited(("achat", usr["id"]), 40, 60):
                return self.err(429, "رسائل كتير")
            b = self.body() or {}
            agent, msg = b.get("agent"), b.get("message")
            if agent not in ("management", "orders") or not isinstance(msg, str) or not msg.strip() or len(msg) > 2000:
                return self.err(400, "رسالة غير صحيحة")
            return self.send(200, {"reply": agents.run_agent(agent, f"a:{usr['id']}:{agent}", msg.strip(), ctx)})
        return self.err(404, "غير موجود")

def main():
    new_pw = db.init_db()
    if new_pw:
        print("=" * 50)
        print("New admin account created:")
        print("  Username: admin")
        print(f"  Password: {new_pw}")
        print("  (Save it now - it will not be shown again)")
        print("=" * 50)
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    if agents.AI_ENABLED:
        print(f"AI: ON ({agents.PROVIDER} / {agents.MODEL})")
    else:
        print("AI: OFF - no API key found in .env (demo mode)")
    print(f"Open: http://127.0.0.1:{port}   |   Admin panel: /admin")
    ThreadingHTTPServer((host, port), Handler).serve_forever()

if __name__ == "__main__":
    main()
