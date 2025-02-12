 # Importing required packages
import streamlit as st
import openai
import uuid
import time
import pandas as pd
import io
from openai import OpenAI
import base64
from email.message import EmailMessage


assistant_id = st.secrets["assistant_id"]  
api_key = st.secrets["api_key"]


def set_background(svg_file):
    def get_base64(file_path):
        with open(file_path, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()

    bin_str = get_base64(svg_file)
    page_bg_img = '''
    <style>
    .stApp {
        background-image: url("data:image/svg+xml;base64,%s");
        background-size: cover;
    }
    </style>
    ''' % bin_str
    st.markdown(page_bg_img, unsafe_allow_html=True)


client = OpenAI(api_key=api_key)

# Your chosen model
MODEL = "gpt-4-1106-preview"

# Initialize session state variables
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "run" not in st.session_state:
    st.session_state.run = {"status": None}

if "messages" not in st.session_state:
    st.session_state.messages = []

if "retry_error" not in st.session_state:
    st.session_state.retry_error = 0

# Set up the page
st.set_page_config(page_title="AI Law", page_icon=":robot_face:", layout="wide")
set_background('./assett/sfondo.svg')
st.sidebar.title("AI Law")
st.sidebar.markdown('''
    ## About
AI-based tool 🤖 that optimizes legal professionals' research activities in doctrine and case law ⚖️
    ''')
st.sidebar.divider()
st.sidebar.image('./assett/logo.svg', width=200)
st.sidebar.divider()
# Indirizzo email predefinito
email_address = 'f.gabri@icloud.com'

# Creazione del pulsante Markdown che apre il client di posta elettronica predefinito
st.sidebar.link_button("Send Feedback", "mailto:{email_address}?subject=Feedback&body=Insert here your feedback")

# File uploader for CSV, XLS, XLSX
st.image('./assett/logo.svg', width=200)
uploaded_file = st.file_uploader("Upload your file", type=["pdf", "csv", "xls", "xlsx"])

if uploaded_file is not None:
    # Determine the file type
    file_type = uploaded_file.type

    try:
        # Read the file into a Pandas DataFrame
        if file_type == "text/csv":
            df = pd.read_csv(uploaded_file)
        elif file_type in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
            df = pd.read_excel(uploaded_file)

        # Convert DataFrame to JSON
        json_str = df.to_json(orient='records', indent=4)
        file_stream = io.BytesIO(json_str.encode())

        # Upload JSON data to OpenAI and store the file ID
        file_response = client.files.create(file=file_stream, purpose='answers')
        st.session_state.file_id = file_response.id
        st.success("File uploaded successfully to OpenAI!")

        # Optional: Display and Download JSON
        st.text_area("JSON Output", json_str, height=300)
        st.download_button(label="Download JSON", data=json_str, file_name="converted.json", mime="application/json")
    
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Initialize OpenAI assistant
if "assistant" not in st.session_state:
    openai.api_key = api_key
    st.session_state.assistant = openai.beta.assistants.retrieve(assistant_id)
    st.session_state.thread = client.beta.threads.create(
        metadata={'session_id': st.session_state.session_id}
    )

# Display chat messages
elif hasattr(st.session_state.run, 'status') and st.session_state.run.status == "completed":
    st.session_state.messages = client.beta.threads.messages.list(
        thread_id=st.session_state.thread.id
    )
    for message in reversed(st.session_state.messages.data):
        if message.role in ["user", "assistant"]:
            with st.chat_message(message.role):
                for content_part in message.content:
                    message_text = content_part.text.value
                    st.markdown(message_text)

# Chat input and message creation with file ID
if prompt := st.chat_input("How can I help you?"):
    with st.chat_message('user'):
        st.write(prompt)

    message_data = {
        "thread_id": st.session_state.thread.id,
        "role": "user",
        "content": prompt
    }

    # Include file ID in the request if available
    if "file_id" in st.session_state:
        message_data["file_ids"] = [st.session_state.file_id]

    st.session_state.messages = client.beta.threads.messages.create(**message_data)

    st.session_state.run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread.id,
        assistant_id=st.session_state.assistant.id,
    )
    if st.session_state.retry_error < 3:
        time.sleep(1)
        st.rerun()

# Handle run status
if hasattr(st.session_state.run, 'status'):
    if st.session_state.run.status == "running":
        with st.chat_message('assistant'):
            st.write("Thinking ......")
        if st.session_state.retry_error < 3:
            time.sleep(1)
            st.rerun()

    elif st.session_state.run.status == "failed":
        st.session_state.retry_error += 1
        with st.chat_message('assistant'):
            if st.session_state.retry_error < 3:
                st.write("Run failed, retrying ......")
                time.sleep(3)
                st.rerun()
            else:
                st.error("FAILED: The OpenAI API is currently processing too many requests. Please try again later ......")

    elif st.session_state.run.status != "completed":
        st.session_state.run = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread.id,
            run_id=st.session_state.run.id,
        )
        if st.session_state.retry_error < 3:
            time.sleep(3)
            st.rerun()