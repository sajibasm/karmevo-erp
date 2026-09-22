# 0005 — Jobs: Celery + RabbitMQ with transactional outbox

**Status:** Proposed · **Requirements:** ARC-03, JOB-01..05, E2E-12

## Decision
- Business changes write `integration.outbox_events` in the same transaction. Each tenant database has its own outbox (ADR-0002).
- `outbox-relay` (role `erp_relay`) loops over the registry's ready tenants. For each tenant DB it claims pending rows with `FOR UPDATE SKIP LOCKED` in bounded batches, publishes with RabbitMQ publisher confirms, then marks the rows dispatched. A crash between publish and commit causes a re-publish, which is acceptable because consumers deduplicate.
- Consumers run under `tenant_session(message.tenant_id)` and insert into `integration.inbox_dedup (consumer, event_id)` with `ON CONFLICT DO NOTHING` in the same transaction as their effects. A duplicate becomes a no-op, and a failure rolls back both.
- Separate queues: `notifications`, `documents`, `imports`, `integrations`, `payroll`, `default`. Quorum queues, late acks, bounded retries with exponential backoff, dead-letter queue.
- `integration.job_runs` is the authoritative status table. Messages carry IDs only, never secrets or files.
- One Celery beat per schedule scope. Tenant business schedules are stored in PostgreSQL with time zone, DST, catch-up and overlap policy, and each execution key is unique.
- Kafka is not used (JOB-05).
- One relay pass covers every tenant DB. A tenant whose DB is unreachable is logged and skipped, never blocking the others. With many tenants, P1.1e shards tenants across relay workers.

## Consequences
Delivery is at-least-once, and business effects happen exactly once through dedup. This is tested by simulating a lost commit after publish.
