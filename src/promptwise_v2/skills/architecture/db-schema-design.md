---
name: db-schema-design
description: Design relational database schemas with normalization, indexes, and partitioning strategy.
triggers:
  - database schema
  - db design
  - erd
  - entity relationship
  - normalization
  - indexing strategy
  - database design
depends_on: []
output_schema:
  type: object
  properties:
    tables:
      type: array
      items:
        type: object
    relationships:
      type: array
      items:
        type: object
    indexes:
      type: array
      items:
        type: object
    normalization_form:
      type: string
  required:
    - tables
    - relationships
roles:
  - Architect
  - Dev
model_tier: sonnet
---

# Database Schema Design

Design relational database schema. Steps: (1) Identify entities and attributes. (2) Define relationships (1:1, 1:N, M:N). (3) Normalize to 3NF minimum. (4) Design indexes: primary keys, foreign keys, query-driven composite indexes. (5) Partitioning strategy for tables >10M rows. Output: table definitions with columns/types/constraints, ER diagram description, index recommendations.

## Step 1 — Entity Identification

- List all nouns in the domain: these are candidate entities
- Identify attributes for each entity (avoid storing derived values)
- Mark identifying attributes (natural keys vs surrogate keys)
- Separate multi-valued attributes into child tables

## Step 2 — Relationship Mapping

- **1:1** — embed as columns in the same table or separate table with shared PK
- **1:N** — foreign key on the "many" side pointing to the "one" side
- **M:N** — junction/bridge table with composite PK of both FKs plus any relationship attributes
- Document cardinality and optionality (mandatory vs optional)

## Step 3 — Normalization

- **1NF**: atomic values, no repeating groups, unique rows
- **2NF**: no partial dependencies (every non-key column depends on the full PK)
- **3NF**: no transitive dependencies (non-key columns depend only on the PK, not other non-key columns)
- **BCNF**: every determinant is a candidate key — apply when anomalies still exist after 3NF
- Denormalize deliberately for read-heavy tables after profiling

## Step 4 — Index Design

- **Primary key index**: auto-created, use surrogate UUID or BIGSERIAL
- **Foreign key indexes**: always index FK columns to avoid full-table scans on joins
- **Composite indexes**: order columns by selectivity (most selective first); match query WHERE clause order
- **Partial indexes**: index only rows matching a condition (e.g., `WHERE status = 'active'`)
- **Covering indexes**: include all columns needed by a query to avoid heap access
- Avoid indexing low-cardinality columns (e.g., boolean flags) standalone

## Step 5 — Partitioning (tables >10M rows)

- **Range partitioning**: by date/timestamp — ideal for time-series and log data
- **List partitioning**: by discrete values (region, status) — good for multi-tenant data
- **Hash partitioning**: distribute evenly when no natural partition key — good for hot-row avoidance
- Partition pruning: queries must include the partition key in WHERE clause
- Consider archiving old partitions rather than deleting rows

## Output

Return: table definitions (name, columns, types, constraints, default values), relationship list with type and FK definition, index recommendations with rationale, normalization form achieved, and partitioning strategy if applicable.
