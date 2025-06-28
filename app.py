import fitz  # PyMuPDF
import streamlit as st
from groq import Groq
import time
from datetime import datetime
from langdetect import detect, LangDetectException

st.set_page_config(page_title="Customer Support AI", page_icon="💬")
st.title("💬 Customer Support AI Agent")

# 🔑 Groq client
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# 💡 Intent options
intents = {
    "Billing Issue": {
        "system": "You are helping the user with billing-related questions, like payment issues or invoices.",
        "default_reply": """Here are some billing issues I can assist with:
- Transaction failure
- Incorrect bank charges
- Unrecognized deductions
- EMI payment queries
- Statement clarification"""
    },
    "Claims & Reimbursement": {
        "system": "You assist with insurance claims, status tracking, and reimbursement-related queries.",
        "default_reply": """Claim Help Available:
- How to file a claim
- Track claim status
- Required documents
- Reimbursement timelines"""
    },
    "Policy & Plans": {
        "system": "You help the user understand or upgrade their policy or insurance plan.",
        "default_reply": """Policy Support:
- Term insurance
- Health insurance
- Vehicle insurance
- Pension & investment plans
- Policy upgrade/downgrade help"""
    },
    "Document Help": {
        "system": "You help the user with uploading, verifying, or understanding required documents.",
        "default_reply": """Document Support:
- KYC document checklist
- Upload/verification help
- Required formats
- Common rejection reasons"""
    },
    "Form Filling Help": {
        "system": "You help the user understand how to correctly fill out insurance forms, what each field means, and what info to put.",
        "default_reply": """I can guide you on filling forms like:
- Gold Loan Application
- Car Loan Application
- Insurance Policy Forms
- Account opening forms
- Address/ID update forms"""
    },
    "General Support": {
        "system": "You answer any other customer support queries.",
        "default_reply": """General Help Topics:
- Bank holidays
- Branch info
- Grievance redressal
- Mobile banking help
- Debit/Credit card support"""
    }
}

# 📄 Upload PDF
uploaded_file = st.file_uploader("📄 Upload a PDF (optional)", type="pdf")
pdf_text = ""
if uploaded_file:
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        for page in doc:
            pdf_text += page.get_text()
    st.success("✅ PDF uploaded and content loaded.")

# ⬇️ Intent selection
selected_intent = st.selectbox("Choose your query type:", list(intents.keys()))

# 🧠 Init session
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": intents[selected_intent]["system"]},
        {"role": "assistant", "content": intents[selected_intent]["default_reply"]}
    ]

# 🔄 Reset on intent change
if st.session_state.messages[0]["content"] != intents[selected_intent]["system"]:
    st.session_state.messages = [
        {"role": "system", "content": intents[selected_intent]["system"]},
        {"role": "assistant", "content": intents[selected_intent]["default_reply"]}
    ]

# 🗳 Init feedback storage
if "feedback" not in st.session_state:
    st.session_state.feedback = []

# 💬 Show chat history
for msg in st.session_state.messages[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 🧾 Chat input
user_input = st.chat_input("Ask your question...")

if user_input:
    try:
        user_lang = detect(user_input)
    except LangDetectException:
        user_lang = "en"

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.spinner("Thinking..."):
        context_messages = st.session_state.messages.copy()

        # Multilingual prompt
        context_messages.insert(1, {
            "role": "system",
            "content": f"Always reply in the user's language. The detected language is: {user_lang}"
        })

        # Inject PDF
        if pdf_text:
            context_messages.insert(1, {
                "role": "user",
                "content": f"The following document is uploaded by the user:\n{pdf_text[:4000]}"
            })

        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=context_messages
        )
        bot_reply = response.choices[0].message.content

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_reply = ""
        for chunk in bot_reply:
            full_reply += chunk
            placeholder.markdown(full_reply + "❚")
            time.sleep(0.001)
        placeholder.markdown(full_reply)

        # 👍👎 Feedback on latest message
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍", key="thumb_up"):
                st.session_state.feedback.append({
                    "message": bot_reply,
                    "vote": "up",
                    "timestamp": datetime.now().isoformat()
                })
                st.success("Thanks for your feedback!")
        with col2:
            if st.button("👎", key="thumb_down"):
                st.session_state.feedback.append({
                    "message": bot_reply,
                    "vote": "down",
                    "timestamp": datetime.now().isoformat()
                })
                st.warning("Thanks, we’ll improve!")

    # Add assistant message
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})

    # ✨ Generate summary/ticket
    summary_prompt = [
        {"role": "system", "content": "Summarize the user's question and the assistant's answer in 1-2 lines."},
        {"role": "user", "content": f"User: {user_input}\nAssistant: {bot_reply}"}
    ]

    summary_response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=summary_prompt
    )

    summary_text = summary_response.choices[0].message.content.strip()
    st.session_state.latest_ticket = {
    "intent": selected_intent,
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "user_query": user_input,
    "bot_reply": bot_reply,
    "summary": summary_text
}

# Show ticket only if exists
if "latest_ticket" in st.session_state:
    with st.expander("📋 View Generated Support Ticket"):
        st.json(st.session_state.latest_ticket)