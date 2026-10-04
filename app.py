from google import genai 
from google.genai import types
import streamlit as st
import requests

from prompts import SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE, SUMMARY_REQUEST_PROMPT

from twilio.rest import Client as TwilioClient

# initialising GEMINI Client

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

@st.cache_resource # for re using the resource without creating the same obj again and again.
def get_gemini_key():
    return genai.Client(api_key=GEMINI_API_KEY)

gemini_client = get_gemini_key()
MODEL_NAME = "gemini-3.5-flash-lite"

def send_telegram(chat_id, user_name, summary):
    token = st.secrets["TELEGRAM_BOT_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    message_text = f"🥗 *MacroSnap Summary for {user_name}*\n\n{summary}"
    
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        if data.get("ok"):
            return True, data["result"]["message_id"]
        return False, data.get("description", "Unknown error")
    except Exception as error:
        return False, str(error)

def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])

def add_message(role, kind, content):
    st.session_state.messages.append({"role":role, "kind":kind, "content":content})
    render_message(st.session_state.messages[-1])

def ask_gemini(parts):
    try:
        return st.session_state.chat.send_message(parts).text
    except Exception as error:
        return f"Sorry, something went wrong: {error}"

# step 1 : Onboard (username and phone number)

if not "onboarded" in st.session_state:
    st.title("MacroSnap 🥗")
    st.caption("Snap it. Crack it. Test yourself the Results!")

    with st.form("onboarding_form"):
        name = st.text_input("Your name")
        telegram_chat_id = st.text_input("Telegram Chat ID", placeholder="e.g. 123456789")
        submitted = st.form_submit_button("Lets Go!")

    if submitted:

        if (not name.strip()) or (not telegram_chat_id.strip()):
            st.warning("Please fill out BOTH the fields!!!")

        else:
            st.session_state.name = name.strip()
            st.session_state.telegram_chat_id = telegram_chat_id

        # activate AI

            st.session_state.chat = gemini_client.chats.create(
            model = MODEL_NAME, 
            config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
            )

            st.session_state.messages = []
            st.session_state.onboarded = True 

            st.rerun()

    st.stop() 

# create a chat interface

header_col, button_col = st.columns([5,2], vertical_alignment="center")

with header_col:
    st.title("MacroSnap 🥗")

with button_col:
    send_disabled = len(st.session_state.messages) <= 1
    if st.button("Send to Telegram", disabled=send_disabled):
        with st.spinner("Summarizing your Day..."):
            summary = ask_gemini([SUMMARY_REQUEST_PROMPT])
            success, info = send_telegram(st.session_state.telegram_chat_id, st.session_state.name, summary)

        if success:
            st.success("Yayyy! Message sent. Check your Telegram!")
        else:
            st.error(f"Oops! Couldn't send that: {info}")

st.caption(f"Logged in as {st.session_state.name} - Updates will go to Telegram ID {st.session_state.telegram_chat_id}")

if not st.session_state.messages:
    add_message("assitant", "text", WELCOME_MESSAGE_TEMPLATE.format(name = st.session_state.name))
else:
    for message in st.session_state.messages:
        render_message(message)

user_input = st.chat_input(
    "Ask a question or attach a Click of your Meal", 
    accept_file=True,
    file_type=["jpeg", "png", "jpg"]
)

if user_input:
    photo = user_input.files[0] if user_input.files else None 
    text = user_input.text 
    parts = []

    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type))

    if text:
        add_message("user", "text", text)
        parts.append(text)

    elif photo is not None:
        parts.append("What is this meal? Give me the calories and Macros")

    with st.spinner("Crunching the numbers..."):
        answer = ask_gemini(parts)

    add_message("assistant", "text", answer)
