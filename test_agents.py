"""اختبار منطق الوكلاء بنموذج وهمي (من غير إنترنت ولا مفتاح)."""
import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
import db, agents
db.init_db()

def script(steps):
    it = iter(steps)
    def llm(system, msgs, tools):
        return next(it)
    return llm

def tu(i, name, **inp):
    return {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": i, "name": name, "input": inp}]}
def tx(t):
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": t}]}

# 1) العميل: بحث ثم حجز
llm = script([tu("a", "search_trips", destination="شرم"), tx("لقيت رحلة"),
              tu("b", "create_booking_request", trip_id=1, customer_name="منى", phone="01099998888", persons=3), tx("تم")])
print(agents.run_agent("customer", "s1", "عايز شرم", llm=llm))
print(agents.run_agent("customer", "s1", "احجزلي 3", llm=llm))
o = db.one("SELECT * FROM orders")
assert o and o["total_price"] == 6500 * 3 and o["status"] == "new", o
assert db.one("SELECT COUNT(*) n FROM notifications")["n"] == 1
print("حجز العميل + الإشعار: OK، الذاكرة:", len(agents.HISTORY["s1"]), "رسالة")

# 2) العميل مايقدرش يستخدم أدوات الإدارة
llm = script([tu("c", "update_trip", trip_id=1, price=1), tx("ok")])
agents.run_agent("customer", "s2", "غيّر السعر", llm=llm)
assert db.one("SELECT price FROM trips WHERE id=1")["price"] == 6500
print("منع العميل من تعديل الأسعار: OK")

# 3) أدمن يعدل السعر ويتسجل في audit
llm = script([tu("d", "update_trip", trip_id=1, price=7200), tx("تم")])
agents.run_agent("management", "a1", "السعر 7200", ctx={"username": "admin"}, llm=llm)
assert db.one("SELECT price FROM trips WHERE id=1")["price"] == 7200
assert db.one("SELECT * FROM audit_log WHERE action='update_trip'")
print("تعديل الأدمن + audit: OK")

# 4) مدخلات سيئة من النموذج ما تكسرش حاجة
llm = script([tu("e", "create_booking_request", trip_id=1, customer_name="x", phone="123", persons=-5), tx("اعتذار")])
print(agents.run_agent("customer", "s3", "x", llm=llm))
assert db.one("SELECT COUNT(*) n FROM orders")["n"] == 1
llm = script([tu("f", "report", period="weekly"), tx("التقرير")])
print(agents.run_agent("orders", "a2", "تقرير", ctx={"username": "admin"}, llm=llm))

# 5) فشل الاتصال بالنموذج
def bad(*a):
    raise RuntimeError("ai_unreachable")
print(agents.run_agent("customer", "s4", "ازيك", llm=bad))
print("كل الاختبارات نجحت ✅")
