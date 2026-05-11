import chainlit as cl
import pymupdf
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_KEY")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=api_key,
    api_version="2024-02-01"
)

def load_documents():
    from azure.storage.blob import BlobServiceClient
    storage_key = os.getenv("AZURE_STORAGE_KEY")
    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT")
    container = os.getenv("AZURE_STORAGE_CONTAINER")
    connect_str = f"DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key};EndpointSuffix=core.windows.net"
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_client = blob_service_client.get_container_client(container)
    all_text = []
    for blob in container_client.list_blobs():
        if blob.name.endswith(".pdf"):
            blob_client = container_client.get_blob_client(blob.name)
            pdf_bytes = blob_client.download_blob().readall()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            all_text.append({"filename": blob.name, "content": text})
    return all_text

@cl.on_chat_start
async def start():
    docs = load_documents()
    cl.user_session.set("documents", docs)
    await cl.Message(content=f"Welcome to **Apprentice** — your AI-powered mechanical contracting assistant. Loaded {len(docs)} documents. Ask me anything!").send()

@cl.on_message
async def main(message: cl.Message):
    documents = cl.user_session.get("documents") or []
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
            {"role": "user", "content": message.content}
        ]
    )
    answer = response.choices[0].message.content
    await cl.Message(content=answer).send()
