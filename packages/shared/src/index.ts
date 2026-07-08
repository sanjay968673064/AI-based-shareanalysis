import { z } from "zod";

export const holdingSchema = z.object({
  symbol: z.string(),
  companyName: z.string(),
  exchange: z.string(),
  sector: z.string().nullable(),
  assetClass: z.string(),
  quantity: z.number(),
  averagePrice: z.number(),
  lastPrice: z.number(),
  marketValue: z.number(),
  dayPnl: z.number(),
  totalPnl: z.number(),
  allocationPct: z.number()
});

export const allocationSchema = z.object({
  label: z.string(),
  value: z.number(),
  percentage: z.number()
});

export const portfolioSummarySchema = z.object({
  portfolioValue: z.number(),
  dayPnl: z.number(),
  dayPnlPct: z.number(),
  totalPnl: z.number(),
  totalPnlPct: z.number(),
  healthScore: z.number().min(0).max(100),
  cashBalance: z.number(),
  dividendSummary: z.number(),
  aiSummary: z.string(),
  holdings: z.array(holdingSchema),
  sectorAllocation: z.array(allocationSchema),
  assetAllocation: z.array(allocationSchema),
  recentTransactions: z.array(z.string()),
  upcomingEvents: z.array(z.string()),
  updatedAt: z.string()
});

export const portfolioAlertSchema = z.object({
  severity: z.enum(["low", "medium", "high"]),
  alertType: z.string(),
  symbol: z.string().nullable(),
  message: z.string(),
  action: z.string()
});

export const stockRecommendationSchema = z.object({
  symbol: z.string(),
  companyName: z.string(),
  recommendation: z.string(),
  confidenceScore: z.number(),
  riskScore: z.number(),
  expectedUpside: z.number(),
  expectedDownside: z.number(),
  targetAllocation: z.number(),
  reasoning: z.string(),
  bullishFactors: z.array(z.string()),
  bearishFactors: z.array(z.string()),
  keyRisks: z.array(z.string()),
  whatChanged: z.string(),
  technical: z
    .object({
      rsi14: z.number().nullable().optional(),
      macd: z.number().nullable().optional(),
      ema20: z.number().nullable().optional(),
      ema50: z.number().nullable().optional(),
      trendDirection: z.string(),
      momentumScore: z.number(),
      notes: z.array(z.string())
    })
    .passthrough()
});

export const portfolioIntelligenceSchema = z.object({
  generatedAt: z.string(),
  recommendations: z.array(stockRecommendationSchema),
  alerts: z.array(portfolioAlertSchema),
  dataQuality: z.object({
    score: z.number(),
    warnings: z.array(z.string())
  })
});

export const analyticsMetricSchema = z.object({
  label: z.string(),
  value: z.string(),
  detail: z.string().nullable().optional(),
  tone: z.enum(["good", "watch", "bad", "neutral"])
});

export const companyNewsSchema = z.object({
  title: z.string(),
  publisher: z.string().nullable().optional(),
  link: z.string().nullable().optional(),
  publishedAt: z.string().nullable().optional()
});

export const companyAnalyticsSchema = z.object({
  symbol: z.string(),
  companyName: z.string(),
  sector: z.string().nullable().optional(),
  industry: z.string().nullable().optional(),
  currency: z.string().nullable().optional(),
  lastPrice: z.number().nullable().optional(),
  dayChangePct: z.number().nullable().optional(),
  fiftyTwoWeekLow: z.number().nullable().optional(),
  fiftyTwoWeekHigh: z.number().nullable().optional(),
  businessSummary: z.string(),
  overallScore: z.number(),
  balanceSheetScore: z.number(),
  growthScore: z.number(),
  cashFlowScore: z.number(),
  valuationScore: z.number(),
  recommendation: z.string(),
  planning: z.string(),
  strengths: z.array(z.string()),
  concerns: z.array(z.string()),
  financials: z.array(analyticsMetricSchema),
  news: z.array(companyNewsSchema),
  sourceNotes: z.array(z.string())
});

export const decisionSignalSchema = z.object({
  symbol: z.string(),
  action: z.string(),
  confidence: z.number(),
  convictionScore: z.number(),
  riskFlags: z.array(z.string()),
  entryDiscipline: z.string(),
  exitGuard: z.string(),
  reasoning: z.string()
});

export const analyticsSanityCheckSchema = z.object({
  label: z.string(),
  status: z.enum(["pass", "watch", "fail"]),
  detail: z.string()
});

export const portfolioAnalyticsSchema = z.object({
  generatedAt: z.string(),
  cachedForDate: z.string(),
  nextRefreshAt: z.string(),
  modelVersion: z.string(),
  dataQualityScore: z.number(),
  summary: z.string(),
  companies: z.array(companyAnalyticsSchema),
  decisionSignals: z.array(decisionSignalSchema),
  sanityChecks: z.array(analyticsSanityCheckSchema),
  warnings: z.array(z.string())
});

export const openAiSettingsSchema = z.object({
  configured: z.boolean(),
  provider: z.enum(["gemini", "openai"]),
  maskedKey: z.string().nullable().optional(),
  model: z.string()
});

export const aiAnalyticsInsightSchema = z.object({
  configured: z.boolean(),
  provider: z.enum(["gemini", "openai"]).nullable().optional(),
  generatedAt: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
  summary: z.string(),
  buyFocus: z.array(z.string()),
  holdFocus: z.array(z.string()),
  sellOrReviewFocus: z.array(z.string()),
  riskControls: z.array(z.string()),
  dataWarnings: z.array(z.string())
});

export const discoveryCandidateSchema = z.object({
  symbol: z.string(),
  companyName: z.string(),
  sector: z.string().nullable().optional(),
  industry: z.string().nullable().optional(),
  lastPrice: z.number().nullable().optional(),
  discoveryScore: z.number(),
  conviction: z.enum(["High", "Medium", "Low"]),
  riskLevel: z.enum(["Low", "Medium", "High"]),
  recommendation: z.string(),
  whyBuy: z.array(z.string()),
  companyPotential: z.array(z.string()),
  risks: z.array(z.string()),
  entryDiscipline: z.string(),
  verificationTriggers: z.array(z.string()),
  researchView: z.string(),
  dataQualityScore: z.number(),
  sourceNotes: z.array(z.string())
});

export const stockDiscoverySchema = z.object({
  generatedAt: z.string(),
  universe: z.string(),
  methodology: z.string(),
  candidates: z.array(discoveryCandidateSchema),
  excludedSymbols: z.array(z.string()),
  warnings: z.array(z.string())
});

export type Holding = z.infer<typeof holdingSchema>;
export type Allocation = z.infer<typeof allocationSchema>;
export type PortfolioSummary = z.infer<typeof portfolioSummarySchema>;
export type PortfolioAlert = z.infer<typeof portfolioAlertSchema>;
export type StockRecommendation = z.infer<typeof stockRecommendationSchema>;
export type PortfolioIntelligence = z.infer<typeof portfolioIntelligenceSchema>;
export type AnalyticsMetric = z.infer<typeof analyticsMetricSchema>;
export type CompanyNews = z.infer<typeof companyNewsSchema>;
export type CompanyAnalytics = z.infer<typeof companyAnalyticsSchema>;
export type DecisionSignal = z.infer<typeof decisionSignalSchema>;
export type AnalyticsSanityCheck = z.infer<typeof analyticsSanityCheckSchema>;
export type PortfolioAnalytics = z.infer<typeof portfolioAnalyticsSchema>;
export type OpenAiSettings = z.infer<typeof openAiSettingsSchema>;
export type AiAnalyticsInsight = z.infer<typeof aiAnalyticsInsightSchema>;
export type DiscoveryCandidate = z.infer<typeof discoveryCandidateSchema>;
export type StockDiscovery = z.infer<typeof stockDiscoverySchema>;
