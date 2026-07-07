from decimal import Decimal

from src.services.csv_portfolio_parser import parse_portfolio_csv


def test_parse_manual_portfolio_csv() -> None:
    content = (
        "Symbol,Company Name,Quantity,Average Price,Last Price,Sector\n"
        "INFY,Infosys Ltd,10,1400.50,1510.25,Information Technology\n"
    ).encode()

    holdings, skipped = parse_portfolio_csv(content)

    assert skipped == 0
    assert holdings[0]["symbol"] == "INFY"
    assert holdings[0]["quantity"] == 10
    assert holdings[0]["total_pnl"] == Decimal("1097.50")


def test_parse_zerodha_style_portfolio_csv() -> None:
    content = (
        "Instrument,Qty.,Avg. cost,LTP,P&L,Day chg.\n"
        "HDFCBANK,5,\"1,500.00\",\"1,650.00\",750.00,25.00\n"
        ",0,0,0,0,0\n"
    ).encode()

    holdings, skipped = parse_portfolio_csv(content)

    assert skipped == 1
    assert holdings[0]["symbol"] == "HDFCBANK"
    assert holdings[0]["company_name"] == "HDFCBANK"
    assert holdings[0]["total_pnl"] == Decimal("750.00")
    assert holdings[0]["day_pnl"] == Decimal("2062.500")


def test_parse_actual_zerodha_holdings_csv() -> None:
    content = (
        '"Instrument","Qty.","Avg. cost","LTP","Invested","Cur. val","P&L","Net chg.","Day chg.",""\n'
        '"ADANIENT",1,2204.65,3212.2,2204.65,3212.2,1007.55,45.7,1.07,""\n'
        '"ADANIPOWER",30,104.25,221.75,3127.45,6652.5,3525.05,112.71,-1.27,""\n'
    ).encode()

    holdings, skipped = parse_portfolio_csv(content)

    assert skipped == 0
    assert holdings[0]["symbol"] == "ADANIENT"
    assert holdings[0]["quantity"] == Decimal("1")
    assert holdings[0]["average_price"] == Decimal("2204.65")
    assert holdings[0]["last_price"] == Decimal("3212.2")
    assert holdings[0]["total_pnl"] == Decimal("1007.55")
    assert holdings[0]["day_pnl"] == Decimal("34.37054")


def test_parse_screener_style_zerodha_csv() -> None:
    content = (
        '"Name","Average Price","Buy Quantity","Change","Change %","Last Price","Sector","Sell Quantity"\n'
        '"RELIANCE INDUSTRIES",1305.14,4064,0.5,0.04,1304,"Refineries",0\n'
        '"BHARTI AIRTEL",1903.53,0,35.4,1.89,1910.4,"Telecom",520\n'
    ).encode()

    holdings, skipped = parse_portfolio_csv(content)

    assert skipped == 1
    assert holdings[0]["symbol"] == "RELIANCE INDUSTRIES"
    assert holdings[0]["company_name"] == "RELIANCE INDUSTRIES"
    assert holdings[0]["quantity"] == Decimal("4064")
    assert holdings[0]["day_pnl"] == Decimal("2032.0")
