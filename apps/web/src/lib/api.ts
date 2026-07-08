import {
  aiAnalyticsInsightSchema,
  openAiSettingsSchema,
  portfolioAnalyticsSchema,
  portfolioIntelligenceSchema,
  portfolioSummarySchema,
  stockDiscoverySchema,
  type AiAnalyticsInsight,
  type OpenAiSettings,
  type PortfolioAnalytics,
  type PortfolioIntelligence,
  type PortfolioSummary,
  type StockDiscovery
} from "@portfolio/shared";

import { fallbackPortfolio } from "@/lib/mock-data";
import { authHeaders } from "@/lib/auth";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type ReadOnlyConnectResponse = {
  authorization_url: string;
  read_only: boolean;
  message: string;
};

export type ZerodhaConnectInput = {
  zerodhaUserId: string;
  accountLabel: string;
};

export type ManualPortfolioImportResponse = {
  importedCount: number;
  skippedCount: number;
  message: string;
};

type McpConnectResponse = {
  authorization_url: string;
  read_only: boolean;
  message: string;
};

export type BrokerStatus = {
  broker: string;
  status: string;
  read_only: boolean;
  last_synced_at: string | null;
};

export async function fetchPortfolioSummary(): Promise<PortfolioSummary> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/portfolio/summary`, {
      headers: authHeaders(),
      cache: "no-store"
    });
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error("Sign in to continue.");
      }
      throw new Error(`Portfolio API returned ${response.status}`);
    }
    return portfolioSummarySchema.parse(await response.json());
  } catch (error) {
    if (error instanceof Error && error.message === "Sign in to continue.") {
      throw error;
    }
    return fallbackPortfolio;
  }
}

export async function fetchPortfolioIntelligence(): Promise<PortfolioIntelligence> {
  const response = await fetch(`${apiBaseUrl}/api/v1/intelligence/analysis`, {
    headers: authHeaders(),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Portfolio intelligence API returned ${response.status}`);
  }
  return portfolioIntelligenceSchema.parse(await response.json());
}

export async function runPortfolioIntelligence(): Promise<PortfolioIntelligence> {
  const response = await fetch(`${apiBaseUrl}/api/v1/intelligence/run`, {
    method: "POST",
    headers: authHeaders(),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Portfolio intelligence run returned ${response.status}`);
  }
  return portfolioIntelligenceSchema.parse(await response.json());
}

export async function fetchZerodhaStatus(): Promise<BrokerStatus> {
  const response = await fetch(`${apiBaseUrl}/api/v1/zerodha/status`, {
    headers: authHeaders(),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Zerodha status API returned ${response.status}`);
  }
  return response.json();
}

export async function fetchPortfolioAnalytics(forceRefresh = false): Promise<PortfolioAnalytics> {
  const params = new URLSearchParams();
  if (forceRefresh) {
    params.set("forceRefresh", "true");
  }
  const response = await fetch(`${apiBaseUrl}/api/v1/analytics/company?${params.toString()}`, {
    headers: authHeaders(),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Company analytics API returned ${response.status}`);
  }
  return portfolioAnalyticsSchema.parse(await response.json());
}

export async function runDailyAnalyticsRefresh(): Promise<{ status: string; refreshedUsers: number }> {
  const response = await fetch(`${apiBaseUrl}/api/v1/analytics/daily-refresh`, {
    method: "POST",
    headers: authHeaders(),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Daily analytics refresh returned ${response.status}`);
  }
  return response.json();
}

export async function fetchOpenAiSettings(): Promise<OpenAiSettings> {
  const response = await fetch(`${apiBaseUrl}/api/v1/settings/openai`, {
    headers: authHeaders(),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`AI settings API returned ${response.status}`);
  }
  return openAiSettingsSchema.parse(await response.json());
}

export async function saveOpenAiSettings(input: { apiKey: string; provider: "gemini" | "openai"; model?: string }): Promise<OpenAiSettings> {
  const response = await fetch(`${apiBaseUrl}/api/v1/settings/openai`, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(input)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : `AI settings save returned ${response.status}`;
    throw new Error(detail);
  }
  return openAiSettingsSchema.parse(await response.json());
}

export async function deleteOpenAiSettings(): Promise<OpenAiSettings> {
  const response = await fetch(`${apiBaseUrl}/api/v1/settings/openai`, {
    method: "DELETE",
    headers: authHeaders()
  });
  if (!response.ok) {
    throw new Error(`AI settings delete returned ${response.status}`);
  }
  return openAiSettingsSchema.parse(await response.json());
}

export async function runOpenAiAnalyticsInsight(): Promise<AiAnalyticsInsight> {
  const response = await fetch(`${apiBaseUrl}/api/v1/analytics/openai-insight`, {
    method: "POST",
    headers: authHeaders(),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`AI analytics insight returned ${response.status}`);
  }
  return aiAnalyticsInsightSchema.parse(await response.json());
}

export async function fetchStockDiscovery(): Promise<StockDiscovery> {
  const response = await fetch(`${apiBaseUrl}/api/v1/discovery/new-shares`, {
    headers: authHeaders(),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Stock discovery API returned ${response.status}`);
  }
  return stockDiscoverySchema.parse(await response.json());
}

export async function createZerodhaReadOnlyConnection(input: ZerodhaConnectInput): Promise<ReadOnlyConnectResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/zerodha/connect/read-only`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(input)
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : `Zerodha connect API returned ${response.status}`;
    throw new Error(detail);
  }
  return response.json();
}

export async function uploadManualPortfolioCsv(file: File): Promise<ManualPortfolioImportResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${apiBaseUrl}/api/v1/portfolio/manual-import`, {
    method: "POST",
    headers: authHeaders(),
    body: formData
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : `Portfolio import returned ${response.status}`;
    throw new Error(detail);
  }
  return response.json();
}

export async function createZerodhaMcpConnection(): Promise<McpConnectResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/zerodha/mcp/connect`, {
    method: "POST",
    headers: authHeaders()
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : `Kite MCP connect returned ${response.status}`;
    throw new Error(detail);
  }
  return response.json();
}

export async function syncZerodhaMcpHoldings(): Promise<ManualPortfolioImportResponse> {
  const response = await fetch(`${apiBaseUrl}/api/v1/zerodha/mcp/sync`, {
    method: "POST",
    headers: authHeaders()
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : `Kite MCP sync returned ${response.status}`;
    throw new Error(detail);
  }
  return response.json();
}
