-- Demo permit filer — the local system of record (idempotent; re-runnable).
-- In a REAL business bot this table is the client's own system reached over its
-- odoo connection in a real bot; the demo keeps it local so the whole loop runs anywhere.
CREATE TABLE IF NOT EXISTS permit_applications (
    id INTEGER PRIMARY KEY,
    applicant_name TEXT NOT NULL,
    company TEXT NOT NULL,
    permit_type TEXT NOT NULL,
    start_date TEXT NOT NULL,          -- dd-mm-yyyy, as the portal expects it
    municipality TEXT NOT NULL,
    street TEXT NOT NULL,
    house_number TEXT NOT NULL,
    postcode TEXT NOT NULL,
    city TEXT NOT NULL,
    has_insurance TEXT NOT NULL,       -- 'Yes' | 'No', as the portal's radios expect
    night_work TEXT NOT NULL,          -- 'Yes' | 'No'
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | filing | filed | escalated
    confirmation_no TEXT,              -- ONLY ever a value read off the portal page
    filed_at TEXT
);
