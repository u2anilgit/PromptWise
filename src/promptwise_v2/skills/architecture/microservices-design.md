---
name: microservices-design
description: Design microservices architecture with DDD boundaries, event contracts, sagas, and service mesh.
triggers:
  - microservices
  - service design
  - service boundaries
  - saga pattern
  - event driven
  - service mesh
  - domain driven design
depends_on: []
output_schema:
  type: object
  properties:
    services:
      type: array
      items:
        type: object
    event_contracts:
      type: array
      items:
        type: object
    communication_pattern:
      type: string
      enum: [sync-REST, async-events, mixed]
    saga_patterns:
      type: array
      items:
        type: object
  required:
    - services
    - communication_pattern
roles:
  - Architect
model_tier: opus
---

# Microservices Design

Design microservices architecture. (1) Define service boundaries via Domain-Driven Design bounded contexts. (2) Define event contracts for async communication (event name, payload schema, producer, consumers). (3) Choose communication: sync (REST/gRPC) for queries, async (events) for state changes. (4) Saga patterns for distributed transactions (choreography vs orchestration). (5) Service mesh config if needed (sidecar proxy, mTLS). Output: service list + event contracts + deployment topology.

## Step 1 — Service Boundaries (DDD Bounded Contexts)

- Identify bounded contexts from the domain model — each context owns its data
- Apply the **Single Responsibility Principle** at service level: one business capability per service
- Use **context mapping** patterns: Partnership, Shared Kernel, Customer-Supplier, Conformist, Anti-Corruption Layer
- Avoid chatty services — if two services always communicate together, consider merging
- Each service has its own database — no shared schemas

## Step 2 — Event Contracts

- Define events for every significant state change: `OrderPlaced`, `PaymentProcessed`, `InventoryReserved`
- Event schema: `{ event_name, version, aggregate_id, timestamp, payload, metadata }`
- Use semantic versioning for events — additive changes are non-breaking
- Producer owns the schema; consumers must tolerate unknown fields
- Store events in an event log (Kafka, Kinesis, EventBridge) for replay capability

## Step 3 — Communication Patterns

- **Sync (REST/gRPC)**: use for queries that need immediate responses; add circuit breakers and timeouts
- **Async (events/messages)**: use for state changes, workflows, and fan-out notifications
- **Mixed**: queries sync, commands async — most production systems use this pattern
- API Gateway for external clients; service mesh or direct calls for internal communication
- gRPC preferred over REST for internal sync calls: typed contracts, binary encoding, streaming

## Step 4 — Saga Patterns (Distributed Transactions)

### Choreography Saga
- Services react to events and emit compensating events on failure
- No central coordinator — fully decoupled
- Risk: hard to track overall transaction state; use for simple flows (3 steps)

### Orchestration Saga
- Central saga orchestrator sends commands to services and awaits replies
- Explicit compensation logic in one place
- Use for complex flows (4+ steps), or when visibility into saga state is required
- Implement as a state machine with: `PENDING → PROCESSING → COMPLETED | COMPENSATING → FAILED`

## Step 5 — Service Mesh

- Use when: >5 services, mTLS required, need distributed tracing, or advanced traffic management
- **Sidecar proxy** (Envoy/Istio): intercepts all traffic, handles retries/timeouts/circuit-breaking
- **mTLS**: automatic certificate rotation, zero-trust between services
- **Observability**: distributed tracing (Jaeger/Zipkin), metrics (Prometheus), logs (structured JSON)
- **Traffic management**: canary releases, A/B testing, fault injection for testing

## Output

Return service list (name, responsibility, owns-data, APIs), event contracts (name, producer, consumers, payload schema), chosen communication pattern with rationale, saga designs for distributed transactions, and deployment topology (containers, service mesh config if applicable).
