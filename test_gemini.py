"""اختبار دعم Gemini بسيرفر وهمي بيتحقق من شكل الطلبات (من غير إنترنت)."""
import os, json, tempfile, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
problems, seen = [], []

class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        out = {"models": [{"name": "models/gemini-9-flash-preview", "supportedGenerationMethods": ["generateContent"]},
                          {"name": "models/gemini-8-flash", "supportedGenerationMethods": ["generateContent"]},
                          {"name": "models/gemini-8-flash-image", "supportedGenerationMethods": ["generateContent"]},
                          {"name": "models/gemini-8-pro", "supportedGenerationMethods": ["generateContent"]},
                          {"name": "models/text-embedding", "supportedGenerationMethods": ["embedContent"]}]}
        data = json.dumps(out).encode(); self.send_response(200); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        if "gemini-old" in self.path:
            self.send_response(404); self.end_headers(); self.wfile.write(b"{}"); return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append(body)
        if self.headers.get("x-goog-api-key") != "FAKEKEY": problems.append("مفتاح الهيدر ناقص")
        if "/models/gemini-test:generateContent" not in self.path and "gemini-8-flash:" not in self.path: problems.append("المسار غلط " + self.path)
        if "systemInstruction" not in body: problems.append("systemInstruction ناقص")
        decl = body["tools"][0]["functionDeclarations"]
        if any("parameters" in d and not d["parameters"].get("properties") for d in decl): problems.append("parameters فاضي")
        last = body["contents"][-1]
        fr = [p for p in last["parts"] if "functionResponse" in p]
        if fr:
            prev = body["contents"][-2]
            if prev["role"] != "model" or prev["parts"][0].get("thoughtSignature") != "SIG1": problems.append("thoughtSignature ما رجعش")
            if fr[0]["functionResponse"]["name"] != "search_trips": problems.append("اسم الدالة في الرد غلط")
            if "trips" not in fr[0]["functionResponse"]["response"]: problems.append("نتيجة الأداة ناقصة")
            out = {"candidates": [{"content": {"role": "model", "parts": [{"text": "لقيتلك رحلة شرم الشيخ"}]}}]}
        elif "429" in last["parts"][0].get("text", ""):
            self.send_response(429); self.end_headers(); self.wfile.write(b"{}"); return
        else:
            out = {"candidates": [{"content": {"role": "model", "parts": [
                {"functionCall": {"name": "search_trips", "args": {"destination": "شرم"}}, "thoughtSignature": "SIG1"}]}}]}
        data = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)

srv = HTTPServer(("127.0.0.1", 8999), Fake)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ.update({"DB_PATH": os.path.join(tempfile.mkdtemp(), "g.db"), "GEMINI_API_KEY": "FAKEKEY",
                   "GEMINI_BASE": "http://127.0.0.1:8999", "AI_MODEL": "gemini-test"})
import db, agents
db.init_db()
assert agents.PROVIDER == "gemini" and agents.AI_ENABLED

print(agents.run_agent("customer", "g1", "عايز رحلة شرم"))
print("طول المحادثة:", len(agents.HISTORY["g1"]))
# أداة بدون معاملات (list_trips) لازم ما تتبعتش parameters فاضية
agents._call_gemini("x", [{"role": "user", "content": "hi"}], agents._schemas("management"))
# خطأ 429 يرجّع رسالة لطيفة ومايبوّظش المحادثة
n = len(agents.HISTORY["g1"])
print(agents.run_agent("customer", "g1", "429"))
assert len(agents.HISTORY["g1"]) == n
assert not problems, problems
# موديل اسمه اتسحب (404): لازم يتحوّل لوحده لموديل مستقر شغال
agents.MODEL = "gemini-old"
print(agents.run_agent("customer", "g2", "عايز رحلة شرم"))
assert agents.MODEL == "gemini-8-flash", agents.MODEL
assert not problems, problems
print("اختبار Gemini نجح ✅")
