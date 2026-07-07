# Zerodha Kite MCP Integration

The app is MCP-first for Zerodha live data.

## User Flow

1. User clicks **Connect Zerodha**.
2. Backend calls the Kite MCP `login` tool.
3. Backend keeps that user's MCP session alive.
4. App opens the returned Zerodha authorization URL in a new tab.
5. User logs in and approves access on Zerodha.
6. User returns to the same app tab and clicks **Sync Holdings**.
7. Backend calls the Kite MCP `get_holdings` tool on the same MCP session.
8. Holdings are normalized and saved into PostgreSQL.
9. Dashboard refreshes.

The app must keep the MCP session alive between connect and sync. If the backend restarts between those steps, reconnect before syncing.

## Configuration

Hosted MCP mode:

```env
ZERODHA_INTEGRATION_MODE=mcp
ZERODHA_HOSTED_MCP_URL=https://mcp.kite.trade/mcp
ZERODHA_MCP_LOGIN_TOOL=login
ZERODHA_MCP_HOLDINGS_TOOL=get_holdings
ZERODHA_KITE_MCP_READ_ONLY=true
```

No Kite API key is required for the hosted MCP endpoint.

## Safety

The app uses an internal read-only allowlist. It allows portfolio and market data tools such as:

- `login`
- `get_holdings`
- `get_positions`
- `get_margins`
- `get_orders`
- `get_trades`
- `get_quotes`
- `get_ltp`

It blocks trading tools such as:

- `place_order`
- `modify_order`
- `cancel_order`
- GTT create/modify/delete tools

CSV upload remains available as a fallback when MCP authorization is unavailable.
