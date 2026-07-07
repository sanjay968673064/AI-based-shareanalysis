import csv
import io
import re
from decimal import Decimal, InvalidOperation


class PortfolioCsvParseError(ValueError):
    pass


HEADER_ALIASES = {
    "symbol": {"symbol", "tradingsymbol", "trading symbol", "instrument", "ticker", "scrip", "name"},
    "company_name": {"company", "company name", "name", "instrument name"},
    "exchange": {"exchange", "exch"},
    "sector": {"sector", "industry"},
    "asset_class": {"asset class", "asset_class", "asset", "type"},
    "quantity": {"quantity", "qty", "qty.", "net qty", "net quantity", "holdings qty", "buy quantity"},
    "average_price": {"average price", "avg price", "avg. cost", "avg cost", "average_price", "buy avg"},
    "last_price": {"last price", "ltp", "last traded price", "current price", "last_price"},
    "day_pnl": {"day pnl", "day p&l", "day_pnl"},
    "day_change_pct": {"day chg.", "day chg", "day change", "day change %", "day %"},
    "price_change": {"change", "price change"},
    "total_pnl": {"total pnl", "pnl", "p&l", "total p&l", "total_pnl", "profit loss"},
}


def parse_portfolio_csv(content: bytes) -> tuple[list[dict], int]:
    decoded = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise PortfolioCsvParseError("CSV file has no header row.")

    header_map = _build_header_map(reader.fieldnames)
    if "symbol" not in header_map or "quantity" not in header_map:
        raise PortfolioCsvParseError("CSV must include Symbol and Quantity columns.")

    rows: list[dict] = []
    skipped = 0
    for row in reader:
        parsed = _parse_row(row, header_map)
        if parsed is None:
            skipped += 1
            continue
        rows.append(parsed)

    if not rows:
        raise PortfolioCsvParseError("No valid holdings found in CSV.")
    return rows, skipped


def _build_header_map(fieldnames: list[str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for field in fieldnames:
        normalized.setdefault(_normalize_header(field), field)
    header_map: dict[str, str] = {}
    for canonical, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            field = normalized.get(_normalize_header(alias))
            if field:
                header_map[canonical] = field
                break
    return header_map


def _parse_row(row: dict[str, str], header_map: dict[str, str]) -> dict | None:
    symbol = _get(row, header_map, "symbol").upper()
    if not symbol:
        return None
    quantity = _money(_get(row, header_map, "quantity"))
    average_price = _money(_get(row, header_map, "average_price"), default=Decimal("0"))
    last_price = _money(_get(row, header_map, "last_price"), default=average_price)
    if quantity <= 0:
        return None

    total_pnl_raw = _get(row, header_map, "total_pnl")
    day_pnl_raw = _get(row, header_map, "day_pnl")
    day_change_pct_raw = _get(row, header_map, "day_change_pct")
    price_change_raw = _get(row, header_map, "price_change")
    total_pnl = (
        _money(total_pnl_raw, default=Decimal("0"))
        if total_pnl_raw
        else (last_price - average_price) * quantity
    )
    if day_pnl_raw:
        day_pnl = _money(day_pnl_raw, default=Decimal("0"))
    elif day_change_pct_raw:
        day_pnl = (last_price * quantity * _money(day_change_pct_raw, default=Decimal("0"))) / Decimal("100")
    elif price_change_raw:
        day_pnl = _money(price_change_raw, default=Decimal("0")) * quantity
    else:
        day_pnl = Decimal("0")

    return {
        "symbol": symbol,
        "exchange": _get(row, header_map, "exchange") or "NSE",
        "company_name": _get(row, header_map, "company_name") or symbol,
        "sector": _get(row, header_map, "sector") or None,
        "asset_class": _get(row, header_map, "asset_class") or "equity",
        "quantity": quantity,
        "average_price": average_price,
        "last_price": last_price,
        "day_pnl": day_pnl,
        "total_pnl": total_pnl,
    }


def _get(row: dict[str, str], header_map: dict[str, str], key: str) -> str:
    field = header_map.get(key)
    return str(row.get(field, "")).strip() if field else ""


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _money(value: str, default: Decimal | None = None) -> Decimal:
    if not value:
        if default is not None:
            return default
        raise PortfolioCsvParseError("Missing numeric value.")
    cleaned = value.strip().replace(",", "").replace("₹", "").replace("%", "")
    is_negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        if default is not None:
            return default
        raise PortfolioCsvParseError(f"Invalid numeric value: {value}") from exc
    return -amount if is_negative else amount
