-- ==========================================
-- Generate 80,000 Contacts
-- ==========================================

INSERT INTO contacts (
    name,
    email,
    company,
    phone,
    city,
    status,
    created_at,
    updated_at
)
SELECT
    'Contact ' || gs,
    'contact' || gs || '@example.com',
    'Company ' || ((gs % 5000) + 1),
    '+84 9' || LPAD((10000000 + gs)::text, 8, '0'),
    (
        ARRAY[
            'Ho Chi Minh City',
            'Hanoi',
            'Da Nang',
            'Can Tho',
            'Singapore',
            'Bangkok',
            'Sydney',
            'New York'
        ]
    )[1 + (random() * 7)::int],
    (
        ARRAY[
            'active',
            'inactive',
            'lead'
        ]
    )[1 + (random() * 2)::int],
    NOW() - (random() * interval '3 years'),
    NOW()
FROM generate_series(1, 80000) gs;


-- ==========================================
-- Generate 8,000 Deals
-- ==========================================

INSERT INTO deals (
    contact_id,
    title,
    value,
    stage,
    owner,
    created_at,
    updated_at
)
SELECT
    FLOOR(random() * 80000 + 1)::int,
    'Deal #' || gs,
    ROUND((random() * 500000 + 1000)::numeric, 2),
    (
        ARRAY[
            'prospecting',
            'qualified',
            'proposal',
            'negotiation',
            'closed_won',
            'closed_lost'
        ]
    )[1 + (random() * 5)::int],
    (
        ARRAY[
            'sales_alice',
            'sales_bob',
            'sales_carol',
            'sales_david',
            'sales_emma'
        ]
    )[1 + (random() * 4)::int],
    NOW() - (random() * interval '2 years'),
    NOW()
FROM generate_series(1, 8000) gs;