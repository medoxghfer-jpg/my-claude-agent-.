
import streamlit as st
from google import genai

# إعداد الصفحة
st.set_page_config(
    page_title="My AI Agent",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 My AI Agent - Gemini")
st.caption("مساعدك الذكي")

# قراءة مفتاح Gemini بأمان
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("مفتاح Gemini API غير موجود في إعدادات Secrets.")
    st.stop()

# إنشاء اتصال Gemini
client = genai.Client(api_key=api_key)

# تهيئة سجل المحادثة
if "messages" not in st.session_state:
    st.session_state.messages = []

# عرض المحادثات السابقة
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# استقبال رسالة المستخدم
user_prompt = st.chat_input("اكتب رسالتك هنا...")

if user_prompt:

    # عرض رسالة المستخدم
    st.session_state.messages.append({
        "role": "user",
        "content": user_prompt
    })

    with st.chat_message("user"):
        st.markdown(user_prompt)

    # إرسال الطلب إلى Gemini
    with st.chat_message("assistant"):
        with st.spinner("جاري التفكير..."):

            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        {
                            "role": "user" if m["role"] == "user" else "model",
                            "parts": [{"text": m["content"]}]
                        }
                        for m in st.session_state.messages
                    ]
                )

                answer = response.text

                if not answer:
                    answer = "لم أتمكن من إنشاء رد، حاول مرة أخرى."

                st.markdown(answer)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })

            except Exception as e:
                st.error("حدث خطأ أثناء الاتصال بـ Gemini.")
                st.caption(f"تفاصيل الخطأ: {type(e).__name__}")
