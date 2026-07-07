# Manual Portfolio CSV Import

Use **Upload CSV** in the dashboard to import holdings without connecting Zerodha.

The importer requires:

- `Symbol`
- `Quantity`

Recommended columns:

```csv
Symbol,Company Name,Exchange,Sector,Quantity,Average Price,Last Price,Day P&L,Total P&L
INFY,Infosys Ltd,NSE,Information Technology,10,1400.50,1510.25,-25.00,1097.50
HDFCBANK,HDFC Bank Ltd,NSE,Financial Services,5,1500.00,1650.00,25.00,750.00
```

Accepted aliases include Zerodha-style columns such as `Instrument`, `Qty.`, `Avg. cost`, `LTP`, `P&L`, and `Day chg.`.

Actual Zerodha holdings exports are supported:

```csv
Instrument,Qty.,Avg. cost,LTP,Invested,Cur. val,P&L,Net chg.,Day chg.
ADANIENT,1,2204.65,3212.2,2204.65,3212.2,1007.55,45.7,1.07
```

For this format, `Day chg.` is treated as a percentage and converted into day P&L using current value.

The importer also accepts Screener/Zerodha watchlist-style exports like:

```csv
Name,Average Price,Buy Quantity,Change,Last Price,Sector
RELIANCE INDUSTRIES,1305.14,4064,0.5,1304,Refineries
```

For this format:

- `Name` is used as both symbol and company name.
- `Buy Quantity` is used as quantity.
- `Change` is treated as per-share day change and multiplied by quantity for day P&L.
- Rows with `Buy Quantity` of zero are skipped.

Import behavior:

- The uploaded CSV replaces the current manual holdings for the user.
- Rows without a symbol or with zero quantity are skipped.
- If `Last Price` is missing, the importer uses `Average Price`.
- If `Total P&L` is missing, the importer calculates it from quantity, average price, and last price.
