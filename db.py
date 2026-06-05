import os, psycopg2, psycopg2.extras
from dotenv import load_dotenv
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