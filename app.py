import streamlit as st
import pymupdf
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🏗️ Apprentice")
        password = st.text_input("Enter password to access:", type="password")
        if st.button("Login"):
            correct = os.getenv("APP_PASSWORD") or st.secrets.get("APP_PASSWORD")
            if password == correct:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
        st.stop()

check_password()

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or st.secrets.get("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_KEY") or st.secrets.get("AZURE_OPENAI_KEY")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or st.secrets.get("AZURE_OPENAI_DEPLOYMENT")

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version="2024-02-01"
)

def extract_text_from_onedrive():
    import msal
    import requests
    client_id = os.getenv("ONEDRIVE_CLIENT_ID") or st.secrets.get("ONEDRIVE_CLIENT_ID")
    client_secret = os.getenv("ONEDRIVE_CLIENT_SECRET") or st.secrets.get("ONEDRIVE_CLIENT_SECRET")
    tenant_id = os.getenv("ONEDRIVE_TENANT_ID") or st.secrets.get("ONEDRIVE_TENANT_ID")
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )
    token = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in token:
        st.error(f"Authentication failed: {token.get('error_description')}")
        return []
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    folder_url = "https://graph.microsoft.com/v1.0/me/drive/root:/apprentice-docs:/children"
    response = requests.get(folder_url, headers=headers)
    files = response.json().get("value", [])
    all_text = []
    for file in files:
        if file["name"].endswith(".pdf"):
            download_url = file["@microsoft.graph.downloadUrl"]
            pdf_bytes = requests.get(download_url).content
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            all_text.append({"filename": file["name"], "content": text})
    return all_text

def ask_question(question, documents):
    context = ""
    for doc in documents:
        context += f"\n\nDocument: {doc['filename']}\n{doc['content'][:50000]}"
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": f"""You are an expert assistant for a mechanical contracting company.
            Answer questions based ONLY on the provided construction documents.
            Always cite which document your answer comes from.
            If the answer is not in the documents, say so clearly.
            Documents:
            {context}"""},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content

st.set_page_config(page_title="Apprentice", page_icon="🏗️")
st.title("🏗️ Apprentice")
st.caption("Your personal AI-powered mechanical contracting assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "documents" not in st.session_state:
    with st.spinner("Loading construction documents..."):
        st.session_state.documents = extract_text_from_onedrive()
    st.success(f"Loaded {len(st.session_state.documents)} documents")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about your construction documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Searching documents..."):
            response = ask_question(prompt, st.session_state.documents)
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
