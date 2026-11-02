"""تشخيص سريع: بيجرّب الاتصال بالذكاء الاصطناعي ويطبع النتيجة والوقت."""
import time
import server, agents   # تحميل .env
print("Provider:", agents.PROVIDER or "none", "| Model:", agents.MODEL, "| Key set:", agents.AI_ENABLED)
if not agents.AI_ENABLED:
    raise SystemExit("No API key found in .env")
t = time.time()
try:
    r = agents.call_llm("Reply briefly.", [{"role": "user", "content": "قول مرحبا بجملة واحدة"}], agents._schemas("customer"))
    print("Reply:", "".join(b.get("text", "") for b in r["content"]))
    print(f"OK - took {time.time() - t:.1f}s")
except Exception as e:
    print("FAILED:", e, f"after {time.time() - t:.1f}s")
