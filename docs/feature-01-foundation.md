# Feature 1: SaaS Foundation And Portfolio Dashboard

## Scope

This feature creates the production foundation without implementing live trading or full autonomous advice.

Included:

- Monorepo structure.
- Docker Compose for web, API, PostgreSQL, and Redis.
- Tenant-aware database schema.
- FastAPI health, portfolio summary, and Zerodha connection status endpoints.
- Read-only broker client boundary for official Kite MCP integration.
- Next.js dashboard shell with responsive premium fintech UI.
- Shared TypeScript portfolio contracts.
- Initial tests and CI.

Deferred until approval:

- Live Kite MCP adapter implementation.
- Clerk/Auth.js production auth wiring.
- Celery scheduled jobs.
- AI agent orchestration and generated recommendations.
- Alerts, reports, and copilot memory.

## API Contracts

- `GET /health`
- `GET /api/v1/portfolio/summary`
- `GET /api/v1/zerodha/status`
- `POST /api/v1/zerodha/connect/read-only`

All tenant-scoped endpoints use the authenticated user context. In development, pass:

```http
X-User-Id: demo-user
```
