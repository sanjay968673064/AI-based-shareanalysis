# Architecture

## Modular Layout

```text
apps/
  web/      Next.js SaaS frontend
  api/      FastAPI public/backend API
  agent/    LangGraph AI advisory workflows
packages/
  shared/   TypeScript contracts shared with frontend
  database/ PostgreSQL migrations and schema notes
docs/       Product and engineering documentation
```

## Tenancy Model

Every user-facing record carries a `tenant_id` and `user_id` where applicable. API dependencies resolve the authenticated user context before service methods execute. Repositories require that context and never expose unscoped reads.

Feature 1 uses a development `X-User-Id` header so the API is runnable before Clerk/Auth.js is configured. Production auth should replace this dependency with verified Clerk or Auth.js JWT claims while preserving the same `UserContext` interface.

## Broker Integration

Zerodha access is isolated behind `BrokerPortfolioClient`. The first concrete target is the official Kite MCP Server in read-only mode. The application stores encrypted access tokens only, never user passwords, and the broker adapter exposes portfolio, holdings, positions, orders, PnL, trade history, and quote reads.

There are intentionally no trade placement methods in the broker interface.

## AI Boundary

Agents may read normalized portfolio snapshots and write advisory reports. They cannot execute broker actions. Recommendations must include reason, confidence, risk, upside, downside, target price, stop loss, and horizon.

## Runtime Services

- PostgreSQL: tenant data, reports, alerts, audit logs.
- Redis: caching, rate-limit counters, Celery broker.
- Celery: scheduled portfolio refreshes and report generation.
- FastAPI: secure API and service orchestration.
- Next.js: SaaS dashboard and AI copilot UI.
