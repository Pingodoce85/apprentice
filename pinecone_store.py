import os
import time
from pinecone import Pinecone, ServerlessSpec

def get_pinecone_index():
    api_key = os.getenv('PINECONE_API_KEY')
    pc = Pinecone(api_key=api_key)
    index_name = "fieldbook"
    if index_name not in [i.name for i in pc.list_indexes()]:
        pc.create_index(
            name=index_name,
            dimension=1536,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
    return pc.Index(index_name)

def get_embedding(text, client, deployment="text-embedding-ada-002"):
    text = text[:8000]
    response = client.embeddings.create(
        input=text,
        model=deployment
    )
    return response.data[0].embedding

def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks[:100]

def index_document(filename, content, client):
    index = get_pinecone_index()
    chunks = chunk_text(content)
    vectors = []
    for i, chunk in enumerate(chunks):
        try:
            embedding = get_embedding(chunk, client)
            vector_id = filename.replace(" ", "_")[:40] + "_chunk_" + str(i)
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "filename": filename,
                    "chunk_index": i,
                    "text": chunk
                }
            })
            time.sleep(0.1)
        except Exception as e:
            print("Embedding error:", e)
            continue
    batch_size = 25
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        try:
            index.upsert(vectors=batch)
        except Exception as e:
            print("Upsert error:", e)
    print(f"Indexed {len(vectors)} chunks from {filename}")

def search_pinecone(question, client, top_k=5):
    index = get_pinecone_index()
    query_embedding = get_embedding(question, client)
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    context = ""
    for match in results.matches:
        if match.score > 0.7:
            context += "\n\nDocument: " + match.metadata["filename"]
            context += "\n" + match.metadata["text"]
    return context
