# First run — create the local system of record

The bot's application records live in a local sqlite database. On first use (the
`sqlite_db` artifact in `required_artifacts.yaml` is missing), create it from the
shipped schema:

```
mkdir -p ~/.hermes/data/oteny-permit-filer-demo
sqlite3 ~/.hermes/data/oteny-permit-filer-demo/permits.db < skills/talents/oteny-permit-filer-demo/scripts/init.sql
```

The schema is idempotent (`CREATE TABLE IF NOT EXISTS`) — re-running it is safe.
Seed a test row when the owner wants a dry run:

```
sqlite3 ~/.hermes/data/oteny-permit-filer-demo/permits.db "INSERT INTO permit_applications (applicant_name, company, permit_type, start_date, municipality, street, house_number, postcode, city, has_insurance, night_work) VALUES ('Ada Lovelace', 'Analytical Engines BV', 'Scaffolding', '01-08-2026', 'Rivertown', 'Main Street', '1', '1234 AB', 'Rivertown', 'Yes', 'No');"
```

Then `selfcheck` reports READY and the filing checklist can run.
