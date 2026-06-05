---
name: test-data-generator
description: Generate realistic PII-safe synthetic test data from schema definitions.
triggers:
  - test data
  - seed data
  - mock data
  - fixtures
  - fake data
  - generate data
  - faker
depends_on: []
output_schema:
  type: object
  properties:
    records_generated:
      type: integer
    fixtures_file:
      type: string
    data_format:
      type: string
      enum:
        - json
        - csv
        - sql
  required:
    - records_generated
    - fixtures_file
roles:
  - Dev
  - QA
model_tier: sonnet
---

# Test Data Generator

Generate realistic test data. Detect schema from: SQLAlchemy models, Pydantic models, TypeScript interfaces, JSON schema. Use Faker for PII-safe synthetic data (no real emails/SSNs). Output: JSON fixtures, CSV, or SQL INSERT statements. Relationships respected (FK constraints). Volume: 10-100 records default. All PII fields use fake values.

## Schema Detection

Auto-detect schema from:
- **SQLAlchemy** (`models.py`) — column types, nullable flags, FK relationships.
- **Pydantic** (`schemas.py`) — field types, validators, optional fields.
- **TypeScript** — interface definitions, type aliases.
- **JSON Schema** — `$schema`, `properties`, `required`, `$ref`.
- **Database** — `DESCRIBE table` or `\d tablename` output.

## PII-Safe Field Mapping

| Field Pattern | Faker Method | Example Output |
|--------------|--------------|----------------|
| `email`, `*_email` | `faker.email()` | `alice.smith@example.com` |
| `name`, `full_name` | `faker.name()` | `Alice Smith` |
| `first_name` | `faker.first_name()` | `Alice` |
| `last_name` | `faker.last_name()` | `Smith` |
| `phone`, `*_phone` | `faker.phone_number()` | `+1-555-0123` |
| `ssn`, `tax_id` | `faker.ssn()` | `123-45-6789` (fake) |
| `address` | `faker.address()` | `123 Fake St, Springfield` |
| `ip_address` | `faker.ipv4_private()` | `192.168.1.100` |
| `password` | `faker.password()` | `Tr0ub4dor&3` |
| `url` | `faker.url()` | `https://example.com/path` |
| `uuid`, `id` | `faker.uuid4()` | `550e8400-...` |

## Relationship Handling

- FK constraints: generate parent records first, sample valid parent IDs for child records.
- Unique constraints: track generated values, regenerate on collision.
- Enum fields: randomly sample from allowed enum values.
- Nullable fields: 20% null by default (configurable).

## Output Formats

### JSON Fixtures
```json
[
  {"id": "uuid", "name": "Alice Smith", "email": "alice@example.com"},
  ...
]
```

### CSV
```csv
id,name,email
uuid,Alice Smith,alice@example.com
```

### SQL INSERT
```sql
INSERT INTO users (id, name, email) VALUES
  ('uuid', 'Alice Smith', 'alice@example.com'),
  ...;
```

## Volume

- Default: 10 records (fast, covers basic test cases).
- Standard: 50 records (covers pagination, filtering tests).
- Stress: 100 records (covers performance and edge cases).
- Custom: specify with `count=N`.

## Rules

- Never use real personal data — all PII must be synthetic.
- Domain for email fields: always `example.com`, `test.com`, or `fake.org`.
- Dates: realistic ranges (born 1960-2000, created last 2 years).
- Amounts/prices: positive numbers in reasonable range for context.
- Seed with fixed value for reproducible output: `faker.seed(42)`.

## Output

Return `records_generated` (integer), `fixtures_file` (output file path), and `data_format` (`json | csv | sql`). Output the full fixture content as a code block.
