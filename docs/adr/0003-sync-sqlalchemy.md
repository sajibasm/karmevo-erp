# 0003 — Synchronous SQLAlchemy shared by API and workers

**Status:** Proposed · **Requirements:** ARC-05, JOB-01

## Context
Celery tasks are synchronous. Keeping the domain services async for FastAPI and sync for Celery would duplicate code or need event-loop bridging. The ERP workload is dominated by database transactions and row locks, not by high-fanout I/O.

## Decision
Use SQLAlchemy 2.x ORM in sync mode with psycopg 3. FastAPI endpoints are plain `def`, which Starlette runs in its threadpool. The same domain services run unchanged in Celery tasks. Transactions are opened by `Database.tenant_session()` or `Database.platform_session()`, never implicitly.

## Consequences
- One implementation of every business rule, testable without an event loop.
- Throughput is bounded by the threadpool and DB pool sizes. These are tuned per deployment profile and load-tested in P1.9 (OPS-07).
- Websocket and streaming endpoints (kitchen display, live chat) may use async handlers that call domain services through `run_in_threadpool`.
