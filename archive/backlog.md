# PromptWise Supreme v3.0 Product Backlog & Roadmap

This backlog catalogs all **43 new skills, features, and integrations** required for the complete PromptWise Supreme v3.0 rollout, following the prerequisite Phase 3.0 foundation.

---

## 📅 Roadmap Overview

| Phase | Title | Scope | Est. Effort | Status |
|---|---|---|---|---|
| **Phase 1 (v3.1)** | [Dev Workflow Skills](#phase-1-dev-workflow-skills-v31) | 8 markdown skills for core development | 1–2 weeks | ✅ Completed |
| **Phase 2 (v3.2)** | [Docs & Architecture](#phase-2-docs--architecture-skills-v32) | 9 PM/BA/Architect skills + DOCX & Mermaid | 2 weeks | ✅ Completed |
| **Phase 3 (v3.3)** | [Security & Compliance](#phase-3-security--compliance-expansion-v33) | 7 security features, SBOM, licensing, OWASP | 2–3 weeks | ✅ Completed |
| **Phase 4 (v3.4-3.5)** | [AI Prompts & Testing](#phase-4-ai-prompts--testing-skills-v34-35) | 7 AI prompt skills + 5 test execution skills | 3–4 weeks | ✅ Completed |
| **Phase 5 (v3.7)** | [Org Roles & ROI Dashboard](#phase-5-org-roles--roi-dashboard-v37) | 8 industry roles (Banking, Health, Legal...) + charts | 5 weeks | ✅ Completed |
| **Phase 6 (v3.6-3.8)** | [Platform, DevOps & Enterprise](#phase-6-platform-devops--enterprise-platforms-v36-38) | VS Code, GHA hook, Slack, Prometheus, PG | 4–6 weeks | ✅ Completed |

---

## 🛠️ Backlog Details

### Phase 1: Dev Workflow Skills (v3.1)
*Prerequisite: Phase 3.0 Core (SkillLoader & DAG parser).*

- [x] **TSK-1.1: TDD Skill (`tdd.md`)**
  - **Description**: Guides test-first development by writing failing tests before coding.
  - **Target Role**: Dev
  - **Primary Model**: Claude 3.5 Sonnet
  - **Handoff Output**: `{test_suite_path: string, framework: "pytest" | "jest" | "gotest"}`
- [x] **TSK-1.2: Systematic Debugging (`systematic-debugging.md`)**
  - **Description**: Guides the user through a structured debugging loop (reproduce → isolate → hypothesize → verify).
  - **Target Role**: Dev
  - **Primary Model**: Claude 3 Opus (Extended Thinking)
  - **Handoff Output**: `{hypotheses: array, root_cause: string, verified: boolean}`
- [x] **TSK-1.3: Feature Development (`feature-dev.md`)**
  - **Description**: Orchestrates a complete feature build by chaining requirements definition to TDD and code review.
  - **Target Role**: Dev
  - **Primary Model**: Claude 3.5 Sonnet
  - **Handoff Output**: `{feature_name: string, files_created: array, test_results: string}`
- [x] **TSK-1.4: Code Review (`code-review.md`)**
  - **Description**: Performs a comprehensive style, security, correctness, and complexity audit.
  - **Target Role**: Dev, EM
  - **Primary Model**: Claude 3.5 Sonnet
  - **Handoff Output**: `{score: number, issues: array, approved: boolean}`
- [x] **TSK-1.5: Verification Checklist (`verification-before-completion.md`)**
  - **Description**: A fast checklist check (tests passing, zero TODOs, clean compile) prior to completing a task.
  - **Target Role**: Dev
  - **Primary Model**: Claude 3.5 Haiku
  - **Handoff Output**: `{checklist_passed: boolean, failures: array}`
- [x] **TSK-1.6: Refactoring Assistant (`refactoring.md`)**
  - **Description**: Proposes structured, incremental code cleanups backed by safety tests.
  - **Target Role**: Dev
  - **Primary Model**: Claude 3.5 Sonnet
  - **Handoff Output**: `{refactoring_diff: string, tests_retained: boolean}`
- [x] **TSK-1.7: Git Workflow Helper (`git-workflow.md`)**
  - **Description**: Automates branch creation, conventional commit formatting, and merge conflict resolution.
  - **Target Role**: Dev
  - **Primary Model**: Claude 3.5 Haiku
  - **Handoff Output**: `{branch_name: string, commit_message: string}`
- [x] **TSK-1.8: Branch Finisher (`finishing-branch.md`)**
  - **Description**: Generates pull request descriptions and triggers final build tests.
  - **Target Role**: Dev
  - **Primary Model**: Claude 3.5 Sonnet
  - **Handoff Output**: `{pr_title: string, pr_body: string}`

---

### Phase 2: Docs & Architecture Skills (v3.2)
*Requires python-docx & python-pptx (optional).*

- [x] **TSK-2.1: Business Requirement Document (`brd-generator.md`)**
  - **Description**: Conducts an elicitation interview and exports a formal BRD Word document.
  - **Target Role**: PM, BA
  - **Primary Model**: Claude 3 Opus
- [x] **TSK-2.2: Product Requirement Document (`prd-generator.md`)**
  - **Description**: Maps user goals, KPIs, and features into a structured PRD document.
  - **Target Role**: PM
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-2.3: User Story Generator (`user-story-generator.md`)**
  - **Description**: Bulk exports user stories with detailed Gherkin acceptance criteria (Given/When/Then).
  - **Target Role**: PM, SM
  - **Primary Model**: Claude 3.5 Haiku
- [x] **TSK-2.4: System Design Blueprinter (`system-design.md`)**
  - **Description**: Generates C4-model context and container architecture plans, exporting Mermaid markup.
  - **Target Role**: Architect
  - **Primary Model**: Claude 3 Opus
- [x] **TSK-2.5: ADR Editor (`adr.md`)**
  - **Description**: Generates Architecture Decision Records in MADR format.
  - **Target Role**: Architect
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-2.6: Architecture Auditor (`architecture-review.md`)**
  - **Description**: Scores coupling, cohesion, and scalability trade-offs of existing code.
  - **Target Role**: Architect, EM
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-2.7: Threat Modeler (`security-architecture.md`)**
  - **Description**: Evaluates data boundaries and flows using the STRIDE threat modeling pattern.
  - **Target Role**: Architect, Security
  - **Primary Model**: Claude 3 Opus
- [x] **TSK-2.8: API Docs Synthesizer (`api-docs.md`)**
  - **Description**: Inspects codebase routes and outputs OpenAPI 3.1 YAML specs.
  - **Target Role**: Dev
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-2.9: Changelog Generator (`changelog-generator.md`)**
  - **Description**: Scans git commit logs to build user-facing release notes.
  - **Target Role**: Dev, SM
  - **Primary Model**: Claude 3.5 Haiku

---

### Phase 3: Security & Compliance Expansion (v3.3)
*Replaces supply chain security stub with active OSV queries, SBOM parsing, and profiles.*

- [x] **TSK-3.1: PII Preflight Audit Hook**
  - **Description**: Scans prompts and LLM responses to redact, warn, or block PII.
  - **Target Role**: All Roles
  - **Primary Model**: Claude 3.5 Haiku
- [x] **TSK-3.2: Injection Preflight Audit Hook**
  - **Description**: Evaluates prompt injection risk scoring before calling the model router.
  - **Target Role**: All Roles
  - **Primary Model**: Claude 3.5 Haiku
- [x] **TSK-3.3: OWASP Top-10 Post-Generation Auditor**
  - **Description**: Scans generated code files for SQLi, XSS, SSRF, and flags security issues.
  - **Target Role**: Dev, Security
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-3.4: SBOM Generator**
  - **Description**: Audits project dependencies and generates a CycloneDX SBOM.
  - **Target Role**: IT
  - **Primary Model**: Claude 3.5 Haiku
- [x] **TSK-3.5: License Compliance Matrix**
  - **Description**: Validates dependencies against a license whitelist (detects GPL contamination).
  - **Target Role**: IT, Legal
  - **Primary Model**: Claude 3.5 Haiku
- [x] **TSK-3.6: Secrets Rotation Advisor**
  - **Description**: Flags hardcoded tokens and generates environment variable migration guides.
  - **Target Role**: Dev, IT
  - **Primary Model**: Claude 3.5 Haiku
- [x] **TSK-3.7: Compliance Engine Profiles**
  - **Description**: Implements configuration schema for SOC2, HIPAA, and FINRA profiles.
  - **Target Role**: IT, Security
  - **Primary Model**: Rule Engine (Python)

---

### Phase 4: AI Prompts & Testing Skills (v3.4-3.5)
*AI engineering workspace and comprehensive code testing tools.*

- [x] **TSK-4.1: Prompt Registry Database Store**
  - **Description**: Manages, searches, and versions system prompts using memory database tables.
  - **Target Role**: Dev, PM
  - **Primary Model**: SQLite + Claude 3.5 Haiku
- [x] **TSK-4.2: Multi-Model Evaluator**
  - **Description**: Executes prompts across Opus, Sonnet, and Haiku in parallel and compares output.
  - **Target Role**: Dev, PM
  - **Primary Model**: Claude 3 Opus (as judge)
- [x] **TSK-4.3: RAG Optimizer**
  - **Description**: Analyzes retrieval chunks, overlap settings, and recommends indexing adjustments.
  - **Target Role**: Data, Dev
  - **Primary Model**: Claude 3 Opus
- [x] **TSK-4.4: Few-Shot Example Builder**
  - **Description**: Synthesizes and structures prompt example blocks to maximize in-context learning.
  - **Target Role**: Dev, PM
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-4.5: Agent Chain Designer**
  - **Description**: Recommends multi-agent layouts and outputs skill dependencies.
  - **Target Role**: Dev, PM
  - **Primary Model**: Claude 3 Opus
- [x] **TSK-4.6: System Prompt Auditor**
  - **Description**: Adversarially red-teams system instructions to find logical loop holes.
  - **Target Role**: Dev, PM
  - **Primary Model**: Claude 3 Opus (Extended Thinking)
- [x] **TSK-4.7: Model Migration Advisor**
  - **Description**: Rewrites prompts to work optimally with newer model architectures.
  - **Target Role**: Dev
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-4.8: Test Generator**
  - **Description**: Analyzes code files and auto-generates unit/integration test suites.
  - **Target Role**: Dev, QA
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-4.9: Test Coverage Advisor**
  - **Description**: Inspects coverage logs and highlights untested critical code paths.
  - **Target Role**: Dev, QA
  - **Primary Model**: Claude 3.5 Haiku
- [x] **TSK-4.10: API Testing Generator**
  - **Description**: Generates end-to-end API test scripts based on OpenAPI specs.
  - **Target Role**: Dev, QA
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-4.11: E2E Playwright Scenario Designer**
  - **Description**: Builds UI page-object test blueprints utilizing `playwright_bridge.py`.
  - **Target Role**: Dev, QA
  - **Primary Model**: Claude 3 Opus
- [x] **TSK-4.12: Test Data Generator**
  - **Description**: Generates schema-valid SQL and JSON test mock data using Faker.
  - **Target Role**: Dev, QA
  - **Primary Model**: Claude 3.5 Sonnet

---

### Phase 5: Org Roles & ROI Dashboard (v3.7)
*Supreme tier industry-specific roles and management dashboard views.*

- [x] **TSK-5.1: Banking Role Skill Pack**
  - **Description**: Implements FINRA Rule 3110 and AML reconciliation helper templates.
  - **Target Role**: Banking
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-5.2: Healthcare Role Skill Pack**
  - **Description**: Implements HIPAA Safe Harbor filters and FHIR JSON schema validators.
  - **Target Role**: Healthcare
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-5.3: Legal Role Skill Pack**
  - **Description**: Implements GDPR compliance audits and contract phrase classifiers.
  - **Target Role**: Legal
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-5.4: HR Role Skill Pack**
  - **Description**: Job description analyzer and performance review formatting tools.
  - **Target Role**: HR
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-5.5: Data & ML Role Skill Pack**
  - **Description**: SQL optimizers and model card generators.
  - **Target Role**: Data
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-5.6: C-Suite Executive Skill Pack**
  - **Description**: Generates executive ROI reports and board presentation deck outlines.
  - **Target Role**: C-Suite
  - **Primary Model**: Claude 3 Opus
- [x] **TSK-5.7: Security Role Skill Pack**
  - **Description**: Automated SOC2 compliance checklist generators and network audit tools.
  - **Target Role**: Security
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-5.8: QA Role Skill Pack**
  - **Description**: Defect triage assistants and test strategy template generators.
  - **Target Role**: QA
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-5.9: Enterprise ROI Dashboard**
  - **Description**: Web charts visualizing time/hours saved, active seats, and token metrics.
  - **Target Role**: Admin, C-Suite
  - **Primary Model**: Flask / Chart.js

---

### Phase 6: Platform, DevOps & Enterprise Platforms (v3.6-3.8)
*Platform integrations, remote transports, and production databases.*

- [x] **TSK-6.1: DevOps Skill Pack**
  - **Description**: IaC Terraform builders, incident runbook assistants, and CI generators.
  - **Target Role**: DevOps
  - **Primary Model**: Claude 3.5 Sonnet
- [x] **TSK-6.2: VS Code Extension wrapper**
  - **Description**: Packages the MCP stdio/Flask server as a native VS Code extension.
  - **Target Role**: All Roles
  - **Primary Model**: TypeScript
- [x] **TSK-6.3: GitHub Actions pre-commit hook**
  - **Description**: Composite GHA runner that triggers code review and security audits on PR.
  - **Target Role**: All Roles
  - **Primary Model**: YAML
- [x] **TSK-6.4: Slack / MS Teams Webhook Integrator**
  - **Description**: Renders overspend alerts and daily metrics directly to chat channels.
  - **Target Role**: EM, Admin
  - **Primary Model**: Python Webhook
- [x] **TSK-6.5: Prometheus /metrics Exporter**
  - **Description**: Adds system metrics exporter to the dashboard backend.
  - **Target Role**: IT
  - **Primary Model**: Python (prometheus_client)
- [x] **TSK-6.6: PostgreSQL DB Engine support**
  - **Description**: Integrates PostgreSQL connection support into `memory_manager.py`.
  - **Target Role**: Admin
  - **Primary Model**: SQLAlchemy ORM
- [x] **TSK-6.7: SSO & SAML RBAC integration**
  - **Description**: Implements user login and scope gates for remote SSE transport endpoints.
  - **Target Role**: IT, Admin
  - **Primary Model**: Authlib
