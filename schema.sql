-- contacts table
CREATE TABLE contacts (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE,
    company     TEXT,
    phone       TEXT,
    city        TEXT,
    status      TEXT DEFAULT 'active',  -- active | inactive | lead
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- deals table
CREATE TABLE deals (
    id           SERIAL PRIMARY KEY,
    contact_id   INT REFERENCES contacts(id),
    title        TEXT NOT NULL,
    value        NUMERIC(12,2),
    stage        TEXT DEFAULT 'prospecting',
    -- stages: prospecting | qualified | proposal | negotiation | closed_won | closed_lost
    owner        TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_contacts_status  ON contacts(status);
CREATE INDEX idx_contacts_company ON contacts(company);
CREATE INDEX idx_deals_stage       ON deals(stage);
CREATE INDEX idx_deals_contact     ON deals(contact_id);