import streamlit as st
import pymupdf
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2024-02-01"
)

def extract_text_from_pdfs(pdf_folder):
    all_text = []
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
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
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

st.set_page_config(page_title="P&J Construction GPT", page_icon="🏗️")
st.title("🏗️ P&J Construction Document Assistant")
st.caption("Ask questions about your construction specifications and standards")

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
