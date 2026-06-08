CREATE TABLE contacts (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL,
    email        TEXT UNIQUE,
    company      TEXT,
    phone        TEXT,
    city         TEXT,
    industry     TEXT,
    country      TEXT,
    status       TEXT DEFAULT 'active',
    source       TEXT,
    assigned_to  TEXT,
    tags         TEXT[] DEFAULT '{}',
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE deals (
    id           SERIAL PRIMARY KEY,
    contact_id   INT REFERENCES contacts(id),
    title        TEXT NOT NULL,
    value        NUMERIC(12,2),
    stage        TEXT DEFAULT 'prospecting',
    probability  INT DEFAULT 0,
    owner        TEXT,
    close_date   DATE,
    product      TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE activities (
    id           SERIAL PRIMARY KEY,
    contact_id   INT REFERENCES contacts(id),
    deal_id      INT REFERENCES deals(id),
    type         TEXT,
    summary      TEXT,
    created_by   TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_contacts_status      ON contacts(status);
CREATE INDEX idx_contacts_company     ON contacts(company);
CREATE INDEX idx_contacts_city        ON contacts(city);
CREATE INDEX idx_contacts_assigned    ON contacts(assigned_to);
CREATE INDEX idx_deals_stage          ON deals(stage);
CREATE INDEX idx_deals_contact        ON deals(contact_id);
CREATE INDEX idx_deals_owner          ON deals(owner);
CREATE INDEX idx_deals_close_date     ON deals(close_date);
CREATE INDEX idx_activities_contact   ON activities(contact_id);
CREATE INDEX idx_activities_deal      ON activities(deal_id);