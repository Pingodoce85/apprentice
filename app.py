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
        st.title("🏗️ P&J Construction Document Assistant")
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


def extract_text_from_pdfs(pdf_folder):
    all_text = []
    storage_key = os.getenv("AZURE_STORAGE_KEY") or st.secrets.get("AZURE_STORAGE_KEY")
    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT") or st.secrets.get("AZURE_STORAGE_ACCOUNT")
    container = os.getenv("AZURE_STORAGE_CONTAINER") or st.secrets.get("AZURE_STORAGE_CONTAINER", "construction-docs")   



    try:
        from azure.storage.blob import BlobServiceClient
        connect_str = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        container_client = blob_service_client.get_container_client(container)
        
        for blob in container_client.list_blobs():
            if blob.name.endswith(".pdf"):
                blob_client = container_client.get_blob_client(blob.name)
                pdf_bytes = blob_client.download_blob().readall()
                doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                all_text.append({"filename": blob.name, "content": text})
    except Exception as e:
        st.warning(f"Could not connect to Azure Storage, falling back to local files: {e}")
        for filename in os.listdir(pdf_folder):
            if filename.endswith(".pdf"):
                filepath = os.path.join(pdf_folder, filename)
                doc = pymupdf.open(filepath)
                text = ""
                for page in doc:
                    text += page.get_text()
                all_text.append({"filename": filename, "content": text})
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
st.title("🏗️Apprenticet")
st.caption("Your personal AI-powered mechnical contracting assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "documents" not in st.session_state:
    with st.spinner("Loading construction documents..."):
        st.session_state.documents = extract_text_from_pdfs("pdfs")
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

