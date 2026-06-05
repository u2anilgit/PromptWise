---
name: data-flow-analysis
description: Map full data lifecycle including PII touchpoints, transformations, and compliance exposure.
triggers:
  - data flow
  - data lifecycle
  - pii flow
  - data lineage
  - dfd
  - data flow diagram
  - data mapping
depends_on: []
output_schema:
  type: object
  properties:
    data_sources:
      type: array
      items:
        type: object
    transformations:
      type: array
      items:
        type: object
    pii_touchpoints:
      type: array
      items:
        type: object
    retention_policies:
      type: object
  required:
    - data_sources
    - pii_touchpoints
roles:
  - Architect
  - IT
model_tier: opus
---

# Data Flow Analysis

Map full data lifecycle. (1) Identify data sources (databases, APIs, files, user inputs). (2) Trace transformations and processing steps. (3) Flag all PII touchpoints: where PII is collected, stored, processed, transmitted. (4) Map retention policies per data type. (5) Identify compliance exposure: GDPR (EU data), HIPAA (health data), PCI-DSS (payment data). Output: DFD description + PII inventory + retention matrix.

## Step 1 — Data Source Inventory

- **Databases**: list all databases/schemas, their purpose, and data owner
- **External APIs**: third-party services that send or receive data (payment processors, analytics, CDNs)
- **File stores**: S3 buckets, file shares, blob storage — classify by sensitivity
- **User inputs**: web forms, mobile apps, API endpoints where users submit data
- **Logs and events**: application logs, audit logs, event streams
- For each source: name, type, data categories, sensitivity level (public/internal/confidential/restricted)

## Step 2 — Transformation Mapping

- Trace each data element from source to destination through every processing step
- Document: input format → transformation logic → output format
- Identify where data is: aggregated, anonymized, enriched, filtered, copied, or archived
- Note ETL/ELT pipelines, batch jobs, stream processors, and ML feature pipelines
- Flag any cross-border data transfers (data leaving a jurisdiction)

## Step 3 — PII Touchpoints

Classify PII by category:
- **Direct identifiers**: name, email, phone, SSN, passport number, IP address
- **Indirect identifiers**: date of birth, job title, location data that could identify individuals
- **Sensitive PII**: health data, financial data, biometrics, political/religious beliefs
- **Pseudonymized data**: tokenized or hashed identifiers (still PII if reversible)

For each touchpoint record:
- Where PII enters the system
- Where it is stored (encrypted at rest? column-level encryption?)
- Where it is transmitted (TLS? to which parties?)
- Where it is displayed (access controls? masking?)
- Where it is deleted or anonymized

## Step 4 — Retention Policies

Map retention per data category:
- **Active data**: in primary databases — retention period + deletion trigger
- **Archived data**: cold storage — retention period + access controls
- **Backup data**: frequency, retention window, geographic distribution
- **Log data**: operational logs (30-90 days), audit logs (1-7 years by regulation)
- Define right-to-erasure process: how to delete all data for a given user across all stores

## Step 5 — Compliance Exposure

### GDPR (EU personal data)
- Lawful basis for each processing activity (consent, contract, legitimate interest)
- Data Protection Impact Assessment (DPIA) required for high-risk processing
- Data subject rights: access, rectification, erasure, portability, objection
- 72-hour breach notification requirement

### HIPAA (US health data)
- PHI classification: any data that identifies a patient + health information
- Required safeguards: access controls, audit logs, encryption, BAAs with vendors
- Minimum necessary principle: only access PHI needed for the task

### PCI-DSS (payment card data)
- Cardholder data environment (CDE) scope: any system that stores/processes/transmits card data
- Never store CVV/CVC after authorization
- Tokenize PANs; use point-to-point encryption (P2PE)
- Quarterly vulnerability scans, annual penetration tests

## Output

Return data source inventory, transformation map (as DFD description), PII touchpoint list with location/protection/access-control per element, retention matrix by data type, and compliance exposure summary with required controls per regulation.
