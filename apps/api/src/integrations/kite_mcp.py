from contextlib import AsyncExitStack
from dataclasses import dataclass
import json
import re
from typing import Protocol
from urllib.parse import urlencode

from anyio import BrokenResourceError, ClosedResourceError, EndOfStream
import httpx
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

from src.core.config import settings


class BrokerConfigurationError(RuntimeError):
    pass


class BrokerPortfolioClient(Protocol):
    async def create_read_only_authorization_url(self, user_reference: str, account_label: str) -> str:
        """Return a user-specific Zerodha authorization URL with read-only scopes."""

    async def create_mcp_authorization_url(self, user_reference: str) -> str:
        """Return a Kite MCP authorization URL."""

    async def fetch_mcp_holdings(self, user_reference: str) -> list[dict]:
        """Fetch normalized holdings through Kite MCP."""


@dataclass(frozen=True)
class KiteMcpClient:
    base_url: str = settings.zerodha_kite_mcp_url
    read_only: bool = settings.zerodha_kite_mcp_read_only

    async def create_read_only_authorization_url(self, user_reference: str, account_label: str) -> str:
        if not self.read_only:
            raise RuntimeError("Kite MCP integration must be configured in read-only mode.")

        redirect_params = urlencode(
            {
                "user_ref": user_reference,
                "account_label": account_label,
                "mode": "read_only",
            }
        )

        async with httpx.AsyncClient(timeout=5) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/oauth/read-only-url",
                    json={
                        "state": user_reference,
                        "account_label": account_label,
                        "redirect_params": redirect_params,
                        "scopes": ["portfolio", "orders", "positions", "quotes"],
                    },
                )
                response.raise_for_status()
                return str(response.json()["authorization_url"])
            except httpx.HTTPError:
                if not settings.zerodha_kite_api_key:
                    raise BrokerConfigurationError(
                        "ZERODHA_KITE_API_KEY is required before Zerodha login can start."
                    )
                query = urlencode(
                    {
                        "v": "3",
                        "api_key": settings.zerodha_kite_api_key,
                        "redirect_params": redirect_params,
                    }
                )
                return f"https://kite.zerodha.com/connect/login?{query}"

    async def create_mcp_authorization_url(self, user_reference: str) -> str:
        result = await self._call_mcp_tool(user_reference, settings.zerodha_mcp_login_tool, {})
        url = _extract_url(result)
        if not url:
            raise BrokerConfigurationError("Kite MCP login did not return an authorization URL.")
        return url

    async def fetch_mcp_holdings(self, user_reference: str) -> list[dict]:
        result = await self._call_mcp_tool(user_reference, settings.zerodha_mcp_holdings_tool, {})
        payload = _extract_payload(result)
        rows = _extract_holdings_rows(payload)
        return [_normalize_mcp_holding(row) for row in rows if _normalize_mcp_holding(row) is not None]

    async def _call_mcp_tool(self, session_key: str, tool_name: str, arguments: dict) -> types.CallToolResult:
        if tool_name not in READ_ONLY_MCP_TOOLS:
            raise BrokerConfigurationError(f"MCP tool '{tool_name}' is not allowed by this read-only app.")
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                session = await _get_or_create_mcp_session(session_key, force_new=attempt > 0)
                tools = await session.session.list_tools()
                available = {tool.name for tool in tools.tools}
                if tool_name not in available:
                    raise BrokerConfigurationError(
                        f"Kite MCP tool '{tool_name}' is not available. Available tools: {', '.join(sorted(available))}"
                    )
                return await session.session.call_tool(tool_name, arguments)
            except (BrokenResourceError, ClosedResourceError, EndOfStream) as exc:
                last_error = exc
                await _drop_mcp_session(session_key)
        raise BrokerConfigurationError(
            "Kite MCP session closed before Zerodha authorization could start. Please try Connect Zerodha again."
        ) from last_error


@dataclass
class _PersistentMcpSession:
    stack: AsyncExitStack
    session: ClientSession


_MCP_SESSIONS: dict[str, _PersistentMcpSession] = {}


async def _get_or_create_mcp_session(session_key: str, force_new: bool = False) -> _PersistentMcpSession:
    if force_new:
        await _drop_mcp_session(session_key)
    existing = _MCP_SESSIONS.get(session_key)
    if existing is not None:
        return existing

    stack = AsyncExitStack()
    try:
        read_stream, write_stream, _ = await stack.enter_async_context(
            streamable_http_client(settings.zerodha_hosted_mcp_url)
        )
        session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        handle = _PersistentMcpSession(stack=stack, session=session)
        _MCP_SESSIONS[session_key] = handle
        return handle
    except Exception:
        await stack.aclose()
        raise


async def _drop_mcp_session(session_key: str) -> None:
    existing = _MCP_SESSIONS.pop(session_key, None)
    if existing is None:
        return
    try:
        await existing.stack.aclose()
    except Exception:
        pass


READ_ONLY_MCP_TOOLS = {
    "login",
    "get_profile",
    "get_margins",
    "get_holdings",
    "get_positions",
    "get_mf_holdings",
    "get_quotes",
    "get_ltp",
    "get_ohlc",
    "get_historical_data",
    "search_instruments",
    "get_orders",
    "get_trades",
    "get_order_history",
    "get_order_trades",
}


def _extract_url(result: types.CallToolResult) -> str | None:
    payload = _extract_payload(result)
    if isinstance(payload, dict):
        for key in ("authorization_url", "auth_url", "login_url", "url"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
    text = _extract_text(result)
    match = re.search(r"https?://\S+", text)
    return match.group(0).rstrip(").,") if match else None


def _extract_payload(result: types.CallToolResult):
    structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if structured:
        return structured
    text = _extract_text(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


def _extract_text(result: types.CallToolResult) -> str:
    parts: list[str] = []
    for item in result.content:
        if isinstance(item, types.TextContent):
            parts.append(item.text)
    return "\n".join(parts)


def _extract_holdings_rows(payload) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("holdings", "data", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
            if isinstance(value, dict):
                nested = _extract_holdings_rows(value)
                if nested:
                    return nested
    return []


def _normalize_mcp_holding(row: dict) -> dict | None:
    symbol = _first_string(row, "tradingsymbol", "trading_symbol", "symbol", "instrument")
    quantity = _first_number(row, "quantity", "qty", "t1_quantity")
    if not symbol or quantity <= 0:
        return None
    average_price = _first_number(row, "average_price", "avg_price", "avg_cost", "average_cost")
    last_price = _first_number(row, "last_price", "ltp", "close_price")
    if last_price <= 0:
        last_price = average_price
    total_pnl = _first_number(row, "pnl", "profit_loss", "total_pnl")
    if total_pnl == 0 and average_price > 0 and last_price > 0:
        total_pnl = (last_price - average_price) * quantity
    day_change_pct = _first_number(row, "day_change_percentage", "day_change", "day_chg")
    day_pnl = _first_number(row, "day_pnl", "day_profit_loss")
    if day_pnl == 0 and day_change_pct != 0:
        day_pnl = (last_price * quantity * day_change_pct) / 100
    return {
        "symbol": symbol,
        "exchange": _first_string(row, "exchange") or "NSE",
        "company_name": _first_string(row, "company_name", "name") or symbol,
        "sector": _first_string(row, "sector") or None,
        "asset_class": "equity",
        "quantity": quantity,
        "average_price": average_price,
        "last_price": last_price,
        "day_pnl": day_pnl,
        "total_pnl": total_pnl,
    }


def _first_string(row: dict, *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _first_number(row: dict, *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            return float(str(value).replace(",", "").replace("₹", ""))
        except ValueError:
            continue
    return 0.0
