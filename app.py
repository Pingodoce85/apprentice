import streamlit as st
import pymupdf
import os
import json
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

def load_glossary():
    try:
        with open("glossary.json", "r") as f:
            return json.load(f)
    except:
        return {}

def enrich_with_glossary(question, glossary):
    found_terms = []
    question_upper = question.upper()
    for term, definition in glossary.items():
        if term.upper() in question_upper:
            found_terms.append(f"{term}: {definition}")
    if found_terms:
        return "\n\nRelevant Technical Terms:\n" + "\n".join(found_terms)
    return ""

glossary = load_glossary()

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.markdown("""
        <style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
html, body, [class*="css"], p, div, span, input, textarea, button, [data-testid="stChatMessage"], [data-testid="stMarkdownContainer"], [data-testid="stChatInput"] * { font-family: 'Inter', sans-serif !important; }
        [data-testid="InputInstructions"] {display: none;}
        </style>
        """, unsafe_allow_html=True)
        st.title("Fieldbook")
        with st.form("login_form"):
            password = st.text_input("Enter password to access:", type="password")
            submitted = st.form_submit_button("Login")
        if submitted:
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

def detect_color_content(image):
    import cv2
    import numpy as np
    img_array = np.array(image)
    hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    color_pixels = np.sum(saturation > 50)
    total_pixels = saturation.size
    return color_pixels / total_pixels

def preprocess_image(image, color_ratio):
    import cv2
    import numpy as np
    img_array = np.array(image)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    coords = np.column_stack(np.where(gray < 200))
    if len(coords) > 100:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) > 80:
            angle = 180 + angle

        if abs(angle) > 0.5:
            h, w = gray.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            if color_ratio > 0.05:
                img_array = cv2.warpAffine(img_array, M, (w, h))
            else:
                rotated = cv2.warpAffine(gray, M, (w, h))
                _, img_array = cv2.threshold(rotated, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                img_array = cv2.fastNlMeansDenoising(img_array, h=10)
    from PIL import Image
    if len(img_array.shape) == 2:
        return Image.fromarray(img_array)
    return Image.fromarray(img_array)

@st.cache_resource
def extract_text_from_storage():
    from azure.storage.blob import BlobServiceClient
    from pdf2image import convert_from_bytes
    import io
    import pandas as pd

    storage_key = os.getenv("AZURE_STORAGE_KEY") or st.secrets.get("AZURE_STORAGE_KEY")
    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT") or st.secrets.get("AZURE_STORAGE_ACCOUNT")
    container = os.getenv("AZURE_STORAGE_CONTAINER") or st.secrets.get("AZURE_STORAGE_CONTAINER")
    connect_str = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_client = blob_service_client.get_container_client(container)

    cache_blob_name = "_cache.json"
    try:
        cache_blob = container_client.get_blob_client(cache_blob_name)
        cache_data = cache_blob.download_blob().readall()
        cached_docs = json.loads(cache_data)
        current_pdfs = set()
        for blob in container_client.list_blobs():
            if blob.name.endswith(".pdf"):
                current_pdfs.add(blob.name)
        cached_pdfs = set(doc["filename"] for doc in cached_docs)
        if current_pdfs == cached_pdfs:
            return cached_docs
    except Exception:
        cached_docs = []

    all_text = list(cached_docs) if cached_docs else []
    cached_filenames = set(doc["filename"] for doc in all_text)

    for blob in container_client.list_blobs():
        if blob.name.endswith(".pdf") and blob.name not in cached_filenames:
            blob_client = container_client.get_blob_client(blob.name)
            pdf_bytes = blob_client.download_blob().readall()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                page_text = page.get_text()
                tables = page.find_tables()
                if tables.tables:
                    for table in tables.tables:
                        try:
                            df = table.to_pandas()
                            text += "\n[TABLE]\n"
                            text += df.to_html(index=False)
                            text += "\n[/TABLE]\n"
                        except:
                            pass
                text += page_text
            def is_meaningful(t):
                import re
                clean = re.sub(r'<[^>]+>', '', t)
                clean = re.sub(r'\s+', ' ', clean).strip()
                words = [w for w in clean.split() if len(w) > 2]
                return len(words) > 50

            if not is_meaningful(text):
                from doc_intelligence import extract_with_document_intelligence
                di_text = extract_with_document_intelligence(pdf_bytes)
                if di_text and is_meaningful(di_text):
                    text = di_text
                else:
                    text = extract_with_vision(pdf_bytes, blob.name)
            all_text.append({"filename": blob.name, "content": text})

    for blob in container_client.list_blobs():
        if (blob.name.endswith(".xlsx") or blob.name.endswith(".xls")) and blob.name not in cached_filenames:
            blob_client = container_client.get_blob_client(blob.name)
            file_bytes = blob_client.download_blob().readall()
            from excel_extractor import extract_text_from_excel
            text = extract_text_from_excel(file_bytes, blob.name)
            all_text.append({"filename": blob.name, "content": text})

    for blob in container_client.list_blobs():
        if (blob.name.endswith(".docx") or blob.name.endswith(".doc")) and blob.name not in cached_filenames:
            blob_client = container_client.get_blob_client(blob.name)
            file_bytes = blob_client.download_blob().readall()
            from word_extractor import extract_text_from_word
            text = extract_text_from_word(file_bytes, blob.name)
            all_text.append({"filename": blob.name, "content": text})

    try:
        cache_blob = container_client.get_blob_client(cache_blob_name)
        cache_blob.upload_blob(json.dumps(all_text), overwrite=True)
    except Exception:
        pass

    return all_text

def extract_with_vision(pdf_bytes, filename):
    import base64
    from pdf2image import convert_from_bytes
    import io
    full_text = ""
    try:
        images = convert_from_bytes(pdf_bytes, dpi=150, first_page=1, last_page=10)
        for i, image in enumerate(images):
            color_ratio = detect_color_content(image)
            image = preprocess_image(image, color_ratio)
            has_color = color_ratio > 0.05
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
            color_note = "This document contains color annotations. Red typically indicates revisions or rejections, blue indicates cold water systems, green indicates sanitary systems. Note the color of important annotations alongside their content." if has_color else "Return the extracted text only."
            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_data}"}
                            },
                            {
                                "type": "text",
                                "text": "You are reading a construction document. Extract ALL text including upside down or rotated text. Mark circled items as CIRCLED: [item], highlighted text as HIGHLIGHTED: [item], handwritten notes as ANNOTATION: [note], red markups as REVISION: [content], stamps as STAMP: [content]. Ignore coffee stains and paper damage. Note color coded elements."

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

def ask_question_stream(question, documents):
    from pinecone_store import search_pinecone

    pinecone_context = search_pinecone(question, client)
    if pinecone_context:
        context = pinecone_context
        context += enrich_with_glossary(question, glossary)
        procore_keywords = ["rfi", "submittal", "procore", "procure", "procore", "prorcore", "approved", "rejected", "pending", "project"]
        if any(word in question.lower() for word in procore_keywords):
            try:
                from procore_rag import fetch_procore_context
                procore_context = fetch_procore_context(question)
                if procore_context:
                    context += procore_context
            except Exception as e:
                print("Procore error: " + str(e))
        stream = client.chat.completions.create(
            model=deployment,
            stream=True,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert assistant for a mechanical contracting company. "
                        "Answer questions based on the provided construction documents and any Procore project data included in the context. "
                        "Always cite the document name and relevant details in your answer. "
                        "If the answer is not in the documents, say so clearly.\n\n"
                        "Documents:" + context
                    )
                },
                {"role": "user", "content": question}
            ]
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
        return

    from toc_extractor import extract_toc, extract_section_text
    from section_router import route_question_to_section
    from azure.storage.blob import BlobServiceClient

    storage_key = os.getenv("AZURE_STORAGE_KEY") or st.secrets.get("AZURE_STORAGE_KEY")
    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT") or st.secrets.get("AZURE_STORAGE_ACCOUNT")
    container = os.getenv("AZURE_STORAGE_CONTAINER") or st.secrets.get("AZURE_STORAGE_CONTAINER")
    connect_str = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_client = blob_service_client.get_container_client(container)

    context = ""
    citation_notes = []

    for doc in documents:
        filename = doc["filename"]
        try:
            blob_client = container_client.get_blob_client(filename)
            pdf_bytes = blob_client.download_blob().readall()
            toc = extract_toc(pdf_bytes)
            match = route_question_to_section(question, toc)
            if match:
                for section in match:
                    section_text = extract_section_text(pdf_bytes, section["start_page"], section["end_page"])
                    context += "\n\nDocument: " + filename
                    context += "\nSection: " + section["title"] + " (Pages " + str(section["start_page"]) + "-" + str(section["end_page"]) + ")\n"
                    context += section_text[:20000]
                    citation_notes.append(filename + " -> " + section["title"] + ", p." + str(section["start_page"]))
                context += "\n\nFull document fallback: " + filename + "\n" + doc["content"][:50000]
            else:
                context += "\n\nDocument: " + filename + "\n" + doc["content"][:3000]
                citation_notes.append(filename + " -> full document search")
        except Exception as e:
            context += "\n\nDocument: " + filename + "\n" + doc["content"][:3000]

    context += enrich_with_glossary(question, glossary)

    from thefuzz import fuzz
    email_keywords = ["email", "wrote", "sent", "said", "submittal", "approved", "engineer", "correspondence", "message", "confirm", "rfi", "vendor", "contractor"]
    question_words = question.lower().split()
    email_trigger = any(
        any(fuzz.ratio(qword, keyword) > 80 for keyword in email_keywords)
        for qword in question_words
    )
    if email_trigger:
        try:
            from email_rag import fetch_emails, format_emails_for_context
            user_email = os.getenv("OUTLOOK_USER_EMAIL") or st.secrets.get("OUTLOOK_USER_EMAIL")
            if user_email:
                emails = fetch_emails(user_email, max_emails=30)
                if emails:
                    context += "\n\nRECENT EMAILS:\n"
                    context += format_emails_for_context(emails)
        except Exception as e:
            print("Procore error: " + str(e))

    procore_keywords = ["rfi", "submittal", "procore", "procure", "prorcore", "approved", "rejected", "pending", "project"]
    if any(word in question.lower() for word in procore_keywords):
        try:
            from procore_rag import fetch_procore_context
            procore_context = fetch_procore_context(question)
            print("PROCORE CONTEXT:", procore_context[:200])
            if procore_context:
                context += procore_context
        except Exception as e:
            print("Procore error: " + str(e)) 

    citation_hint = "\n\nSections searched: " + "; ".join(citation_notes)

    stream = client.chat.completions.create(
        model=deployment,
        stream=True,
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are an expert assistant for a mechanical contracting company. "
                    f"Answer questions based on the provided construction documents and any Procore project data included in the context. "
                    f"Always cite the document name, section title, and page number in your answer. "
                    f"If the answer is not in the documents, say so clearly.\n\n"
                    f"Documents:{context}{citation_hint}"
                )
            },
            {"role": "user", "content": question}
        ]
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


st.set_page_config(page_title="Fieldbook")

st.markdown("""
<style>
#MainMenu {visibility: hidden;}
header [data-testid="stToolbar"] {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

st.title("Fieldbook")
st.caption("Your personal AI-powered mechanical contracting assistant.")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "documents" not in st.session_state:
    with st.spinner("Initializing document database..."):
        st.session_state.documents = extract_text_from_storage()

for message in st.session_state.messages:
    if message["role"] == "assistant":
        with st.chat_message("assistant", avatar="👷"):
            st.markdown(message["content"])
    else:
        with st.chat_message("user"):
            st.markdown(message["content"])





if prompt := st.chat_input("Ask about your construction documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="👷"):
        response = st.write_stream(ask_question_stream(prompt, st.session_state.documents))
    st.session_state.messages.append({"role": "assistant", "content": response})
