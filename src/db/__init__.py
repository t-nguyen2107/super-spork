"""Database package — PostgreSQL connection + all CRM query functions."""
from src.db.connection import (
    get_conn,
    search_contacts,
    get_deals,
    get_contact_deals,
    get_pipeline_summary,
    semantic_search_contacts,
)
