# CRM Chatbot — Quick Start with Pre-Embedded Database

This guide lets you skip the long embedding process (~2h for 80k contacts) by restoring a pre-built database dump that already includes all contact embeddings.

## Prerequisites

- Docker running
- Python 3.10+

## Step 1: Start PostgreSQL (pgvector)

```powershell
docker-compose up -d
```

Wait ~10s for the container to be ready:

```powershell
docker exec crm_pg pg_isready -U crm
```

## Step 2: Download & Restore the Pre-Embedded Database

Download `db_embedded.sql.gz` (287MB) from [Google Drive](https://drive.google.com/file/d/1aTC7Xd5-XO_h3yuHHhMdez1WsWh5zhrR/view?usp=sharing) and place it in the project root.

The file contains:
- 80,000 contacts
- ~8,000 deals
- Activities
- 80,000 contact embeddings (768-dim vectors, nomic-embed-text model)
- All indexes including HNSW for fast cosine similarity search

**Option A: Restore directly (recommended)**

```powershell
# Copy dump into container
docker cp db_embedded.sql.gz crm_pg:/tmp/db_embedded.sql.gz

# Restore inside container (gunzip piped to psql)
docker exec crm_pg bash -c "gunzip -c /tmp/db_embedded.sql.gz | psql -U crm -d crm"
```

**Option B: If gunzip is not available in container**

```powershell
# Decompress on host first (requires 7-Zip or similar)
# Then pipe the plain SQL into psql:
Get-Content db_embedded.sql | docker exec -i crm_pg psql -U crm -d crm
```

## Step 3: Verify

```powershell
docker exec crm_pg psql -U crm -d crm -c "
  SELECT 'contacts' AS tbl, COUNT(*) FROM contacts
  UNION ALL SELECT 'deals', COUNT(*) FROM deals
  UNION ALL SELECT 'contact_embeddings', COUNT(*) FROM contact_embeddings;
"
```

Expected output:
```
         tbl          | count
----------------------+-------
 contacts             | 80000
 deals                |  ~8000
 contact_embeddings   | 80000
```

## Step 4: Install Python Dependencies

```powershell
pip install -r requirements.txt
```

## Step 5: Run the Chatbot

Make sure LM Studio is running with your LLM model, then:

```powershell
python main.py
```

## File Info

| File | Size | Contents |
|------|------|----------|
| `db_embedded.sql.gz` | 287 MB | Full DB dump with embeddings (compressed) |

## Notes

- This dump was created with `pg_dump --no-owner --no-privileges`, so it works with any PostgreSQL user
- The dump includes the `pgvector` extension (`CREATE EXTENSION IF NOT EXISTS vector`) and all HNSW indexes
- If you modify contacts after restoring, run `python -m src.embeddings.sync --since 1h` to embed only new/changed records
- To re-embed everything from scratch: `python -m src.embeddings.sync --force`
- The `.env` file is required for DB connection settings — copy from `.env.example` if needed

## Troubleshooting

**"extension vector does not exist"**
- Make sure you're using `pgvector/pgvector:pg16` image, not plain postgres. Check `docker-compose.yml`.

**"connection refused"**
- Wait for container to start: `docker exec crm_pg pg_isready -U crm`
- Check `.env` matches `docker-compose.yml` credentials

**"out of memory" during restore**
- The dump is large. If restore fails, try increasing Docker memory limit to 4GB+
