import os, psycopg2, psycopg2.extras
from dotenv import load_dotenv
from src.embeddings.embedder import embed as _embed
load_dotenv()

def get_conn():
    return psycopg2.connect(
        host=os.getenv("PG_HOST"), port=os.getenv("PG_PORT"),
        dbname=os.getenv("PG_DB"), user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def search_contacts(name=None, company=None, city=None, status=None, limit=10):
    clauses, params = [], []
    if name:    clauses.append("name ILIKE %s");    params.append(f"%{name}%")
    if company: clauses.append("company ILIKE %s"); params.append(f"%{company}%")
    if city:    clauses.append("city ILIKE %s");    params.append(f"%{city}%")
    if status:  clauses.append("status = %s");      params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM contacts {where} ORDER BY name LIMIT %s"
    params.append(limit)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def get_deals(stage=None, owner=None, min_value=None, max_value=None, limit=10):
    clauses, params = [], []
    if stage:     clauses.append("d.stage = %s");       params.append(stage)
    if owner:     clauses.append("d.owner = %s");       params.append(owner)
    if min_value: clauses.append("d.value >= %s");      params.append(min_value)
    if max_value: clauses.append("d.value <= %s");      params.append(max_value)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT d.*, c.name AS contact_name, c.company
        FROM deals d JOIN contacts c ON c.id = d.contact_id
        {where} ORDER BY d.value DESC LIMIT %s"""
    params.append(limit)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def get_contact_deals(contact_id):
    sql = """SELECT d.*, c.name AS contact_name FROM deals d
             JOIN contacts c ON c.id = d.contact_id
             WHERE d.contact_id = %s ORDER BY d.created_at DESC"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (contact_id,))
            return cur.fetchall()

def get_pipeline_summary():
    sql = """SELECT stage, COUNT(*) AS deal_count,
             SUM(value) AS total_value, AVG(value) AS avg_value
             FROM deals GROUP BY stage ORDER BY total_value DESC"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

def semantic_search_contacts(query, country=None, industry=None, status=None,
                             min_value=None, limit=10):
    query_vector = _embed(query)
    clauses, params = [], []
    if country:
        clauses.append("c.country = %s")
        params.append(country.upper())
    if industry:
        clauses.append("c.industry = %s")
        params.append(industry)
    if status:
        clauses.append("c.status = %s")
        params.append(status)
    if min_value:
        clauses.append("c.id IN (SELECT contact_id FROM deals WHERE value >= %s)")
        params.append(min_value)
    where = ("AND " + " AND ".join(clauses)) if clauses else ""
    sql = f"""
        SELECT c.id, c.name, c.email, c.company, c.industry,
               c.city, c.country, c.status, c.tags, c.notes,
               c.assigned_to,
               1 - (e.embedding <=> %s::vector) AS similarity_score
        FROM contacts c
        JOIN contact_embeddings e ON e.contact_id = c.id
        WHERE e.embedding IS NOT NULL
        {where}
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
    """
    vec_str = str(query_vector)
    final_params = [vec_str] + params + [vec_str, limit]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, final_params)
            return cur.fetchall()