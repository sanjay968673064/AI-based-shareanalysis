import type { PortfolioSummary } from "@portfolio/shared";

export const fallbackPortfolio: PortfolioSummary = {
  portfolioValue: 163525.6,
  dayPnl: 672,
  dayPnlPct: 0.41,
  totalPnl: 14750.4,
  totalPnlPct: 9.92,
  healthScore: 82,
  cashBalance: 0,
  dividendSummary: 0,
  aiSummary:
    "Portfolio quality is healthy with positive long-term P&L. Financials and auto exposure are leading gains; monitor IT weakness and sector concentration.",
  holdings: [
    {
      symbol: "RELIANCE",
      companyName: "Reliance Industries Ltd",
      exchange: "NSE",
      sector: "Energy",
      assetClass: "equity",
      quantity: 12,
      averagePrice: 2445,
      lastPrice: 2862.4,
      marketValue: 34348.8,
      dayPnl: 188.3,
      totalPnl: 5008.8,
      allocationPct: 21
    },
    {
      symbol: "TATAMOTORS",
      companyName: "Tata Motors Ltd",
      exchange: "NSE",
      sector: "Consumer Cyclical",
      assetClass: "equity",
      quantity: 40,
      averagePrice: 685.8,
      lastPrice: 804.15,
      marketValue: 32166,
      dayPnl: 420,
      totalPnl: 4734,
      allocationPct: 19.7
    },
    {
      symbol: "HDFCBANK",
      companyName: "HDFC Bank Ltd",
      exchange: "NSE",
      sector: "Financial Services",
      assetClass: "equity",
      quantity: 18,
      averagePrice: 1562.1,
      lastPrice: 1698.3,
      marketValue: 30569.4,
      dayPnl: 312.2,
      totalPnl: 2451.6,
      allocationPct: 18.7
    },
    {
      symbol: "INFY",
      companyName: "Infosys Ltd",
      exchange: "NSE",
      sector: "Information Technology",
      assetClass: "equity",
      quantity: 24,
      averagePrice: 1410.25,
      lastPrice: 1516.75,
      marketValue: 36402,
      dayPnl: -248.5,
      totalPnl: 2556,
      allocationPct: 22.3
    }
  ],
  sectorAllocation: [
    { label: "Information Technology", value: 36402, percentage: 22.3 },
    { label: "Energy", value: 34348.8, percentage: 21 },
    { label: "Consumer Cyclical", value: 32166, percentage: 19.7 },
    { label: "Financial Services", value: 30569.4, percentage: 18.7 }
  ],
  assetAllocation: [{ label: "equity", value: 163525.6, percentage: 100 }],
  recentTransactions: [],
  upcomingEvents: [],
  updatedAt: "2026-07-01T00:00:00.000Z"
};
