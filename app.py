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


def extract_text_from_storage():
    from azure.storage.blob import BlobServiceClient
    import base64
    from pdf2image import convert_from_bytes
    from PIL import Image
    import io

    storage_key = os.getenv("AZURE_STORAGE_KEY") or st.secrets.get("AZURE_STORAGE_KEY")
    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT") or st.secrets.get("AZURE_STORAGE_ACCOUNT")
    container = os.getenv("AZURE_STORAGE_CONTAINER") or st.secrets.get("AZURE_STORAGE_CONTAINER")
    
    connect_str = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_client = blob_service_client.get_container_client(container)
    
    all_text = []
    
    for blob in container_client.list_blobs():
        if blob.name.endswith(".pdf"):
            blob_client = container_client.get_blob_client(blob.name)
            pdf_bytes = blob_client.download_blob().readall()
            
            # First try standard text extraction
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            
            # If text extraction yields little content use GPT-4o Vision
            if len(text.strip()) < 100:
                text = extract_with_vision(pdf_bytes, blob.name)
            
            all_text.append({"filename": blob.name, "content": text})
    
    return all_text

def extract_with_vision(pdf_bytes, filename):
    import base64
    from pdf2image import convert_from_bytes
    import io
    
    full_text = ""
    try:
        images = convert_from_bytes(pdf_bytes, dpi=150, first_page=1, last_page=10)
        for i, image in enumerate(images):
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_data}"
                                }
                            },
                            {
                                "type": "text",
                                "text": "You are reading a construction document. Extract ALL text you can see including handwritten notes, stamps, labels, dimensions, and annotations. Ignore coffee stains, smudges, and other artifacts. Return the extracted text only."
                            }
                        ]
                    }
                ]
            )
            full_text += f"\n[Page {i+1}]\n"
            full_text += response.choices[0].message.content
    except Exception as e:
        full_text = f"Vision extraction failed: {e}"
    
    return full_text


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
        st.session_state.documents = extract_text_from_storage()

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
