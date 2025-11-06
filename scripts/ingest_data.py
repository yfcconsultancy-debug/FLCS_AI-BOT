# scripts/ingest_data.py
import os, time, uuid
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from pypdf import PdfReader
import cohere

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
INDEX_NAME = os.getenv("PINECONE_INDEX", "flcs-chatbot")

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
EMBED_MODEL = os.getenv("COHERE_EMBED_MODEL", "embed-english-v3.0")

assert PINECONE_API_KEY and COHERE_API_KEY, "Missing API keys."

pc = Pinecone(api_key=PINECONE_API_KEY)
co = cohere.Client(COHERE_API_KEY)

def ensure_index():
    names = pc.list_indexes().names()
    if INDEX_NAME not in names:
        print(f"Creating Pinecone index '{INDEX_NAME}' ...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=1024,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=PINECONE_ENV)
        )
        while not pc.describe_index(INDEX_NAME).status["ready"]:
            time.sleep(5)
    print(f"Index '{INDEX_NAME}' ready.")

def read_pdfs_text(data_dir):
    docs = []
    for root, _, files in os.walk(data_dir):
        for f in files:
            if f.lower().endswith(".pdf"):
                path = os.path.join(root, f)
                try:
                    reader = PdfReader(path)
                    for i, page in enumerate(reader.pages):
                        text = (page.extract_text() or "").strip()
                        if text:
                            docs.append({
                                "id": str(uuid.uuid4()),
                                "text": text,
                                "meta": {"source": f, "page": i+1}
                            })
                except Exception as e:
                    print(f"Warning: Could not read {f}. Error: {e}")
    return docs

def embed_texts(texts):
    resp = co.embed(model=EMBED_MODEL, input_type="search_document", texts=texts)
    return resp.embeddings

def upsert_pinecone(docs):
    index = pc.Index(INDEX_NAME)
    BATCH = 64
    for i in range(0, len(docs), BATCH):
        chunk = docs[i:i+BATCH]
        try:
            vectors = embed_texts([d["text"] for d in chunk])
            items = []
            for d, v in zip(chunk, vectors):
                items.append({
                    "id": d["id"],
                    "values": v,
                    "metadata": d["meta"] | {"text": d["text"]},
                })
            index.upsert(vectors=items)
            print(f"Upserted {i+len(chunk)}/{len(docs)}")
        except Exception as e:
            print(f"Error embedding/upserting batch {i}: {e}")

def main():
    ensure_index()
    data_dir = os.path.join(BASE_DIR, "data")
    assert os.path.isdir(data_dir), f"Missing folder: {data_dir}"
    docs = read_pdfs_text(data_dir)
    if not docs:
        print("No extractable text found in PDFs under /data. Add PDFs.")
        return
    upsert_pinecone(docs)
    print("✅ Ingestion complete.")

if __name__ == "__main__":
    main()