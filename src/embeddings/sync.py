"""
Embeds contacts into contact_embeddings with multiple sync strategies.

Usage:
  python -m src.embeddings.sync              # embed only contacts without embedding
  python -m src.embeddings.sync --since 1h   # contacts updated recently + unembedded
  python -m src.embeddings.sync --smart      # smart: detect related deal/activity changes
  python -m src.embeddings.sync --force      # re-embed ALL contacts (overwrite)
"""
import os, sys, psycopg2, psycopg2.extras
from dotenv import load_dotenv
from src.embeddings.embedder import embed_batch, build_embed_text, EMBED_MODEL
load_dotenv()

# How many contacts to embed per batch (balance between speed and API limits)
BATCH_SIZE = 32

# Default lookback window for --smart mode (detects changes in last 2 hours)
SMART_LOOKBACK = "2h"


def get_conn():
    """Create a new PostgreSQL connection with dict cursor."""
    return psycopg2.connect(
        host=os.getenv("PG_HOST"), port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DB"), user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def fetch_unembedded(conn):
    """Get contacts that don't have an embedding yet."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.* FROM contacts c
            LEFT JOIN contact_embeddings e ON e.contact_id = c.id
            WHERE e.contact_id IS NULL
            ORDER BY c.id
        """)
        return cur.fetchall()


def fetch_all(conn):
    """Get ALL contacts (for --force mode, re-embed everything)."""
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM contacts ORDER BY id")
        return cur.fetchall()


def fetch_since(conn, interval):
    """Get contacts updated recently or not yet embedded."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.* FROM contacts c
            LEFT JOIN contact_embeddings e ON e.contact_id = c.id
            WHERE c.updated_at > now() - %s::interval
               OR e.contact_id IS NULL
            ORDER BY c.id
        """, (interval,))
        return cur.fetchall()


def fetch_smart(conn, lookback=None):
    """
    Smart sync: find contacts that need re-embedding because their
    RELATED data (deals, activities) changed, even if the contact
    row itself was not updated.

    Detects:
    1. Contacts with no embedding yet
    2. Contacts whose own row was updated recently
    3. Contacts whose deals were created/updated recently
    4. Contacts whose activities were created recently

    Uses UNION to combine all contact IDs, then fetches full rows.
    """
    if lookback is None:
        lookback = SMART_LOOKBACK

    # Step 1: Collect all contact IDs that need re-embedding
    with conn.cursor() as cur:
        cur.execute("""
            -- Contacts with no embedding at all
            SELECT c.id FROM contacts c
            LEFT JOIN contact_embeddings e ON e.contact_id = c.id
            WHERE e.contact_id IS NULL

            UNION

            -- Contacts whose own data changed (name, company, industry, etc.)
            SELECT c.id FROM contacts c
            JOIN contact_embeddings e ON e.contact_id = c.id
            WHERE c.updated_at > e.updated_at

            UNION

            -- Contacts whose own data changed within lookback window
            SELECT id FROM contacts
            WHERE updated_at > now() - %s::interval

            UNION

            -- Contacts with deals that were recently created or updated
            -- (deal stage/value/product changes affect contact context)
            SELECT DISTINCT contact_id FROM deals
            WHERE updated_at > now() - %s::interval
               OR created_at > now() - %s::interval

            UNION

            -- Contacts with recent activities (calls, meetings, emails)
            -- (new activity = new context about the contact)
            SELECT DISTINCT contact_id FROM activities
            WHERE created_at > now() - %s::interval
        """, (lookback, lookback, lookback, lookback))

        # Get deduplicated contact IDs from the UNION above
        contact_ids = [row["id"] for row in cur.fetchall()]

    if not contact_ids:
        return []

    # Step 2: Fetch full contact rows for those IDs
    with conn.cursor() as cur:
        # Use ANY(array) instead of IN for large ID lists
        cur.execute("""
            SELECT * FROM contacts
            WHERE id = ANY(%s)
            ORDER BY id
        """, (contact_ids,))
        return cur.fetchall()


def enrich_embed_text(conn, contact):
    """
    Enrich the embedding text with deal and activity context.
    This makes the embedding more useful for semantic search because
    it captures not just who the contact is, but what's happening with them.

    Example enrichment:
      "John works at Acme Corp. Industry: SaaS.
       Active deals: 2 deals ($150k total) in negotiation.
       Recent activity: Meeting about contract renewal."
    """
    parts = []

    # Base contact info
    base_text = build_embed_text(dict(contact))
    parts.append(base_text.rstrip("."))

    # Add deal summary (stage + count + total value)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT stage, COUNT(*) AS deal_count, COALESCE(SUM(value), 0) AS total_value
            FROM deals
            WHERE contact_id = %s
            GROUP BY stage
            ORDER BY total_value DESC
        """, (contact["id"],))
        deal_summary = cur.fetchall()

    if deal_summary:
        deal_parts = []
        total_deals = 0
        total_value = 0
        for row in deal_summary:
            deal_parts.append(f"{row['stage']}: {row['deal_count']} deal(s) ${row['total_value']:,.0f}")
            total_deals += row["deal_count"]
            total_value += float(row["total_value"])
        parts.append(f"Deals: {total_deals} total (${total_value:,.0f}) — {'; '.join(deal_parts)}")

    # Add latest activity summary (top 5 most recent)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT type, summary, created_at
            FROM activities
            WHERE contact_id = %s
            ORDER BY created_at DESC
            LIMIT 5
        """, (contact["id"],))
        activities = cur.fetchall()

    if activities:
        act_parts = [f"{a['type']}: {a['summary']}" for a in activities if a["summary"]]
        if act_parts:
            parts.append(f"Recent activity: {'; '.join(act_parts)}")

    return ". ".join(parts) + "."


def insert_batch(conn, rows):
    """Insert/update a batch of (contact_id, vector_str, text, model) tuples."""
    with conn.cursor() as cur:
        args_str = ",".join(
            cur.mogrify("(%s, %s, %s, %s, now())", (cid, vec, txt, EMBED_MODEL)).decode()
            for cid, vec, txt in rows
        )
        cur.execute(f"""
            INSERT INTO contact_embeddings
                (contact_id, embedding, embed_text, model, updated_at)
            VALUES {args_str}
            ON CONFLICT (contact_id) DO UPDATE SET
                embedding  = EXCLUDED.embedding,
                embed_text = EXCLUDED.embed_text,
                model      = EXCLUDED.model,
                updated_at = now()
        """)
    conn.commit()


def embed_contacts(contacts, conn, enrich=False):
    """
    Core embedding loop: batch embed a list of contacts.

    Args:
        contacts: list of RealDictRow contacts
        conn: active DB connection
        enrich: if True, use enriched text (deals + activities) instead of just contact fields
    """
    total = len(contacts)
    print(f"Embedding {total} contacts with {EMBED_MODEL} (batch={BATCH_SIZE}, enrich={enrich})...")
    ok, err = 0, 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = contacts[batch_start:batch_start + BATCH_SIZE]
        try:
            # Build embed text — optionally enriched with deal/activity context
            if enrich:
                texts = [enrich_embed_text(conn, c) for c in batch]
            else:
                texts = [build_embed_text(dict(c)) for c in batch]

            # Single API call for the whole batch
            vectors = embed_batch(texts)

            # Prepare rows for batch INSERT
            rows = [
                (c["id"], str(vec), txt)
                for c, vec, txt in zip(batch, vectors, texts)
            ]
            insert_batch(conn, rows)
            ok += len(batch)
            done = batch_start + len(batch)
            if done % 320 == 0 or done == total:
                print(f"  {done}/{total} done ({ok} ok, {err} err)")
        except Exception as e:
            # If batch fails, fall back to one-by-one for this batch
            conn.rollback()
            print(f"  Batch {batch_start} failed ({e}), retrying one-by-one...")
            for contact in batch:
                try:
                    if enrich:
                        text = enrich_embed_text(conn, contact)
                    else:
                        text = build_embed_text(dict(contact))
                    vec = embed_batch([text])[0]
                    insert_batch(conn, [(contact["id"], str(vec), text)])
                    ok += 1
                except Exception as e2:
                    conn.rollback()
                    print(f"  x contact {contact['id']}: {e2}")
                    err += 1

    print(f"\nDone. {ok} embedded, {err} errors.")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM contact_embeddings")
        print(f"Total in contact_embeddings: {cur.fetchone()['n']}")


def sync(since_interval=None, force=False, smart=False, smart_lookback=None):
    """
    Main sync entry point. Chooses which contacts to embed based on flags.

    Modes:
      default  — only embed contacts without embedding
      --since  — contacts updated in last X interval + unembedded
      --smart  — detect contacts affected by deal/activity changes (enriched text)
      --force  — re-embed everything
    """
    with get_conn() as conn:
        if force:
            print("Mode: FORCE — re-embedding all contacts")
            contacts = fetch_all(conn)
            embed_contacts(contacts, conn, enrich=False)
        elif smart:
            lookback = smart_lookback or SMART_LOOKBACK
            print(f"Mode: SMART — detecting contacts affected by deal/activity changes (lookback={lookback})")
            contacts = fetch_smart(conn, lookback)
            print(f"  Found {len(contacts)} contacts needing re-embedding")
            # Smart mode uses enriched text (includes deal/activity context)
            embed_contacts(contacts, conn, enrich=True)
        elif since_interval:
            print(f"Mode: SINCE — contacts updated in last {since_interval} + unembedded")
            contacts = fetch_since(conn, since_interval)
            embed_contacts(contacts, conn, enrich=False)
        else:
            print("Mode: DEFAULT — embedding contacts without embedding")
            contacts = fetch_unembedded(conn)
            embed_contacts(contacts, conn, enrich=False)


if __name__ == "__main__":
    force = "--force" in sys.argv
    smart = "--smart" in sys.argv
    since = None
    if "--since" in sys.argv:
        idx = sys.argv.index("--since") + 1
        if idx < len(sys.argv):
            since = sys.argv[idx]
    sync(since_interval=since, force=force, smart=smart)
