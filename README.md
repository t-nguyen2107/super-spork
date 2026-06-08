# CRM Chatbot — Local LLM + PostgreSQL + pgvector

A Python CLI chatbot that uses a **local LLM** (LM Studio) with OpenAI-compatible tool calling to query a PostgreSQL CRM database. Built as a learning project in three progressive phases.

## Quick Start

```powershell
# 1. Start PostgreSQL with pgvector
docker-compose up -d

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Initialize database schema
Get-Content sql\schema.sql | docker exec -i crm_pg psql -U crm -d crm

# 4. Seed with demo data (~30 contacts)
Get-Content sql\seed.sql | docker exec -i crm_pg psql -U crm -d crm

# 5. Run the chatbot
python main.py
```

**Prerequisites:** Docker, Python 3.10+, LM Studio running with a chat model loaded (e.g. `google/gemma-4-e4b`).

For the full 80k-contact dataset with pre-built embeddings, download [`db_embedded.sql.gz`](https://drive.google.com/file/d/1aTC7Xd5-XO_h3yuHHhMdez1WsWh5zhrR/view?usp=sharing) (287MB) and follow [RESTORE_DB.md](RESTORE_DB.md).

## Project Phases

| Phase | Focus | Status | Documentation |
|-------|-------|--------|--------------|
| **P1** — Tool Calling | LLM calls Python functions with exact SQL filters | Done | [P1 Doc](docs/P1_CRM_Chatbot_Tool_Calling.html) |
| **P2** — pgvector Search | Semantic similarity search via vector embeddings | Done | [P2 Doc](docs/P2_CRM_Chatbot_pgvector_Hybrid.html) |
| **P2 ENHANCE** — Hardening | Error handling, history window, warmup, restructure | Done | [P2 ENHANCE Doc](docs/P2_ENHANCE_CRM_Chatbot_Hardening.html) |
| **P3** — Deal Intelligence | Multi-agent RAG pipeline (planned) | Planned | [Overview](docs/CRM_Chatbot_Architecture_Overview.html) |

## Architecture

```
User Query
  ↓
LM Studio LLM (google/gemma-4-e4b)
  ↓
Tool Router (LLM picks the right tool)
  ├── search_contacts       → PostgreSQL (exact ILIKE filters)
  ├── get_deals             → PostgreSQL (stage/value/product filters)
  ├── get_contact_deals     → PostgreSQL (join: deals + contacts)
  ├── get_pipeline_summary  → PostgreSQL (GROUP BY aggregation)
  └── semantic_search       → embed query → PostgreSQL (cosine ANN + HNSW)
  ↓
LLM formats response → Rich markdown in terminal
```

## Project Structure

```
super-spork/
├── main.py                 # Entry point — runs the chatbot
├── docker-compose.yml      # pgvector/pgvector:pg16
├── requirements.txt        # Python dependencies
├── src/
│   ├── chatbot/
│   │   ├── cli.py          # Main CLI loop + tool calling + warmup
│   │   └── tools.py        # 5 OpenAI-compatible tool definitions
│   ├── db/
│   │   └── connection.py   # All SQL queries + semantic search
│   └── embeddings/
│       ├── embedder.py     # Embed text via /v1/embeddings API
│       └── sync.py         # Batch/incremental embedding
├── tests/
│   ├── test_crm.py         # 53 unit tests (mocked)
│   └── chat_scenarios.py   # 10 real chat scenarios
├── scripts/                # Utility scripts
├── sql/                    # Schema, migrations, seed data
└── docs/                   # Architecture documentation (HTML)
```

## Documentation

- [Architecture Overview](docs/CRM_Chatbot_Architecture_Overview.html) — Full system diagram and data flow
- [P1: Tool Calling](docs/P1_CRM_Chatbot_Tool_Calling.html) — How the LLM calls Python functions
- [P2: pgvector Hybrid Search](docs/P2_CRM_Chatbot_pgvector_Hybrid.html) — Semantic similarity on contacts
- [P2 ENHANCE: Production Hardening](docs/P2_ENHANCE_CRM_Chatbot_Hardening.html) — Error handling, warmup, restructure, test results

## Commands

```powershell
# Large dataset (80k contacts, 8k deals)
python scripts\generate_seed.py
Get-Content sql\seed_gen.sql | docker exec -i crm_pg psql -U crm -d crm

# P2: Apply pgvector migration + embed all contacts
Get-Content sql\migration_p2.sql | docker exec -i crm_pg psql -U crm -d crm
python -m src.embeddings.sync

# Run tests
python -m tests.test_crm           # 53 unit tests (no services needed)
python tests\chat_scenarios.py     # 10 real chat scenarios (needs LLM + DB)
```

## Tech Stack

- **LLM:** LM Studio (OpenAI-compatible API) — works with any local model
- **Database:** PostgreSQL 16 + pgvector extension (HNSW index for cosine similarity)
- **Embeddings:** nomic-embed-text (768-dim) via LM Studio `/v1/embeddings`
- **Python:** openai SDK, psycopg2, Rich (terminal formatting)
- **No cloud services** — everything runs locally

## Environment Variables

Copy `.env` and set these values:

| Variable | Purpose | Example |
|----------|---------|---------|
| `OLLAMA_BASE_URL` | LLM API endpoint | `http://127.0.0.1:1234/v1` |
| `OLLAMA_MODEL` | Chat model name | `google/gemma-4-e4b` |
| `EMBED_MODEL` | Embedding model name | `nomic-embed-text` |
| `PG_HOST` | PostgreSQL host | `localhost` |
| `PG_PORT` | PostgreSQL port | `5432` |
| `PG_DB` | Database name | `crm` |
| `PG_USER` | Database user | `crm` |
| `PG_PASSWORD` | Database password | `crm_local_pw` |
