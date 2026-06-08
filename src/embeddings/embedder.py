import os, requests
from dotenv import load_dotenv
load_dotenv()

BASE_URL   = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
EMBED_MODEL = os.getenv("EMBED_MODEL") or os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBED_URL  = BASE_URL.rstrip("/") + "/embeddings"

def embed(text):
    """Embed a single text string into a vector."""
    resp = requests.post(EMBED_URL, json={
        "model": EMBED_MODEL,
        "input": text
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "data" in data:
        return data["data"][0]["embedding"]
    return data["embedding"]

def embed_batch(texts, timeout=120):
    """Embed multiple texts in one API call. Returns list of vectors in same order."""
    resp = requests.post(EMBED_URL, json={
        "model": EMBED_MODEL,
        "input": texts
    }, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if "data" in data:
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [d["embedding"] for d in sorted_data]
    return [data["embedding"]]

def build_embed_text(contact):
    parts = []
    if contact.get("name"):
        parts.append(f"{contact['name']} works at {contact.get('company', 'unknown')}")
    if contact.get("city") or contact.get("country"):
        loc = ", ".join(filter(None, [contact.get("city"), contact.get("country")]))
        parts.append(f"based in {loc}")
    if contact.get("industry"):
        parts.append(f"Industry: {contact['industry']}")
    if contact.get("status"):
        parts.append(f"Status: {contact['status']}")
    if contact.get("tags"):
        tags = contact["tags"] if isinstance(contact["tags"], list) else [contact["tags"]]
        parts.append(f"Tags: {', '.join(str(t) for t in tags)}")
    if contact.get("notes"):
        parts.append(f"Notes: {contact['notes']}")
    if contact.get("assigned_to"):
        parts.append(f"Assigned to {contact['assigned_to']}")
    return ". ".join(parts) + "."
