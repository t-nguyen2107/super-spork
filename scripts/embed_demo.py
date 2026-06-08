"""Quick embed of first 30 contacts for demo purposes."""
import os, sys, psycopg2, psycopg2.extras

# Add project root to path for src imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv
from src.embeddings.embedder import embed, build_embed_text, EMBED_MODEL
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

conn = psycopg2.connect(
    host=os.getenv("PG_HOST"), port=os.getenv("PG_PORT"),
    dbname=os.getenv("PG_DB"), user=os.getenv("PG_USER"),
    password=os.getenv("PG_PASSWORD"),
    cursor_factory=psycopg2.extras.RealDictCursor
)

cur = conn.cursor()
cur.execute("SELECT * FROM contacts ORDER BY id LIMIT 30")
contacts = cur.fetchall()
print(f"Embedding {len(contacts)} contacts...")

for i, contact in enumerate(contacts):
    text = build_embed_text(dict(contact))
    vector = embed(text)
    name = contact["name"]
    cid = contact["id"]
    with conn.cursor() as cur2:
        cur2.execute("""
            INSERT INTO contact_embeddings (contact_id, embedding, embed_text, model, updated_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (contact_id) DO UPDATE SET
                embedding = EXCLUDED.embedding, embed_text = EXCLUDED.embed_text,
                model = EXCLUDED.model, updated_at = now()
        """, (cid, str(vector), text, EMBED_MODEL))
    conn.commit()
    print(f"  {i+1}/{len(contacts)} {name}")

cur.execute("SELECT COUNT(*) AS n FROM contact_embeddings")
print(f"Total embeddings: {cur.fetchone()['n']}")
conn.close()
