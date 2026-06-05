"""
Generates realistic CRM seed data and writes seed.sql.
Run: python generate_seed.py
Then: docker exec -i crm_pg psql -U crm -d crm < seed.sql
"""
import random, datetime, textwrap

random.seed(42)

# ── Source data pools ─────────────────────────────────────────
FIRST = ["Alice","Bob","Carol","David","Eva","Frank","Grace",
         "Henry","Iris","James","Karen","Leo","Maya","Nate",
         "Olivia","Peter","Quinn","Rachel","Sam","Tina",
         "Umar","Vera","Will","Xuan","Yuki","Zara","Minh",
         "Linh","Huy","Thanh","Bao","Khanh","Lan","Duc"]

LAST  = ["Nguyen","Tran","Le","Smith","Jones","Brown","Wilson",
         "Patel","Chen","Kim","Park","Muller","Schmidt","Garcia",
         "Martinez","Silva","Santos","Johansson","Larsson","Tan",
         "Lim","Wong","Yamamoto","Suzuki","Hoang","Pham","Do"]

COMPANIES = [
    ("TechCorp VN","saas","Ho Chi Minh City","VN"),
    ("Acme Insurance","insurance","Sydney","AU"),
    ("Berlin Fintech GmbH","fintech","Berlin","DE"),
    ("SG Capital","fintech","Singapore","SG"),
    ("Mumbai Software","saas","Mumbai","IN"),
    ("NY Ventures","fintech","New York","US"),
    ("SP Tech","saas","São Paulo","BR"),
    ("Seoul Digital","saas","Seoul","KR"),
    ("CloudCo HK","saas","Hong Kong","HK"),
    ("Nordic Insurance AB","insurance","Stockholm","SE"),
    ("Global Re","insurance","London","GB"),
    ("HCM Dev Studio","saas","Ho Chi Minh City","VN"),
    ("VietSoft","saas","Hanoi","VN"),
    ("Bangkok FS","fintech","Bangkok","TH"),
    ("Cairo Tech","saas","Cairo","EG"),
    ("CDMX Solutions","saas","Mexico City","MX"),
    ("Warsaw IT","saas","Warsaw","PL"),
    ("Dubai Insure","insurance","Dubai","AE"),
    ("Cape Town Digital","saas","Cape Town","ZA"),
    ("Jakarta Systems","saas","Jakarta","ID"),
]

PRODUCTS = ["workers_comp","ctp","liability","property","cyber","life"]
OWNERS   = ["sales_alice","sales_bob","sales_carol","sales_david"]
SOURCES  = ["website","referral","cold_outreach","event","partner"]
STATUSES = ["active","active","active","lead","lead","inactive","churned"]
STAGES   = ["prospecting","qualified","proposal","negotiation",
            "closed_won","closed_won","closed_lost"]
STAGE_PROB = {
    "prospecting":10,"qualified":25,"proposal":50,
    "negotiation":75,"closed_won":100,"closed_lost":0
}

TAG_POOL = ["vip","renewal-risk","upsell","new-logo",
            "enterprise","smb","do-not-call","referral"]

used_emails = set()

def unique_email(first, last, company):
    domain = company.lower().replace(" ","").replace(",","")[:12] + ".com"
    base   = f"{first.lower()}.{last.lower()}"
    email  = f"{base}@{domain}"
    if email in used_emails:
        email = f"{base}{random.randint(2,99)}@{domain}"
    used_emails.add(email)
    return email

def rand_date(start_days_ago=730, end_days_ago=1):
    d = random.randint(end_days_ago, start_days_ago)
    return (datetime.date.today() - datetime.timedelta(days=d)).isoformat()

def pg_array(lst):
    if not lst: return "NULL"
    escaped = [f'"{t}"' for t in lst]
    return "ARRAY[" + ",".join(escaped) + "]"

def pg_str(s):
    if s is None: return "NULL"
    return "'" + s.replace("'","''") + "'"

# ── Generate contacts ─────────────────────────────────────────
NUM_CONTACTS = 80000
contacts = []
for i in range(NUM_CONTACTS):
    first   = random.choice(FIRST)
    last    = random.choice(LAST)
    comp    = random.choice(COMPANIES)
    email   = unique_email(first, last, comp[0])
    status  = random.choice(STATUSES)
    source  = random.choice(SOURCES)
    owner   = random.choice(OWNERS)
    tags    = random.sample(TAG_POOL, k=random.randint(0,3))
    note    = random.choice([None, "Interested in renewal", "Referred by partner",
                             "Attended webinar Q1", "Demo requested", "Budget approved"])
    contacts.append({
        "name":       f"{first} {last}",
        "email":      email,
        "company":    comp[0],
        "industry":   comp[1],
        "city":       comp[2],
        "country":    comp[3],
        "status":     status,
        "source":     source,
        "assigned_to":owner,
        "tags":       tags,
        "notes":      note,
        "created_at": rand_date(730, 30),
    })

# ── Generate deals ────────────────────────────────────────────
NUM_DEALS = 8000
deals = []
contact_indices = list(range(NUM_CONTACTS))
random.shuffle(contact_indices)

for i in range(NUM_DEALS):
    cid     = contact_indices[i % NUM_CONTACTS] + 1  # 1-based
    stage   = random.choice(STAGES)
    product = random.choice(PRODUCTS)
    company = contacts[cid-1]["company"]
    title   = f"{company} – {product.replace('_',' ').title()} {random.choice(['licence','contract','renewal','expansion','pilot'])}"
    value   = round(random.choice([
        random.uniform(5000,25000),
        random.uniform(25000,100000),
        random.uniform(100000,500000),
    ]), -2)
    close_d = rand_date(60, -120)  # some in the future
    deals.append({
        "contact_id":  cid,
        "title":       title,
        "value":       value,
        "stage":       stage,
        "probability": STAGE_PROB[stage],
        "owner":       contacts[cid-1]["assigned_to"],
        "close_date":  close_d,
        "product":     product,
    })

# ── Generate activities ───────────────────────────────────────
activities = []
act_types   = ["call","email","meeting","note","demo"]
act_summaries = {
    "call":    ["Discussed renewal terms","Followed up on proposal","Intro call completed"],
    "email":   ["Sent proposal PDF","Follow-up after demo","Shared pricing sheet"],
    "meeting": ["Quarterly business review","Discovery meeting","Contract review"],
    "note":    ["Budget confirmed for Q2","Decision expected next month","Champion identified"],
    "demo":    ["Full product demo completed","Pilot demo scheduled","Technical demo done"],
}
for d in deals[:20]:
    n_acts = random.randint(1, 4)
    for _ in range(n_acts):
        atype = random.choice(act_types)
        activities.append({
            "contact_id": d["contact_id"],
            "deal_id":    deals.index(d)+1,
            "type":       atype,
            "summary":    random.choice(act_summaries[atype]),
            "created_by": d["owner"],
            "created_at": rand_date(90, 1),
        })

# ── Write seed.sql ────────────────────────────────────────────
lines = ["-- Auto-generated seed data", "-- Run: docker exec -i crm_pg psql -U crm -d crm < seed.sql", ""]
lines.append("TRUNCATE activities, deals, contacts RESTART IDENTITY CASCADE;")
lines.append("")

lines.append("INSERT INTO contacts (name,email,company,industry,city,country,status,source,assigned_to,tags,notes,created_at) VALUES")
rows = []
for c in contacts:
    rows.append(
        f"  ({pg_str(c['name'])},{pg_str(c['email'])},{pg_str(c['company'])},"
        f"{pg_str(c['industry'])},{pg_str(c['city'])},{pg_str(c['country'])},"
        f"{pg_str(c['status'])},{pg_str(c['source'])},{pg_str(c['assigned_to'])},"
        f"{pg_array(c['tags'])},{pg_str(c['notes'])},{pg_str(c['created_at'])})"
    )
lines.append(",\n".join(rows) + ";")
lines.append("")

lines.append("INSERT INTO deals (contact_id,title,value,stage,probability,owner,close_date,product) VALUES")
rows = []
for d in deals:
    rows.append(
        f"  ({d['contact_id']},{pg_str(d['title'])},{d['value']:.2f},"
        f"{pg_str(d['stage'])},{d['probability']},{pg_str(d['owner'])},"
        f"{pg_str(d['close_date'])},{pg_str(d['product'])})"
    )
lines.append(",\n".join(rows) + ";")
lines.append("")

lines.append("INSERT INTO activities (contact_id,deal_id,type,summary,created_by,created_at) VALUES")
rows = []
for a in activities:
    rows.append(
        f"  ({a['contact_id']},{a['deal_id']},{pg_str(a['type'])},"
        f"{pg_str(a['summary'])},{pg_str(a['created_by'])},{pg_str(a['created_at'])})"
    )
lines.append(",\n".join(rows) + ";")
lines.append("")
lines.append("-- Verify")
lines.append("SELECT 'contacts' AS tbl, COUNT(*) FROM contacts")
lines.append("UNION ALL SELECT 'deals', COUNT(*) FROM deals")
lines.append("UNION ALL SELECT 'activities', COUNT(*) FROM activities;")

with open("seed_gen.sql","w") as f:
    f.write("\n".join(lines))

print(f"Written seed_gen.sql: {NUM_CONTACTS} contacts, {NUM_DEALS} deals, {len(activities)} activities")