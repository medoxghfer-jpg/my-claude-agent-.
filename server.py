import streamlit as st
import google.generativeai as genai

st.title("My AI Agent - Gemini")

# سحب المفتاح بأمان من إعدادات Streamlit Secrets
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("غير موجود في الإعدادات! API مفتاح الـ")

user_prompt = st.text_area("هنا Agent اكتب رسالتك للـ:")

if st.button("إرسال"):
    if user_prompt:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(user_prompt)
        st.write(response.text)
    else:
        st.warning(".الرجاء كتابة نص أولاً")
