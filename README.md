# AI Portfolio Advisor

Production-oriented SaaS scaffold for a multi-user AI portfolio management platform. Feature 1 establishes the monorepo, tenant-aware API contracts, database schema, Docker services, and a premium dashboard shell.

## What Is Included

- `apps/web`: Next.js 15, TypeScript, Tailwind CSS, React Query, Zustand, Framer Motion, and dashboard UI.
- `apps/api`: FastAPI service with dependency injection, repository pattern, typed schemas, audit logging, and read-only broker boundaries.
- `apps/agent`: LangGraph-ready agent package skeleton for future portfolio analysis workflows.
- `packages/shared`: Shared TypeScript portfolio contracts.
- `packages/database`: PostgreSQL schema with tenant isolation primitives.
- `docs`: Architecture and feature documentation.
- Manual portfolio CSV import for users who do not want to connect Zerodha yet.
- MCP-first Zerodha connection flow using Kite MCP read-only tool calls.
- Portfolio intelligence with live market-data enrichment, technical signals, recommendations, reports and alerts.
- Holdings-only Analytics engine with daily refresh, fundamentals, news signals, decision signals and sanity checks.

The AI is advisory only. No trade placement endpoint, command, or capability is implemented.

## Quick Start

```bash
cp .env.example .env
npm install
docker compose up --build
```

## Windows One-Click Handoff

To give this app to a non-technical Windows user, double-click:

```text
Create Friend Package.bat
```

Send the generated `dist\AI-Portfolio-Advisor-Windows.zip` file. Your friend should extract it and double-click `Start AI Portfolio Advisor.bat`. More details are in `docs/windows-one-click.md`.

Set `ZERODHA_KITE_API_KEY` and `ZERODHA_KITE_API_SECRET` in `.env` before starting the Zerodha connection flow.

Manual CSV import format is documented in `docs/manual-csv-import.md`.

Zerodha MCP setup is documented in `docs/zerodha-mcp-integration.md`.

Portfolio intelligence setup is documented in `docs/portfolio-intelligence.md`.

Analytics engine behavior is documented in `docs/analytics-engine.md`.

Open:

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs

## Verification

```bash
npm run typecheck
npm run lint:web
npm run api:test
```

Host Python is not required when using Docker.
