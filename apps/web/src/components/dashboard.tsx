"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  Atom,
  BadgeCheck,
  BarChart3,
  Bot,
  BrainCircuit,
  BriefcaseBusiness,
  Building2,
  CalendarClock,
  CheckCircle2,
  CircleDollarSign,
  ClipboardList,
  CircuitBoard,
  Database,
  DatabaseZap,
  FileText,
  Fingerprint,
  Gauge,
  KeyRound,
  Layers,
  LineChart,
  LinkIcon,
  ListChecks,
  LockKeyhole,
  LogOut,
  Newspaper,
  Orbit,
  PieChart,
  RefreshCw,
  RadioTower,
  Rocket,
  ScanLine,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  UserCircle,
  Wallet,
  X,
  Zap
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  AiAnalyticsInsight,
  CompanyAnalytics,
  Holding,
  OpenAiSettings,
  PortfolioAnalytics,
  PortfolioIntelligence,
  PortfolioSummary,
  StockDiscovery
} from "@portfolio/shared";

import { ManualPortfolioUpload } from "@/components/manual-portfolio-upload";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  createZerodhaMcpConnection,
  deleteOpenAiSettings,
  fetchOpenAiSettings,
  fetchPortfolioAnalytics,
  fetchZerodhaStatus,
  fetchPortfolioIntelligence,
  fetchPortfolioSummary,
  fetchStockDiscovery,
  runDailyAnalyticsRefresh,
  runOpenAiAnalyticsInsight,
  runPortfolioIntelligence,
  saveOpenAiSettings,
  syncZerodhaMcpHoldings
} from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useUiStore } from "@/store/ui-store";

type DashboardView = "overview" | "risk" | "reports" | "analytics" | "discover";
type NavItem = [DashboardView, typeof BriefcaseBusiness, string];
type ReportAction = {
  priority: "High" | "Medium" | "Low";
  title: string;
  reason: string;
  timing: string;
};
type ReportSection = "summary" | "actions" | "analytics" | "quality" | "calendar";
type OverviewTileId = "pulse" | "capital" | "performance" | "sync";
type AiProvider = "gemini" | "openai";
type InvestorRiskProfile = "conservative" | "balanced" | "aggressive";
type InvestorHorizon = "short" | "swing" | "long";
type MarketCapFilter = "all" | "Large Cap" | "Mid Cap" | "Small Cap";

const RECOMMENDED_GEMINI_MODEL = "gemini-3.5-flash";
const GEMINI_MODEL_OPTIONS = [
  {
    value: "gemini-3.5-flash",
    label: "Gemini 3.5 Flash",
    detail: "Recommended latest free-tier model for deeper portfolio analysis."
  },
  {
    value: "gemini-3.1-flash-lite",
    label: "Gemini 3.1 Flash-Lite",
    detail: "Free-tier lightweight option for faster, lower-cost analysis."
  },
  {
    value: "gemini-2.5-flash",
    label: "Gemini 2.5 Flash",
    detail: "Free-tier fallback with strong reasoning and broad availability."
  },
  {
    value: "gemini-2.5-flash-lite",
    label: "Gemini 2.5 Flash-Lite",
    detail: "Free-tier fallback for very fast responses."
  }
];
const AI_ANALYSIS_STEPS = [
  {
    at: 0,
    percent: 8,
    title: "Starting analysis",
    detail: "Checking AI configuration and preparing the request."
  },
  {
    at: 2,
    percent: 22,
    title: "Reading portfolio data",
    detail: "Loading your holdings, company analytics, decision signals and sanity checks."
  },
  {
    at: 5,
    percent: 38,
    title: "Building evidence pack",
    detail: "Organizing fundamentals, valuation, cash flow, price context and news into one prompt."
  },
  {
    at: 8,
    percent: 56,
    title: "Sending to AI model",
    detail: "Submitting the holdings-only analysis request to your selected AI provider."
  },
  {
    at: 12,
    percent: 74,
    title: "AI is reasoning",
    detail: "Waiting for buy, hold, review, risk-control and data-warning sections."
  },
  {
    at: 18,
    percent: 88,
    title: "Formatting insights",
    detail: "Validating structured output and preparing the dashboard tiles."
  },
  {
    at: 26,
    percent: 94,
    title: "Final checks",
    detail: "Holding here until the provider returns the completed analysis."
  }
];

export function Dashboard() {
  const auth = useAuth();
  const { view, setView } = useUiStore();
  const queryClient = useQueryClient();
  const { data, isFetching, refetch } = useQuery({
    queryKey: ["portfolio-summary"],
    queryFn: fetchPortfolioSummary
  });
  const {
    data: intelligence,
    isFetching: isAnalyzing,
    refetch: refetchIntelligence
  } = useQuery({
    queryKey: ["portfolio-intelligence"],
    queryFn: fetchPortfolioIntelligence,
    staleTime: 60_000
  });
  const { data: zerodhaStatus, refetch: refetchZerodhaStatus } = useQuery({
    queryKey: ["zerodha-status"],
    queryFn: fetchZerodhaStatus,
    refetchInterval: 30_000
  });
  const {
    data: analytics,
    isFetching: isFetchingAnalytics,
    refetch: refetchAnalytics
  } = useQuery({
    queryKey: ["portfolio-analytics"],
    queryFn: () => fetchPortfolioAnalytics(false),
    staleTime: 24 * 60 * 60 * 1000
  });
  const { data: openAiSettings, refetch: refetchOpenAiSettings } = useQuery({
    queryKey: ["openai-settings"],
    queryFn: fetchOpenAiSettings
  });
  const {
    data: discovery,
    isFetching: isFetchingDiscovery,
    refetch: refetchDiscovery
  } = useQuery({
    queryKey: ["stock-discovery"],
    queryFn: fetchStockDiscovery,
    staleTime: 30 * 60 * 1000
  });
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSyncingMcp, setIsSyncingMcp] = useState(false);
  const [isAutoSyncing, setIsAutoSyncing] = useState(false);
  const [isRunningAnalysis, setIsRunningAnalysis] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);
  const [connectMessage, setConnectMessage] = useState<string | null>(null);
  const [connectUrl, setConnectUrl] = useState<string | null>(null);
  const [isConnectPanelOpen, setIsConnectPanelOpen] = useState(false);
  const [isOpenAiPanelOpen, setIsOpenAiPanelOpen] = useState(false);
  const [openAiKeyInput, setOpenAiKeyInput] = useState("");
  const [aiProviderInput, setAiProviderInput] = useState<AiProvider>("gemini");
  const [openAiModelInput, setOpenAiModelInput] = useState(RECOMMENDED_GEMINI_MODEL);
  const [openAiMessage, setOpenAiMessage] = useState<string | null>(null);
  const [openAiError, setOpenAiError] = useState<string | null>(null);
  const [isSavingOpenAi, setIsSavingOpenAi] = useState(false);
  const [aiInsight, setAiInsight] = useState<AiAnalyticsInsight | null>(null);
  const [aiInsightError, setAiInsightError] = useState<string | null>(null);
  const [isGeneratingAiInsight, setIsGeneratingAiInsight] = useState(false);
  const [isRunningUnifiedAnalytics, setIsRunningUnifiedAnalytics] = useState(false);
  const [unifiedAnalyticsReady, setUnifiedAnalyticsReady] = useState(false);
  const autoSyncInFlight = useRef(false);

  const zerodhaAutoSyncEnabled =
    typeof window !== "undefined" && window.localStorage.getItem("zerodha:auto-sync") === "enabled";

  useEffect(() => {
    if (zerodhaStatus?.status === "connected") {
      window.localStorage.setItem("zerodha:auto-sync", "enabled");
    }
  }, [zerodhaStatus?.status]);

  useEffect(() => {
    if (openAiSettings) {
      setAiProviderInput(openAiSettings.provider);
      setOpenAiModelInput(openAiSettings.model);
    }
  }, [openAiSettings]);

  useEffect(() => {
    if (!zerodhaAutoSyncEnabled && zerodhaStatus?.status !== "connected") {
      return;
    }

    const runAutoSync = async () => {
      if (autoSyncInFlight.current) {
        return;
      }
      autoSyncInFlight.current = true;
      setIsAutoSyncing(true);
      try {
        await syncZerodhaMcpHoldings();
        await refetch();
        await refetchIntelligence();
        await refetchZerodhaStatus();
      } catch {
        // The next interval will retry. If Zerodha expires the session, manual reconnect is required.
      } finally {
        setIsAutoSyncing(false);
        autoSyncInFlight.current = false;
      }
    };

    const firstRun = window.setTimeout(() => {
      void runAutoSync();
    }, 15_000);
    const interval = window.setInterval(() => {
      void runAutoSync();
    }, 180_000);

    return () => {
      window.clearTimeout(firstRun);
      window.clearInterval(interval);
    };
  }, [refetch, refetchIntelligence, refetchZerodhaStatus, zerodhaAutoSyncEnabled, zerodhaStatus?.status]);

  async function handleConnectZerodha() {
    setIsConnecting(true);
    setConnectError(null);
    setConnectMessage(null);
    setConnectUrl(null);
    const zerodhaWindow = window.open("about:blank", "_blank");
    if (zerodhaWindow) {
      zerodhaWindow.opener = null;
      zerodhaWindow.document.title = "Opening Zerodha...";
      zerodhaWindow.document.body.textContent = "Opening Zerodha...";
    }
    try {
      const result = await createZerodhaMcpConnection();
      window.localStorage.setItem("zerodha:auto-sync", "enabled");
      setConnectUrl(result.authorization_url);
      if (zerodhaWindow) {
        zerodhaWindow.location.assign(result.authorization_url);
        setConnectMessage("Zerodha opened in a new tab. Approve there, then return here. This app will auto-sync every 3 minutes.");
      } else {
        setConnectMessage("Popup blocked. Use the Zerodha login link below, approve there, then return here. This app will auto-sync every 3 minutes.");
      }
    } catch (error) {
      zerodhaWindow?.close();
      setConnectError(error instanceof Error ? error.message : "Unable to start Zerodha connection.");
    } finally {
      setIsConnecting(false);
    }
  }

  async function syncMcpHoldings({ quiet = false }: { quiet?: boolean } = {}) {
    if (autoSyncInFlight.current) {
      return;
    }
    autoSyncInFlight.current = true;
    if (!quiet) {
      setIsSyncingMcp(true);
      setConnectError(null);
      setConnectMessage(null);
    }
    try {
      const result = await syncZerodhaMcpHoldings();
      window.localStorage.setItem("zerodha:auto-sync", "enabled");
      if (!quiet) {
        setConnectMessage(`${result.importedCount} holdings synced from Zerodha MCP. Auto-sync will run every 3 minutes.`);
      }
      await refetch();
      await refetchIntelligence();
      await refetchZerodhaStatus();
    } catch (error) {
      if (!quiet) {
        setConnectError(error instanceof Error ? error.message : "Unable to sync Zerodha holdings.");
      }
      throw error;
    } finally {
      if (!quiet) {
        setIsSyncingMcp(false);
      }
      autoSyncInFlight.current = false;
    }
  }

  async function handleSyncMcpHoldings() {
    await syncMcpHoldings();
  }

  async function handleAnalyze() {
    setIsRunningAnalysis(true);
    setConnectError(null);
    try {
      if (zerodhaAutoSyncEnabled || zerodhaStatus?.status === "connected") {
        try {
          await syncMcpHoldings({ quiet: true });
        } catch (error) {
          setConnectError(
            error instanceof Error
              ? `Zerodha refresh failed, so analysis used last saved holdings. ${error.message}`
              : "Zerodha refresh failed, so analysis used last saved holdings."
          );
        }
      }
      const latest = await runPortfolioIntelligence();
      queryClient.setQueryData(["portfolio-intelligence"], latest);
      await refetch();
    } finally {
      setIsRunningAnalysis(false);
    }
  }

  async function handleSaveOpenAiSettings() {
    setIsSavingOpenAi(true);
    setOpenAiError(null);
    setOpenAiMessage(null);
    try {
      const latest = await saveOpenAiSettings({
        apiKey: openAiKeyInput.trim(),
        provider: aiProviderInput,
        model: openAiModelInput.trim()
      });
      queryClient.setQueryData(["openai-settings"], latest);
      setOpenAiKeyInput("");
      setOpenAiMessage(`${aiProviderInput === "gemini" ? "Gemini" : "OpenAI"} connection verified successfully.`);
      await refetchOpenAiSettings();
    } catch (error) {
      setOpenAiError(error instanceof Error ? error.message : "Unable to save OpenAI key.");
    } finally {
      setIsSavingOpenAi(false);
    }
  }

  async function handleDeleteOpenAiSettings() {
    setIsSavingOpenAi(true);
    setOpenAiError(null);
    setOpenAiMessage(null);
    try {
      const latest = await deleteOpenAiSettings();
      queryClient.setQueryData(["openai-settings"], latest);
      setAiInsight(null);
      setAiInsightError(null);
      setOpenAiMessage("AI key removed.");
      await refetchOpenAiSettings();
    } catch (error) {
      setOpenAiError(error instanceof Error ? error.message : "Unable to remove OpenAI key.");
    } finally {
      setIsSavingOpenAi(false);
    }
  }

  async function handleGenerateAiInsight() {
    setIsGeneratingAiInsight(true);
    setAiInsightError(null);
    try {
      const latest = await runOpenAiAnalyticsInsight();
      setAiInsight(latest);
    } catch (error) {
      setAiInsightError(
        error instanceof Error
          ? error.message
          : "AI analysis failed. Check that the backend is running and your AI key is saved."
      );
    } finally {
      setIsGeneratingAiInsight(false);
    }
  }

  async function handleRunUnifiedAnalytics() {
    setIsRunningUnifiedAnalytics(true);
    setAiInsightError(null);
    setUnifiedAnalyticsReady(false);
    try {
      const latestAnalytics = await fetchPortfolioAnalytics(true);
      queryClient.setQueryData(["portfolio-analytics"], latestAnalytics);
      await refetchAnalytics();
      const latestInsight = await runOpenAiAnalyticsInsight();
      setAiInsight(latestInsight);
      setUnifiedAnalyticsReady(Boolean(latestInsight.configured && latestAnalytics.companies.length));
    } catch (error) {
      setAiInsightError(error instanceof Error ? error.message : "Unable to complete unified analytics run.");
    } finally {
      setIsRunningUnifiedAnalytics(false);
    }
  }

  if (!data) {
    return <main className="min-h-screen bg-background" />;
  }

  const pnlTone = data.dayPnl >= 0 ? "text-profit" : "text-loss";

  return (
    <main className="relative min-h-screen overflow-hidden bg-background">
      <MarketPulseFx />
      <div className="relative z-10 border-b border-border bg-black/30 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent text-black">
              <LineChart size={22} />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-normal">AI Portfolio Advisor</h1>
              <p className="text-sm text-muted">Read-only Zerodha intelligence</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw size={18} className={isFetching ? "animate-spin" : ""} />
              Sync
            </Button>
            <Button variant="ghost" onClick={handleAnalyze} disabled={isAnalyzing || isRunningAnalysis}>
              <Bot size={18} className={isAnalyzing || isRunningAnalysis ? "animate-pulse" : ""} />
              {isRunningAnalysis ? "Analyzing" : "Analyze"}
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setOpenAiMessage(null);
                setOpenAiError(null);
                setOpenAiKeyInput("");
                setIsOpenAiPanelOpen(true);
              }}
            >
              <KeyRound size={18} />
              AI Config
            </Button>
            <ManualPortfolioUpload
              onImported={() => {
                void refetch();
                void refetchIntelligence();
              }}
            />
            <Button onClick={() => setIsConnectPanelOpen(true)} disabled={isConnecting}>
              <LinkIcon size={18} />
              Connect Zerodha
            </Button>
            <div className="flex h-10 items-center gap-2 rounded-md border border-border bg-white/5 px-3 text-sm text-muted">
              <UserCircle size={18} />
              <span className="max-w-[150px] truncate">{auth.user?.email ?? "Account"}</span>
            </div>
            <Button variant="ghost" onClick={() => void auth.logout()} title="Sign out" aria-label="Sign out">
              <LogOut size={18} />
            </Button>
          </div>
          {connectError ? <p className="basis-full text-right text-sm text-loss">{connectError}</p> : null}
        </div>
      </div>

      <div className="relative z-10 mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[240px_1fr]">
        <aside className="hidden lg:block">
          <nav className="sticky top-5 space-y-2">
            {([
              ["overview", BriefcaseBusiness, "Overview"],
              ["risk", ShieldCheck, "Risk"],
              ["reports", CalendarClock, "Reports"],
              ["analytics", Building2, "Analytics"],
              ["discover", Search, "Discover"]
            ] satisfies NavItem[]).map(([id, Icon, label]) => (
              <button
                key={id}
                onClick={() => setView(id)}
                className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition ${
                  view === id ? "bg-white/12 text-foreground" : "text-muted hover:bg-white/8 hover:text-foreground"
                }`}
              >
                <Icon size={18} />
                {label}
              </button>
            ))}
          </nav>
        </aside>

        <section className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric title="Portfolio Value" value={formatCurrency(data.portfolioValue)} icon={<Wallet size={18} />} />
            <Metric
              title="Today's P&L"
              value={formatCurrency(data.dayPnl)}
              detail={formatPercent(data.dayPnlPct)}
              tone={pnlTone}
              icon={<LineChart size={18} />}
            />
            <Metric
              title="Overall P&L"
              value={formatCurrency(data.totalPnl)}
              detail={formatPercent(data.totalPnlPct)}
              tone={data.totalPnl >= 0 ? "text-profit" : "text-loss"}
              icon={<Gauge size={18} />}
            />
            <Metric title="Health Score" value={`${data.healthScore}/100`} detail="AI risk model" icon={<Bot size={18} />} />
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={view}
              initial={{ opacity: 0, y: 18, scale: 0.985, filter: "blur(8px)" }}
              animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -12, scale: 0.99, filter: "blur(6px)" }}
              transition={{ duration: 0.34, ease: "easeOut" }}
              className="grid gap-5"
            >
              {view === "analytics" ? (
                <UnifiedAnalyticsWorkspace
                  analytics={analytics}
                  settings={openAiSettings}
                  insight={aiInsight}
                  error={aiInsightError}
                  isRunning={isRunningUnifiedAnalytics}
                  isReady={unifiedAnalyticsReady}
                  onRun={handleRunUnifiedAnalytics}
                  onConfigure={() => setIsOpenAiPanelOpen(true)}
                />
              ) : view === "discover" ? (
                <StockDiscoveryView
                  discovery={discovery}
                  isLoading={isFetchingDiscovery}
                  onRefresh={async () => {
                    await refetchDiscovery();
                  }}
                />
              ) : view === "reports" ? (
                <PortfolioReport
                  data={data}
                  intelligence={intelligence}
                  analytics={analytics}
                  aiInsight={aiInsight}
                  aiInsightError={aiInsightError}
                  aiSettings={openAiSettings}
                  isGeneratingAiInsight={isGeneratingAiInsight}
                  onGenerateAiInsight={handleGenerateAiInsight}
                  onRefresh={handleAnalyze}
                />
              ) : view === "overview" ? (
                <PortfolioOverview data={data} intelligence={intelligence} onAnalyze={handleAnalyze} />
              ) : (
                <PortfolioRisk data={data} intelligence={intelligence} />
              )}
            </motion.div>
          </AnimatePresence>
        </section>
      </div>

      {isConnectPanelOpen ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 px-4 py-6 backdrop-blur-sm sm:items-center">
          <div className="my-auto w-full max-w-md rounded-lg border border-border bg-panel p-5 shadow-glow">
            <div className="mb-5 flex items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold">Connect Zerodha MCP</h2>
                <p className="mt-1 text-sm text-muted">One-click auth. Password, PIN and OTP stay on Zerodha.</p>
              </div>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setIsConnectPanelOpen(false)}
                className="rounded-md border border-border bg-white/5 p-2 text-muted transition hover:bg-white/10 hover:text-foreground"
              >
                <X size={16} />
              </button>
            </div>

            <div className="mb-5 rounded-md border border-border bg-black/20 p-3 text-sm text-muted">
              This app only calls read-only MCP tools: holdings, positions, margins, orders history and quotes. Trading
              tools are blocked.
            </div>

            {connectError ? <p className="mb-4 text-sm text-loss">{connectError}</p> : null}
            {connectMessage ? <p className="mb-4 text-sm text-profit">{connectMessage}</p> : null}
            {zerodhaStatus ? (
              <div className="mb-4 rounded-md border border-border bg-white/5 p-3 text-sm text-muted">
                Zerodha status: <span className="text-foreground">{zerodhaStatus.status}</span>
                {zerodhaStatus.last_synced_at ? (
                  <span> · Last sync {new Date(zerodhaStatus.last_synced_at).toLocaleString()}</span>
                ) : null}
                {isAutoSyncing ? <span className="text-accent"> · Auto-sync running</span> : null}
              </div>
            ) : null}
            {connectUrl ? (
              <a
                href={connectUrl}
                target="_blank"
                rel="noreferrer"
                className="mb-4 block text-sm text-accent underline-offset-4 hover:underline"
              >
                Open Zerodha login
              </a>
            ) : null}

            <div className="flex flex-wrap justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setIsConnectPanelOpen(false)}>
                Cancel
              </Button>
              <Button type="button" variant="ghost" onClick={handleSyncMcpHoldings} disabled={isSyncingMcp}>
                <RefreshCw size={18} className={isSyncingMcp ? "animate-spin" : ""} />
                {isSyncingMcp ? "Syncing" : "Sync Holdings"}
              </Button>
              <Button type="button" onClick={handleConnectZerodha} disabled={isConnecting}>
                <LinkIcon size={18} />
                {isConnecting ? "Opening" : "Connect"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {isOpenAiPanelOpen ? (
        <OpenAiConfigPanel
          settings={openAiSettings}
          apiKey={openAiKeyInput}
          provider={aiProviderInput}
          model={openAiModelInput}
          message={openAiMessage}
          error={openAiError}
          isValidated={Boolean(openAiMessage?.toLowerCase().includes("connection verified")) && !openAiError}
          isSaving={isSavingOpenAi}
          onApiKeyChange={(value) => {
            setOpenAiKeyInput(value);
            setOpenAiMessage(null);
            setOpenAiError(null);
          }}
          onProviderChange={(provider) => {
            setAiProviderInput(provider);
            setOpenAiModelInput(provider === "gemini" ? RECOMMENDED_GEMINI_MODEL : "gpt-4.1-mini");
            setOpenAiMessage(null);
            setOpenAiError(null);
          }}
          onModelChange={(value) => {
            setOpenAiModelInput(value);
            setOpenAiMessage(null);
            setOpenAiError(null);
          }}
          onSave={handleSaveOpenAiSettings}
          onDelete={handleDeleteOpenAiSettings}
          onClose={() => setIsOpenAiPanelOpen(false)}
        />
      ) : null}
    </main>
  );
}

function PortfolioOverview({
  data,
  intelligence,
  onAnalyze
}: {
  data: PortfolioSummary;
  intelligence?: PortfolioIntelligence;
  onAnalyze: () => void;
}) {
  const topHoldings = [...data.holdings].sort((a, b) => b.allocationPct - a.allocationPct);
  const bestHolding = [...data.holdings].sort((a, b) => b.totalPnl - a.totalPnl)[0];
  const weakestHolding = [...data.holdings].sort((a, b) => a.totalPnl - b.totalPnl)[0];
  const largestSector = [...data.sectorAllocation].sort((a, b) => b.percentage - a.percentage)[0];
  const totalCapital = data.portfolioValue + data.cashBalance;
  const cashPct = totalCapital > 0 ? (data.cashBalance / totalCapital) * 100 : 0;
  const topThreeAllocation = topHoldings.slice(0, 3).reduce((sum, holding) => sum + holding.allocationPct, 0);
  const highRiskCount = intelligence?.alerts.filter((alert) => alert.severity === "high").length ?? 0;
  const verdict = getPortfolioVerdict(data.healthScore, topThreeAllocation, highRiskCount, cashPct);
  const generatedAt = new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(intelligence?.generatedAt ?? data.updatedAt));
  const tiles: Array<{
    id: OverviewTileId;
    label: string;
    value: string;
    detail: string;
    tone: string;
    icon: React.ReactNode;
  }> = [
    {
      id: "pulse",
      label: "Portfolio Pulse",
      value: `${data.healthScore}/100`,
      detail: verdict.label,
      tone: "from-cyan-300/20 to-emerald-300/10",
      icon: <Activity size={18} />
    },
    {
      id: "capital",
      label: "Capital",
      value: formatCurrency(totalCapital),
      detail: `${cashPct.toFixed(1)}% cash`,
      tone: "from-emerald-300/18 to-cyan-300/8",
      icon: <Wallet size={18} />
    },
    {
      id: "performance",
      label: "Performance",
      value: formatPercent(data.totalPnlPct),
      detail: data.totalPnl >= 0 ? "Portfolio in profit" : "Portfolio below cost",
      tone: data.totalPnl >= 0 ? "from-lime-300/18 to-cyan-300/8" : "from-rose-300/18 to-cyan-300/8",
      icon: <TrendingUp size={18} />
    },
    {
      id: "sync",
      label: "Live Data",
      value: `${intelligence?.dataQuality.score ?? 72}/100`,
      detail: `Updated ${generatedAt}`,
      tone: "from-sky-300/18 to-white/5",
      icon: <Bot size={18} />
    }
  ];

  return (
    <div className="overflow-hidden rounded-lg border border-cyan-200/14 bg-[#081214] shadow-[0_28px_90px_rgba(45,212,191,0.14)]">
      <div className="border-b border-cyan-200/14 bg-[radial-gradient(circle_at_20%_0%,rgba(45,212,191,0.24),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.92),rgba(8,18,20,0.96))] p-4">
        <div className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
          <div className="min-h-[230px] rounded-md border border-cyan-200/14 bg-black/20 p-5">
            <div className="mb-2 flex items-center gap-2 text-sm text-cyan-200">
              <Layers size={18} />
              Overview
            </div>
            <h2 className="max-w-2xl text-3xl font-semibold tracking-normal">Portfolio cockpit</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-cyan-50/68">
              A quick operating view of capital, current return and live-data quality. Risk details and action calls live in their own tabs.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <GlassStat label="Invested" value={formatCurrency(data.portfolioValue)} />
              <GlassStat label="Cash buffer" value={`${cashPct.toFixed(1)}%`} />
              <GlassStat label="Holdings" value={`${data.holdings.length}`} />
            </div>
            <Button type="button" className="mt-5" onClick={onAnalyze}>
              <Bot size={18} />
              Refresh Live Analysis
            </Button>
          </div>
          <div className="rounded-md border border-cyan-200/14 bg-cyan-200/[0.06] p-5">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-cyan-100/62">Advisor stance</p>
                <h3 className={`mt-1 text-2xl font-semibold ${verdict.tone}`}>{verdict.label}</h3>
              </div>
              <ShieldCheck className="text-cyan-200" size={26} />
            </div>
            <p className="text-sm leading-6 text-cyan-50/72">{verdict.detail}</p>
            <div className="mt-5 h-3 overflow-hidden rounded-full bg-black/35">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${data.healthScore}%` }}
                transition={{ duration: 0.55, ease: "easeOut" }}
                className="h-3 rounded-full bg-cyan-200"
              />
            </div>
            <div className="mt-3 flex justify-between text-xs text-cyan-50/55">
              <span>Defensive</span>
              <span>{data.healthScore}/100</span>
              <span>Healthy</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 border-b border-cyan-200/10 bg-black/16 p-4 md:grid-cols-2 xl:grid-cols-4">
        {tiles.map((tile) => (
          <OverviewTile
            key={tile.id}
            {...tile}
          />
        ))}
      </div>

      <DecisionReadinessBanner
        qualityScore={intelligence?.dataQuality.score ?? 0}
        warnings={intelligence?.dataQuality.warnings ?? ["Run live analysis to calculate data quality before acting."]}
      />

      <div className="grid gap-4 p-4 xl:grid-cols-[1.25fr_0.75fr]">
        <ConsultantDecisionBoard
          data={data}
          intelligence={intelligence}
          topThreeAllocation={topThreeAllocation}
          cashPct={cashPct}
        />

        <div className="grid gap-4">
          <section className="rounded-md border border-cyan-200/12 bg-white/[0.045] p-4">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold">Portfolio mix</h3>
              <PieChart className="text-cyan-200" size={20} />
            </div>
            <div className="space-y-3">
              {data.sectorAllocation.slice(0, 4).map((sector) => (
                <CapitalBar key={sector.label} label={sector.label} value={sector.value} total={data.portfolioValue} tone="bg-cyan-200" />
              ))}
            </div>
            <p className="mt-3 text-xs text-cyan-50/50">
              Largest: {largestSector ? `${largestSector.label} ${largestSector.percentage.toFixed(1)}%` : "Not available"}
            </p>
          </section>

          <section className="rounded-md border border-cyan-200/12 bg-white/[0.045] p-4">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-base font-semibold">Performance pulse</h3>
              <LineChart className="text-profit" size={20} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <GlassStat label="Best contributor" value={bestHolding ? bestHolding.symbol : "N/A"} detail={bestHolding ? formatCurrency(bestHolding.totalPnl) : undefined} />
              <GlassStat label="Weakest contributor" value={weakestHolding ? weakestHolding.symbol : "N/A"} detail={weakestHolding ? formatCurrency(weakestHolding.totalPnl) : undefined} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function DecisionReadinessBanner({ qualityScore, warnings }: { qualityScore: number; warnings: string[] }) {
  const readiness =
    qualityScore >= 75
      ? {
          label: "Decision-ready with verification",
          tone: "border-profit/20 bg-profit/10 text-profit",
          detail: "Use the calls as a shortlist, then confirm valuation, trend, news and position sizing before buying or trimming."
        }
      : qualityScore >= 55
        ? {
            label: "Verify before action",
            tone: "border-amber/22 bg-amber/10 text-amber",
            detail: "Treat recommendations as review prompts until missing data and sanity checks are confirmed."
          }
        : {
            label: "Watchlist only",
            tone: "border-loss/22 bg-loss/10 text-loss",
            detail: "Do not buy or sell from this output alone. Improve market data, fundamentals and broker sync first."
          };

  return (
    <section className="border-b border-cyan-200/10 bg-black/22 p-4">
      <div className={`rounded-md border p-4 ${readiness.tone}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-base font-semibold">
              <ShieldCheck size={18} />
              {readiness.label}
            </div>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-current/82">{readiness.detail}</p>
          </div>
          <div className="rounded-md border border-current/20 bg-black/22 px-3 py-2 text-right">
            <div className="text-xs text-current/70">Data quality</div>
            <div className="text-xl font-semibold text-foreground">{qualityScore}/100</div>
          </div>
        </div>
        {warnings.length ? (
          <div className="mt-3 grid gap-2 lg:grid-cols-2">
            {warnings.slice(0, 4).map((warning) => (
              <div key={warning} className="text-sm leading-5 text-current/78">
                {warning}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function ConsultantDecisionBoard({
  data,
  intelligence,
  topThreeAllocation,
  cashPct
}: {
  data: PortfolioSummary;
  intelligence?: PortfolioIntelligence;
  topThreeAllocation: number;
  cashPct: number;
}) {
  const qualityScore = intelligence?.dataQuality.score ?? 0;
  const highRiskCount = intelligence?.alerts.filter((alert) => alert.severity === "high").length ?? 0;
  const reduceCount = intelligence?.recommendations.filter((item) => isReduceCall(item.recommendation)).length ?? 0;
  const addCount = intelligence?.recommendations.filter((item) => isAddCall(item.recommendation)).length ?? 0;
  const grade = getDecisionGrade(qualityScore, data.healthScore, topThreeAllocation, highRiskCount);
  const facts = [
    {
      label: "Actability",
      value: grade.label,
      detail: grade.detail,
      tone: grade.tone,
      icon: <Target size={18} />
    },
    {
      label: "Evidence",
      value: `${qualityScore}/100`,
      detail: qualityScore >= 70 ? "Usable with verification" : "Needs stronger data",
      tone: qualityScore >= 70 ? "text-profit" : qualityScore >= 55 ? "text-amber" : "text-loss",
      icon: <Database size={18} />
    },
    {
      label: "Concentration",
      value: `${topThreeAllocation.toFixed(1)}%`,
      detail: topThreeAllocation > 55 ? "Top 3 positions are heavy" : "Top 3 weight is manageable",
      tone: topThreeAllocation > 55 ? "text-loss" : topThreeAllocation > 42 ? "text-amber" : "text-profit",
      icon: <Layers size={18} />
    },
    {
      label: "Action mix",
      value: `${addCount}/${reduceCount}`,
      detail: "Add vs reduce signals",
      tone: reduceCount > addCount ? "text-amber" : "text-cyan-100",
      icon: <ListChecks size={18} />
    }
  ];

  return (
    <Card className="relative overflow-hidden border-cyan-200/12 bg-black/22 p-0 shadow-none">
      <div className="market-scanline" />
      <div className="border-b border-cyan-200/10 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm text-cyan-100">
              <Gauge size={18} />
              30-year consultant filter
            </div>
            <h3 className="text-xl font-semibold">Decision cockpit</h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-cyan-50/62">
              This panel removes vanity metrics and focuses on whether the portfolio is actionable, overexposed, under-evidenced or ready for a staged decision.
            </p>
          </div>
          <span className={`rounded-md border border-current/25 bg-black/24 px-3 py-2 text-sm font-medium ${grade.tone}`}>
            {grade.call}
          </span>
        </div>
      </div>

      <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4">
        {facts.map((fact, index) => (
          <motion.div
            key={fact.label}
            initial={{ opacity: 0, y: 14, rotateX: -16 }}
            animate={{ opacity: 1, y: 0, rotateX: 0 }}
            transition={{ delay: index * 0.05, duration: 0.36, ease: "easeOut" }}
            className="holo-card rounded-md border border-cyan-200/12 bg-white/[0.045] p-4"
          >
            <div className="mb-4 flex items-center justify-between text-muted">
              <span className="text-sm">{fact.label}</span>
              {fact.icon}
            </div>
            <div className={`text-xl font-semibold ${fact.tone}`}>{fact.value}</div>
            <div className="mt-1 text-sm leading-5 text-muted">{fact.detail}</div>
          </motion.div>
        ))}
      </div>

      <div className="grid gap-3 border-t border-cyan-200/10 bg-black/18 p-4 lg:grid-cols-3">
        <DecisionRule
          title="Before buying"
          text={qualityScore >= 70 ? "Check valuation, 20/50 EMA trend, latest news and earnings date before adding." : "Do not buy yet; first improve data quality and confirm live prices."}
          tone="text-profit"
        />
        <DecisionRule
          title="Before holding"
          text={data.totalPnlPct >= 0 ? "Hold winners only while thesis, trend and allocation remain inside plan." : "Hold losers only if thesis is intact and downside is capped."}
          tone="text-amber"
        />
        <DecisionRule
          title="Before selling"
          text={highRiskCount || reduceCount ? "Trim in phases when risk persists; avoid panic exits from one weak session." : "No forced sell signal; review only if thesis or position size breaks."}
          tone="text-loss"
        />
      </div>

      <div className="border-t border-cyan-200/10 bg-cyan-200/[0.035] p-4 text-sm leading-6 text-cyan-50/72">
        Cash buffer is shown only when broker/import data confirms it. Current confirmed cash ratio: {cashPct.toFixed(1)}%.
      </div>
    </Card>
  );
}

function DecisionRule({ title, text, tone }: { title: string; text: string; tone: string }) {
  return (
    <div className="rounded-md border border-cyan-200/12 bg-black/24 p-3">
      <div className={`mb-2 text-sm font-semibold ${tone}`}>{title}</div>
      <p className="text-sm leading-5 text-muted">{text}</p>
    </div>
  );
}

function MarketPulseFx() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <div className="market-grid" />
      <div className="market-laser market-laser-a" />
      <div className="market-laser market-laser-b" />
    </div>
  );
}

function OpenAiConfigPanel({
  settings,
  apiKey,
  provider,
  model,
  message,
  error,
  isValidated,
  isSaving,
  onApiKeyChange,
  onProviderChange,
  onModelChange,
  onSave,
  onDelete,
  onClose
}: {
  settings?: OpenAiSettings;
  apiKey: string;
  provider: AiProvider;
  model: string;
  message: string | null;
  error: string | null;
  isValidated: boolean;
  isSaving: boolean;
  onApiKeyChange: (value: string) => void;
  onProviderChange: (value: AiProvider) => void;
  onModelChange: (value: string) => void;
  onSave: () => Promise<void>;
  onDelete: () => Promise<void>;
  onClose: () => void;
}) {
  const geminiModelOptions = GEMINI_MODEL_OPTIONS.some((option) => option.value === model)
    ? GEMINI_MODEL_OPTIONS
    : [
        ...GEMINI_MODEL_OPTIONS,
        {
          value: model,
          label: `${model} (Saved custom)`,
          detail: "This model was already saved. Select the recommended model if this one fails."
        }
      ];
  const hasSavedKey = Boolean(settings?.configured);
  const connectedProvider = settings?.provider ?? provider;
  const connectedLabel = providerLabel(connectedProvider);
  const selectedModelDetail =
    geminiModelOptions.find((option) => option.value === model)?.detail ??
    "Use the recommended model unless Google AI Studio says a specific model is unavailable for your key.";
  const phase = isSaving ? "validating" : isValidated ? "verified" : error ? "error" : "ready";
  const phaseCopy = {
    ready: {
      label: "Ready for validation",
      title: hasSavedKey ? "Saved key found. Validate before showing success." : "Drop in a key. I will prove it works.",
      detail: hasSavedKey
        ? `A ${connectedLabel} key is saved on the server, but this screen will only show success after a fresh live validation.`
        : `Paste your ${providerLabel(provider)} key and run a live provider test before analytics unlocks.`,
      tone: "cyan"
    },
    validating: {
      label: "Neural handshake running",
      title: "Testing the provider now",
      detail: "The backend is sending a live validation request. No success state appears until this returns clean.",
      tone: "violet"
    },
    verified: {
      label: "Live key verified",
      title: `${providerLabel(provider)} accepted the test request`,
      detail: message ?? "Connection verified. This key is ready for AI-powered portfolio analytics.",
      tone: "emerald"
    },
    error: {
      label: "Validation failed",
      title: "The provider rejected this setup",
      detail: error ?? "Check the key, model, provider quota, and network access before trying again.",
      tone: "rose"
    }
  }[phase];
  const canValidate = apiKey.trim().length >= 20 && !isSaving;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#010308]/90 px-3 py-4 backdrop-blur-2xl sm:items-center sm:px-6">
      <motion.div
        initial={{ opacity: 0, y: 34, scale: 0.94, rotateX: -8 }}
        animate={{ opacity: 1, y: 0, scale: 1, rotateX: 0 }}
        exit={{ opacity: 0, y: 20, scale: 0.96 }}
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        className={`ai-lab-shell ai-lab-${phase} my-auto w-full max-w-6xl overflow-hidden rounded-lg border border-white/[0.12] bg-[#05070d] shadow-[0_36px_130px_rgba(0,0,0,0.72)]`}
      >
        <div className="ai-lab-noise" />
        <div className="relative z-10 grid lg:grid-cols-[1.03fr_0.97fr]">
          <section className="ai-lab-hero relative min-h-[520px] overflow-hidden border-b border-white/10 p-5 sm:p-7 lg:border-b-0 lg:border-r lg:border-white/10">
            <div className="ai-lab-grid" />
            <div className="ai-lab-comet ai-lab-comet-a" />
            <div className="ai-lab-comet ai-lab-comet-b" />
            <div className="relative z-10 flex min-h-full flex-col">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-cyan-200/24 bg-cyan-300/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.26em] text-cyan-50">
                      AI Key Lab
                    </span>
                    <span className="rounded-full border border-white/12 bg-white/[0.055] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-300">
                      {phaseCopy.label}
                    </span>
                  </div>
                  <h2 className="max-w-xl text-3xl font-semibold leading-tight text-white sm:text-4xl">
                    Validate first. Celebrate after.
                  </h2>
                  <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300">
                    This panel no longer trusts old saved state as success. It runs a live provider handshake, then flips into verified mode only after the backend accepts the key.
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Close"
                  onClick={onClose}
                  className="shrink-0 rounded-md border border-white/[0.12] bg-white/[0.06] p-2 text-slate-300 transition hover:border-cyan-200/50 hover:bg-cyan-200/[0.12] hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="flex flex-1 items-center justify-center py-8">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={phase}
                    initial={{ opacity: 0, scale: 0.82, rotate: -8 }}
                    animate={{ opacity: 1, scale: 1, rotate: 0 }}
                    exit={{ opacity: 0, scale: 0.88, rotate: 8 }}
                    transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
                    className={`ai-orbital-core ai-orbital-${phase}`}
                  >
                    <div className="ai-orbital-track ai-orbital-track-a" />
                    <div className="ai-orbital-track ai-orbital-track-b" />
                    <div className="ai-orbital-spark ai-orbital-spark-a" />
                    <div className="ai-orbital-spark ai-orbital-spark-b" />
                    <div className="ai-orbital-spark ai-orbital-spark-c" />
                    <div className="ai-orbital-center">
                      {phase === "verified" ? (
                        <BadgeCheck size={54} />
                      ) : phase === "validating" ? (
                        <ScanLine size={54} />
                      ) : phase === "error" ? (
                        <AlertTriangle size={54} />
                      ) : (
                        <BrainCircuit size={54} />
                      )}
                    </div>
                  </motion.div>
                </AnimatePresence>
              </div>

              <AnimatePresence mode="wait">
                <motion.div
                  key={`${phase}-copy`}
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ duration: 0.28 }}
                  className="rounded-lg border border-white/10 bg-black/[0.28] p-4"
                >
                  <div className={`text-xs font-semibold uppercase tracking-[0.22em] ${
                    phaseCopy.tone === "emerald"
                      ? "text-emerald-100/76"
                      : phaseCopy.tone === "rose"
                        ? "text-rose-100/76"
                        : phaseCopy.tone === "violet"
                          ? "text-violet-100/76"
                          : "text-cyan-100/76"
                  }`}>
                    {phaseCopy.label}
                  </div>
                  <div className="mt-2 text-xl font-semibold text-white">{phaseCopy.title}</div>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{phaseCopy.detail}</p>
                </motion.div>
              </AnimatePresence>
            </div>
          </section>

          <section className="relative overflow-hidden p-5 sm:p-7">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_78%_4%,rgba(99,102,241,0.17),transparent_32%),radial-gradient(circle_at_8%_94%,rgba(34,211,238,0.12),transparent_34%)]" />
            <div className="relative z-10 space-y-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">
                    <CircuitBoard size={15} />
                    Connection console
                  </div>
                  <h3 className="mt-2 text-2xl font-semibold text-white">Configure the AI route</h3>
                </div>
                <div className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${
                  phase === "verified"
                    ? "border-emerald-300/30 bg-emerald-300/12 text-emerald-100"
                    : phase === "validating"
                      ? "border-violet-300/30 bg-violet-300/12 text-violet-100"
                      : phase === "error"
                        ? "border-rose-300/30 bg-rose-300/12 text-rose-100"
                        : "border-cyan-300/24 bg-cyan-300/10 text-cyan-100"
                }`}>
                  {phase}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <AiProviderChoice
                  value="gemini"
                  label="Gemini"
                  detail="Fast free-tier analytics"
                  active={provider === "gemini"}
                  icon={Sparkles}
                  onClick={() => onProviderChange("gemini")}
                />
                <AiProviderChoice
                  value="openai"
                  label="OpenAI"
                  detail="Custom model routing"
                  active={provider === "openai"}
                  icon={Bot}
                  onClick={() => onProviderChange("openai")}
                />
              </div>

              <label className="ai-lab-field block">
                <span className="mb-2 flex items-center justify-between gap-3 text-sm text-slate-300">
                  <span className="flex items-center gap-2"><Fingerprint size={16} /> {providerLabel(provider)} API key</span>
                  <span className="rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-1 text-xs text-slate-400">
                    {hasSavedKey ? `Saved: ${settings?.maskedKey ?? "server key"}` : "No saved key"}
                  </span>
                </span>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-cyan-100/[0.54]" size={18} />
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(event) => onApiKeyChange(event.target.value)}
                    placeholder={provider === "gemini" ? "AIza..." : "sk-..."}
                    className="ai-config-input w-full rounded-lg border border-white/[0.12] bg-black/[0.38] py-3 pl-10 pr-3 text-sm text-foreground outline-none transition placeholder:text-slate-600 focus:border-cyan-200/70 focus:ring-2 focus:ring-cyan-300/20"
                  />
                </div>
              </label>

              {provider === "gemini" ? (
                <label className="ai-lab-field block">
                  <span className="mb-2 flex items-center gap-2 text-sm text-slate-300"><Atom size={16} /> Gemini model</span>
                  <select
                    value={model}
                    onChange={(event) => onModelChange(event.target.value)}
                    className="ai-config-input w-full rounded-lg border border-white/[0.12] bg-black/[0.38] px-3 py-3 text-sm text-foreground outline-none transition focus:border-cyan-200/70 focus:ring-2 focus:ring-cyan-300/20"
                  >
                    {geminiModelOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label} {option.value === RECOMMENDED_GEMINI_MODEL ? "(Recommended)" : ""}
                      </option>
                    ))}
                  </select>
                  <div className="mt-3 rounded-lg border border-cyan-200/14 bg-cyan-300/[0.07] p-4 text-xs leading-5 text-cyan-50/76">
                    {selectedModelDetail}
                  </div>
                </label>
              ) : (
                <label className="ai-lab-field block">
                  <span className="mb-2 flex items-center gap-2 text-sm text-slate-300"><Atom size={16} /> OpenAI model</span>
                  <input
                    type="text"
                    value={model}
                    onChange={(event) => onModelChange(event.target.value)}
                    className="ai-config-input w-full rounded-lg border border-white/[0.12] bg-black/[0.38] px-3 py-3 text-sm text-foreground outline-none transition focus:border-cyan-200/70 focus:ring-2 focus:ring-cyan-300/20"
                  />
                </label>
              )}

              <div className="grid gap-3 sm:grid-cols-3">
                <AiConnectionStat icon={RadioTower} label="Live test" value={phase === "verified" ? "Passed" : phase === "validating" ? "Running" : "Required"} tone={phase === "verified" ? "live" : "waiting"} />
                <AiConnectionStat icon={LockKeyhole} label="Vault" value={hasSavedKey ? "Saved" : "Empty"} tone={hasSavedKey ? "saved" : "waiting"} />
                <AiConnectionStat icon={Rocket} label="AI engine" value={phase === "verified" ? "Unlocked" : "Locked"} tone={phase === "verified" ? "live" : "waiting"} />
              </div>

              <div className="rounded-lg border border-white/10 bg-black/[0.26] p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-300/80">
                    <Orbit size={15} />
                    Validation route
                  </span>
                  <span className={`rounded-full px-2.5 py-1 text-xs ${
                    phase === "verified"
                      ? "bg-emerald-300/14 text-emerald-100"
                      : phase === "validating"
                        ? "bg-violet-300/14 text-violet-100"
                        : phase === "error"
                          ? "bg-rose-300/14 text-rose-100"
                          : "bg-cyan-300/10 text-cyan-100"
                  }`}>
                    {phase === "verified" ? "Provider accepted test" : phase === "validating" ? "Testing key" : phase === "error" ? "Fix and retry" : "Awaiting validation"}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-black/[0.5]">
                  <motion.div
                    key={phase}
                    initial={{ width: 0 }}
                    animate={{ width: phase === "verified" ? "100%" : phase === "validating" ? "68%" : phase === "error" ? "24%" : "12%" }}
                    transition={{ duration: 0.7, ease: "easeOut" }}
                    className={`h-2 rounded-full ${
                      phase === "verified"
                        ? "bg-gradient-to-r from-emerald-300 via-cyan-200 to-emerald-300"
                        : phase === "error"
                          ? "bg-gradient-to-r from-rose-400 via-orange-300 to-rose-400"
                          : "bg-gradient-to-r from-cyan-300 via-violet-300 to-cyan-300"
                    }`}
                  />
                </div>
              </div>

              {message && !isValidated ? <div className="rounded-md border border-cyan-200/20 bg-cyan-300/10 p-3 text-sm leading-5 text-cyan-50">{message}</div> : null}

              <div className="flex flex-col gap-3 border-t border-white/10 pt-5 sm:flex-row sm:items-center sm:justify-between">
                {settings?.configured ? (
                  <Button type="button" variant="ghost" onClick={onDelete} disabled={isSaving} className="border-loss/30 text-loss hover:bg-loss/10">
                    Remove Key
                  </Button>
                ) : (
                  <span className="text-xs leading-5 text-slate-500">A live provider request runs before the key is saved.</span>
                )}
                <Button
                  type="button"
                  onClick={onSave}
                  disabled={!canValidate}
                  className="h-11 bg-cyan-300 px-4 text-black shadow-[0_0_34px_rgba(34,211,238,0.28)] hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSaving ? <ScanLine size={18} className="animate-pulse" /> : <Zap size={18} />}
                  {isSaving ? "Validating live key" : `Validate & Save ${providerLabel(provider)} Key`}
                </Button>
              </div>
            </div>
          </section>
        </div>
      </motion.div>
    </div>
  );
}

function AiProviderChoice({
  label,
  detail,
  active,
  icon: Icon,
  onClick
}: {
  value: AiProvider;
  label: string;
  detail: string;
  active: boolean;
  icon: typeof Bot;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group rounded-lg border p-4 text-left transition ${
        active
          ? "border-cyan-200/60 bg-cyan-300/12 shadow-[0_0_30px_rgba(34,211,238,0.15)]"
          : "border-white/10 bg-white/[0.035] hover:border-white/[0.22] hover:bg-white/[0.065]"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className={`flex h-11 w-11 items-center justify-center rounded-lg border ${
          active ? "border-cyan-100/40 bg-cyan-200/[0.16] text-cyan-50" : "border-white/10 bg-black/[0.24] text-slate-300"
        }`}>
          <Icon size={21} />
        </span>
        <span className={`h-3 w-3 rounded-full ${active ? "bg-cyan-200 shadow-[0_0_18px_rgba(103,232,249,0.8)]" : "bg-slate-700"}`} />
      </div>
      <div className="mt-4 text-base font-semibold text-white">{label}</div>
      <div className="mt-1 text-sm text-slate-400">{detail}</div>
    </button>
  );
}

function AiConnectionStat({
  icon: Icon,
  label,
  value,
  tone
}: {
  icon: typeof Bot;
  label: string;
  value: string;
  tone: "live" | "waiting" | "saved";
}) {
  return (
    <div className={`rounded-lg border p-3 ${
      tone === "live"
        ? "border-emerald-200/[0.18] bg-emerald-300/[0.06]"
        : tone === "saved"
          ? "border-cyan-200/[0.18] bg-cyan-300/[0.055]"
          : "border-amber/[0.16] bg-amber/[0.04]"
    }`}>
      <Icon className={tone === "live" ? "text-emerald-100/74" : tone === "saved" ? "text-cyan-100/74" : "text-amber/70"} size={18} />
      <div className={`mt-3 text-xs uppercase tracking-[0.18em] ${tone === "live" ? "text-emerald-100/56" : tone === "saved" ? "text-cyan-100/56" : "text-amber/62"}`}>{label}</div>
      <div className="mt-2 truncate text-sm font-semibold text-foreground">{value}</div>
    </div>
  );
}

function PortfolioAiAnalysisView({
  analytics,
  settings,
  insight,
  error,
  isGenerating,
  onGenerate,
  onConfigure
}: {
  analytics?: PortfolioAnalytics;
  settings?: OpenAiSettings;
  insight: AiAnalyticsInsight | null;
  error: string | null;
  isGenerating: boolean;
  onGenerate: () => Promise<void>;
  onConfigure: () => void;
}) {
  const decisionRows = buildHoldingDecisionRows(analytics);
  const addCount = decisionRows.filter((row) => row.action === "Add").length;
  const holdCount = decisionRows.filter((row) => row.action === "Hold").length;
  const reviewCount = decisionRows.filter((row) => row.action === "Review").length;
  const sanityIssueCount = analytics?.sanityChecks.filter((check) => check.status !== "pass").length ?? 0;
  const isReady = Boolean(settings?.configured && analytics?.companies.length);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!isGenerating) {
      setElapsedSeconds(0);
      return;
    }
    setElapsedSeconds(0);
    const timer = window.setInterval(() => {
      setElapsedSeconds((current) => current + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isGenerating]);

  return (
    <div className="overflow-hidden rounded-lg border border-violet-200/16 bg-[#100d18] shadow-[0_28px_90px_rgba(139,92,246,0.16)]">
      <div className="border-b border-violet-200/14 bg-[radial-gradient(circle_at_14%_0%,rgba(167,139,250,0.25),transparent_34%),linear-gradient(135deg,rgba(67,56,202,0.32),rgba(16,13,24,0.96))] p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="mb-2 flex items-center gap-2 text-violet-100">
              <Bot size={18} />
              AI Analysis
            </div>
            <h2 className="text-2xl font-semibold tracking-normal">Deep portfolio insight from your holdings</h2>
            <p className="mt-2 text-sm leading-6 text-violet-50/70">
              Gemini reads the backend company analytics, decision signals and sanity checks for your current portfolio only, then turns them into practical buy, hold, review and risk-control guidance.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="ghost" onClick={onConfigure}>
              <KeyRound size={18} />
              AI Config
            </Button>
            <Button type="button" onClick={onGenerate} disabled={isGenerating || !isReady}>
              <Sparkles size={18} className={isGenerating ? "animate-pulse" : ""} />
              {isGenerating ? "Analyzing" : "Analyze with AI"}
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-3 border-b border-violet-200/10 bg-black/18 p-4 md:grid-cols-2 xl:grid-cols-4">
        <AnalyticsHeroTile
          icon={<KeyRound size={18} />}
          label="Provider"
          value={settings?.configured ? providerLabel(settings.provider) : "Not set"}
          detail={settings?.configured ? `${settings.maskedKey ?? "saved key"} · ${settings.model}` : "Add Gemini key in AI Config"}
          tone="sky"
        />
        <AnalyticsHeroTile
          icon={<Database size={18} />}
          label="Data Quality"
          value={analytics ? `${analytics.dataQualityScore}/100` : "Loading"}
          detail={analytics ? `Daily cache ${formatShortDateTime(analytics.generatedAt)}` : "Waiting for analytics"}
          tone="teal"
        />
        <AnalyticsHeroTile
          icon={<Target size={18} />}
          label="Signals"
          value={`${addCount}/${holdCount}/${reviewCount}`}
          detail="Add, hold, review"
          tone="green"
        />
        <AnalyticsHeroTile
          icon={<ShieldCheck size={18} />}
          label="Sanity"
          value={sanityIssueCount ? `${sanityIssueCount} watch` : "Passed"}
          detail="Coverage, score and data checks"
          tone="amber"
        />
      </div>

      <div className="grid gap-4 p-4">
        {!settings?.configured ? (
          <div className="rounded-md border border-amber/20 bg-amber/10 p-4 text-sm leading-6 text-amber/90">
            Gemini is not configured yet. Open AI Config and save your Gemini API key. The recommended free-tier model is gemini-3.5-flash.
          </div>
        ) : null}

        {analytics && analytics.companies.length === 0 ? (
          <div className="rounded-md border border-amber/20 bg-amber/10 p-4 text-sm leading-6 text-amber/90">
            No holdings are available for AI analysis. Sync Zerodha or import your portfolio first.
          </div>
        ) : null}

        {error ? (
          <div className="rounded-md border border-loss/20 bg-loss/10 p-4 text-sm leading-6 text-loss">
            {error}
          </div>
        ) : null}

        {isGenerating ? (
          <AiAnalysisProgress
            elapsedSeconds={elapsedSeconds}
            holdingsCount={analytics?.companies.length ?? 0}
            provider={settings?.provider ?? "gemini"}
            model={settings?.model ?? RECOMMENDED_GEMINI_MODEL}
          />
        ) : insight ? (
          <div className="rounded-md border border-profit/18 bg-profit/10 p-4 text-sm leading-6 text-profit">
            AI analysis completed. Review the insight sections below before taking any market decision.
          </div>
        ) : null}

        <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-4">
          <div className="mb-2 flex items-center gap-2 text-violet-100">
            <ClipboardList size={18} />
            <h3 className="text-base font-semibold text-foreground">Analysis discipline</h3>
          </div>
          <div className="grid gap-3 text-sm leading-6 text-muted md:grid-cols-3">
            <div>Uses only your saved holdings and backend analytics data.</div>
            <div>Checks fundamentals, valuation, growth, cash flow, concentration and sanity warnings.</div>
            <div>Returns cautious decision support, not guaranteed buy or sell calls.</div>
          </div>
        </section>

        {insight ? (
          <div className="grid gap-3 xl:grid-cols-2">
            <section className="rounded-md border border-violet-200/14 bg-violet-300/[0.07] p-4 xl:col-span-2">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm text-violet-100">
                <span>{insight.generatedAt ? `Generated ${formatShortDateTime(insight.generatedAt)}` : "AI insight"}</span>
                <span>{insight.provider ? `${providerLabel(insight.provider)} · ${insight.model}` : insight.model}</span>
              </div>
              <AiFormattedText text={insight.summary} className="text-sm leading-6 text-foreground/86" />
            </section>
            <AiInsightList title="Buy focus" items={insight.buyFocus} tone="text-profit" />
            <AiInsightList title="Hold focus" items={insight.holdFocus} tone="text-amber" />
            <AiInsightList title="Sell or review focus" items={insight.sellOrReviewFocus} tone="text-loss" />
            <AiInsightList title="Risk controls" items={insight.riskControls} tone="text-sky-200" />
            {insight.dataWarnings.length ? (
              <section className="rounded-md border border-amber/20 bg-amber/10 p-4 xl:col-span-2">
                <h4 className="mb-3 text-base font-semibold text-amber">AI data warnings</h4>
                <div className="grid gap-2 md:grid-cols-2">
                    {insight.dataWarnings.map((item, index) => (
                      <div key={`${item}-${index}`} className="rounded-md border border-amber/15 bg-black/16 p-3 text-sm leading-5 text-amber/90">
                        <AiFormattedText text={item} />
                      </div>
                    ))}
                </div>
              </section>
            ) : null}
          </div>
        ) : (
          <div className="rounded-md border border-white/10 bg-black/24 p-4 text-sm leading-6 text-muted">
            Click Analyze with AI after Gemini is configured. The output will appear here as a portfolio-level consultant note with symbol-specific action areas.
          </div>
        )}
      </div>
    </div>
  );
}

function PortfolioAnalyticsView({
  analytics,
  isLoading,
  onRefresh
}: {
  analytics?: PortfolioAnalytics;
  isLoading: boolean;
  onRefresh: () => Promise<void>;
}) {
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const selectedCompany =
    analytics?.companies.find((company) => company.symbol === selectedSymbol) ?? analytics?.companies[0];
  const strongCount = analytics?.companies.filter((company) => company.overallScore >= 72).length ?? 0;
  const sanityIssueCount = analytics?.sanityChecks.filter((check) => check.status !== "pass").length ?? 0;
  const decisionRows = buildHoldingDecisionRows(analytics);
  const addCount = decisionRows.filter((row) => row.action === "Add").length;
  const holdCount = decisionRows.filter((row) => row.action === "Hold").length;
  const trimCount = decisionRows.filter((row) => row.action === "Review").length;

  useEffect(() => {
    if (!selectedSymbol && analytics?.companies[0]) {
      setSelectedSymbol(analytics.companies[0].symbol);
    }
  }, [analytics?.companies, selectedSymbol]);

  return (
    <div className="overflow-hidden rounded-lg border border-teal-200/14 bg-[#071311] shadow-[0_28px_90px_rgba(20,184,166,0.14)]">
      <div className="border-b border-teal-200/14 bg-[radial-gradient(circle_at_12%_0%,rgba(45,212,191,0.24),transparent_34%),linear-gradient(135deg,rgba(6,78,59,0.32),rgba(7,19,17,0.96))] p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="mb-2 flex items-center gap-2 text-sm text-teal-100">
              <Building2 size={18} />
              Company Analytics
            </div>
            <h2 className="text-2xl font-semibold tracking-normal">Daily business intelligence scan</h2>
            <p className="mt-2 text-sm leading-6 text-teal-50/68">
              Balance-sheet quality, growth, cash-flow strength, valuation position and internet news are combined into a planning view for each holding.
            </p>
          </div>
          <Button type="button" onClick={onRefresh} disabled={isLoading}>
            <RefreshCw size={18} className={isLoading ? "animate-spin" : ""} />
            {isLoading ? "Refreshing" : "Refresh Daily BI"}
          </Button>
        </div>
      </div>

      <div className="grid gap-3 border-b border-teal-200/10 bg-black/16 p-4 md:grid-cols-2 xl:grid-cols-4">
        <AnalyticsHeroTile icon={<Sparkles size={18} />} label="BI Quality" value={analytics ? `${analytics.dataQualityScore}/100` : "Loading"} detail={analytics ? `Next refresh ${formatShortDateTime(analytics.nextRefreshAt)}` : "Fetching providers"} tone="teal" />
        <AnalyticsHeroTile icon={<Building2 size={18} />} label="Companies" value={`${analytics?.companies.length ?? 0}`} detail={analytics ? analytics.modelVersion : "Holdings analyzed"} tone="sky" />
        <AnalyticsHeroTile icon={<CheckCircle2 size={18} />} label="Strong" value={`${strongCount}`} detail="Score 72+" tone="green" />
        <AnalyticsHeroTile icon={<ShieldCheck size={18} />} label="Sanity" value={sanityIssueCount ? `${sanityIssueCount} watch` : "Passed"} detail="Coverage and score checks" tone="amber" />
      </div>

      <DataProvenancePanel analytics={analytics} />

      <div className="p-4">
        {analytics ? (
          <section className="mb-4 rounded-md border border-emerald-200/14 bg-[linear-gradient(135deg,rgba(16,185,129,0.12),rgba(14,165,233,0.08),rgba(7,19,17,0.40))] p-4">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="mb-2 flex items-center gap-2 text-emerald-100">
                  <CircleDollarSign size={18} />
                  <span className="text-sm font-medium text-foreground">Important data</span>
                </div>
                <h3 className="text-xl font-semibold tracking-normal">Buy, hold and review signals</h3>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-emerald-50/68">
                  Focused on your current portfolio holdings only, ranked by fundamentals, valuation position and data quality.
                </p>
              </div>
              <div className="grid w-full grid-cols-3 gap-2 sm:w-auto sm:min-w-[300px]">
                <DecisionCount label="Add" value={addCount} tone="text-profit" />
                <DecisionCount label="Hold" value={holdCount} tone="text-amber" />
                <DecisionCount label="Review" value={trimCount} tone="text-loss" />
              </div>
            </div>

            <div className="grid gap-3 xl:grid-cols-3">
              {decisionRows.slice(0, 6).map((row) => (
                <button
                  key={row.symbol}
                  type="button"
                  onClick={() => setSelectedSymbol(row.symbol)}
                  className={`rounded-md border p-3 text-left transition duration-200 hover:-translate-y-0.5 ${
                    selectedCompany?.symbol === row.symbol
                      ? "border-emerald-200/45 bg-emerald-300/12"
                      : "border-white/10 bg-black/24 hover:border-emerald-200/28"
                  }`}
                >
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium">{row.symbol}</div>
                      <div className="truncate text-xs text-muted">{row.companyName}</div>
                    </div>
                    <span className={`rounded-md border px-2 py-1 text-xs ${decisionBadgeTone(row.action)}`}>
                      {row.action}
                    </span>
                  </div>
                  <div className="mb-3 grid grid-cols-3 gap-2">
                    <DecisionMiniStat label="Score" value={`${row.score}`} tone={scoreTone(row.score)} />
                    <DecisionMiniStat label="Conviction" value={`${row.conviction}`} tone={scoreTone(row.conviction)} />
                    <DecisionMiniStat label="Confidence" value={`${row.confidence}`} tone={scoreTone(row.confidence)} />
                  </div>
                  <div className="text-sm leading-5 text-foreground/82">{row.reason}</div>
                  <div className="mt-3 rounded-md border border-white/10 bg-white/[0.04] p-2 text-xs leading-5 text-muted">
                    {row.entryDiscipline}
                  </div>
                </button>
              ))}
            </div>
          </section>
        ) : null}

        {analytics ? (
          <div className="mb-4 rounded-md border border-teal-200/12 bg-white/[0.045] p-4">
            <div className="mb-2 flex items-center gap-2 text-teal-100">
              <Database size={18} />
              <span className="text-sm font-medium text-foreground">Daily summary</span>
            </div>
            <p className="text-sm leading-6 text-foreground/84">{analytics.summary}</p>
          </div>
        ) : (
          <div className="rounded-md border border-teal-200/12 bg-white/[0.045] p-4 text-sm text-muted">
            Loading company analytics from public finance providers...
          </div>
        )}

        {analytics?.sanityChecks.length ? (
          <section className="mb-4 rounded-md border border-sky-200/12 bg-sky-300/[0.055] p-4">
            <div className="mb-3 flex items-center gap-2 text-sky-100">
              <ShieldCheck size={18} />
              <h3 className="text-base font-semibold text-foreground">Analytics sanity check</h3>
            </div>
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
              {analytics.sanityChecks.map((check) => (
                <div key={check.label} className="rounded-md border border-white/10 bg-black/22 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{check.label}</span>
                    <span className={sanityTone(check.status)}>{check.status}</span>
                  </div>
                  <p className="text-xs leading-5 text-muted">{check.detail}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {selectedCompany ? (
          <div className="grid gap-4 xl:grid-cols-[0.75fr_1.25fr]">
            <section className="rounded-md border border-teal-200/12 bg-white/[0.045] p-4">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h3 className="text-base font-semibold">Company board</h3>
                  <p className="text-sm text-teal-50/55">Ranked by business intelligence score</p>
                </div>
                <Search className="text-teal-100" size={20} />
              </div>
              <div className="space-y-2">
                {analytics?.companies.map((company) => (
                  <button
                    key={company.symbol}
                    type="button"
                    onClick={() => setSelectedSymbol(company.symbol)}
                    className={`w-full rounded-md border p-3 text-left transition hover:-translate-y-0.5 ${
                      selectedCompany.symbol === company.symbol
                        ? "border-teal-200/45 bg-teal-300/12"
                        : "border-teal-200/12 bg-black/20 hover:border-teal-200/28"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-medium">{company.symbol}</div>
                        <div className="truncate text-xs text-muted">{company.companyName}</div>
                      </div>
                      <div className="text-right">
                        <div className={scoreTone(company.overallScore)}>{company.overallScore}</div>
                        <div className="text-xs text-muted">{company.recommendation}</div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </section>

            <section className="rounded-md border border-teal-200/12 bg-white/[0.045] p-4">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="mb-1 text-sm text-teal-50/58">{selectedCompany.sector ?? "Sector unavailable"}</div>
                  <h3 className="text-2xl font-semibold tracking-normal">{selectedCompany.companyName}</h3>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/78">{selectedCompany.businessSummary}</p>
                </div>
                <div className="rounded-md border border-teal-200/14 bg-black/24 px-3 py-2 text-right">
                  <div className="text-xs text-muted">BI score</div>
                  <div className={`text-2xl font-semibold ${scoreTone(selectedCompany.overallScore)}`}>
                    {selectedCompany.overallScore}/100
                  </div>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <CompanyScore label="Balance sheet" value={selectedCompany.balanceSheetScore} />
                <CompanyScore label="Growth" value={selectedCompany.growthScore} />
                <CompanyScore label="Cash flow" value={selectedCompany.cashFlowScore} />
                <CompanyScore label="Valuation" value={selectedCompany.valuationScore} />
              </div>

              <div className="mt-4 rounded-md border border-teal-200/12 bg-black/22 p-4">
                <div className="mb-2 flex items-center gap-2 text-teal-100">
                  <Sparkles size={18} />
                  <span className="text-sm font-medium text-foreground">Planning suggestion</span>
                </div>
                <p className="text-sm leading-6 text-foreground/84">{selectedCompany.planning}</p>
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-2">
                <SignalPanel title="Business strengths" items={selectedCompany.strengths} tone="text-profit" />
                <SignalPanel title="Review concerns" items={selectedCompany.concerns} tone="text-amber" />
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
                <section className="rounded-md border border-teal-200/12 bg-black/22 p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <Database className="text-teal-100" size={18} />
                    <h4 className="text-base font-semibold">Financial snapshot</h4>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {selectedCompany.financials.map((metric) => (
                      <div key={metric.label} className="rounded-md border border-white/10 bg-white/[0.045] p-3">
                        <div className="text-xs text-muted">{metric.label}</div>
                        <div className={`mt-1 text-sm font-semibold ${metricTone(metric.tone)}`}>{metric.value}</div>
                        {metric.detail ? <div className="mt-1 text-xs text-muted">{metric.detail}</div> : null}
                      </div>
                    ))}
                  </div>
                </section>

                <section className="rounded-md border border-teal-200/12 bg-black/22 p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <Newspaper className="text-amber" size={18} />
                    <h4 className="text-base font-semibold">Latest news signals</h4>
                  </div>
                  <div className="space-y-2">
                    {selectedCompany.news.length ? (
                      selectedCompany.news.map((item) => (
                        <a
                          key={`${item.title}-${item.link ?? ""}`}
                          href={item.link ?? "#"}
                          target="_blank"
                          rel="noreferrer"
                          className="block rounded-md border border-white/10 bg-white/[0.045] p-3 transition hover:border-amber/30"
                        >
                          <div className="text-sm font-medium leading-5 text-foreground">{item.title}</div>
                          <div className="mt-1 text-xs text-muted">{item.publisher ?? "Market news"}</div>
                        </a>
                      ))
                    ) : (
                      <div className="rounded-md border border-white/10 bg-white/[0.045] p-3 text-sm text-muted">
                        No provider news was returned for this company.
                      </div>
                    )}
                  </div>
                </section>
              </div>
            </section>
          </div>
        ) : null}

        {analytics?.warnings.length ? (
          <div className="mt-4 rounded-md border border-amber/20 bg-amber/10 p-4">
            <div className="mb-2 text-sm font-medium text-amber">Provider warnings</div>
            <div className="grid gap-2 lg:grid-cols-2">
              {analytics.warnings.map((warning) => (
                <div key={warning} className="text-sm leading-5 text-amber/90">
                  {warning}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function DataProvenancePanel({ analytics }: { analytics?: PortfolioAnalytics }) {
  const profile = buildDataProvenanceProfile(analytics);
  const gateTone =
    profile.analyticsReadiness >= 75 && profile.blockers === 0
      ? "text-profit"
      : profile.analyticsReadiness >= 55
        ? "text-amber"
        : "text-loss";

  return (
    <section className="border-b border-teal-200/10 bg-black/18 p-4">
      <div className="data-pipeline-shell overflow-hidden rounded-lg border border-cyan-200/14 bg-[#061117] p-4">
        <div className="data-pipeline-scan" />
        <div className="relative z-10">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <div className="mb-2 flex items-center gap-2 text-sm text-cyan-100">
                <DatabaseZap size={18} />
                Data provenance and validation
              </div>
              <h3 className="text-xl font-semibold tracking-normal">What data enters analytics, and how clean is it?</h3>
              <p className="mt-2 text-sm leading-6 text-cyan-50/70">
                Holdings, market feeds, fundamentals and news are fetched, sanitized, cross-checked, scored by sanity checks, then passed into analytics only with warnings and coverage penalties attached.
              </p>
            </div>
            <div className="rounded-lg border border-white/10 bg-black/28 p-3 text-right">
              <div className="text-xs uppercase tracking-[0.18em] text-muted">Analytics gate</div>
              <div className={`mt-1 text-2xl font-semibold ${gateTone}`}>{profile.analyticsReadiness}%</div>
              <div className="mt-1 text-xs text-muted">
                {profile.blockers ? `${profile.blockers} blocker(s)` : "Ready with warnings"}
              </div>
            </div>
          </div>

          <div className="grid gap-3 xl:grid-cols-[0.95fr_1.05fr]">
            <div className="rounded-lg border border-white/10 bg-black/22 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <RadioTower className="text-cyan-100" size={18} />
                  Source coverage
                </div>
                <span className="text-xs text-muted">{profile.companyCount} holding(s)</span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {profile.sources.map((source, index) => (
                  <motion.div
                    key={source.label}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.28, delay: index * 0.04 }}
                    className="rounded-md border border-white/10 bg-white/[0.04] p-3"
                  >
                    <div className="mb-3 flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold">{source.label}</div>
                        <div className="mt-1 text-xs leading-5 text-muted">{source.detail}</div>
                      </div>
                      <span className={source.percent >= 70 ? "text-profit" : source.percent >= 35 ? "text-amber" : "text-loss"}>
                        {source.percent}%
                      </span>
                    </div>
                    <ProgressRail percent={source.percent} tone={source.tone} />
                  </motion.div>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-black/22 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <CircuitBoard className="text-teal-100" size={18} />
                  Processing pipeline
                </div>
                <span className="text-xs text-muted">before analytics</span>
              </div>
              <div className="space-y-3">
                {profile.stages.map((stage, index) => (
                  <motion.div
                    key={stage.label}
                    initial={{ opacity: 0, x: 16 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.28, delay: index * 0.05 }}
                    className="grid gap-3 rounded-md border border-white/10 bg-white/[0.035] p-3 sm:grid-cols-[150px_1fr_58px]"
                  >
                    <div>
                      <div className="text-sm font-semibold">{stage.label}</div>
                      <div className="mt-1 text-xs text-muted">{stage.detail}</div>
                    </div>
                    <div className="self-center">
                      <ProgressRail percent={stage.percent} tone={stage.tone} />
                    </div>
                    <div className={stage.percent >= 75 ? "text-right text-profit" : stage.percent >= 50 ? "text-right text-amber" : "text-right text-loss"}>
                      {stage.percent}%
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-3 grid gap-3 xl:grid-cols-[1fr_0.8fr]">
            <div className="rounded-lg border border-white/10 bg-black/22 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium">
                <ShieldCheck className="text-profit" size={18} />
                Sanity and validation checks
              </div>
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {profile.checks.map((check) => (
                  <div key={check.label} className="rounded-md border border-white/10 bg-white/[0.035] p-3">
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{check.label}</span>
                      <span className={sanityTone(check.status)}>{check.status}</span>
                    </div>
                    <p className="text-xs leading-5 text-muted">{check.detail}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-black/22 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium">
                <AlertTriangle className={profile.blockers ? "text-loss" : "text-amber"} size={18} />
                Data issues before analytics
              </div>
              <div className="space-y-2">
                {profile.issues.length ? (
                  profile.issues.slice(0, 5).map((issue, index) => (
                    <div key={`${issue}-${index}`} className="rounded-md border border-amber/16 bg-amber/10 p-2 text-xs leading-5 text-amber/90">
                      {issue}
                    </div>
                  ))
                ) : (
                  <div className="rounded-md border border-profit/16 bg-profit/10 p-3 text-sm leading-5 text-profit">
                    No provider warning was returned in the latest analytics run.
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function ProgressRail({ percent, tone }: { percent: number; tone: "teal" | "cyan" | "green" | "amber" | "rose" | "violet" }) {
  const gradient =
    tone === "green"
      ? "from-emerald-300 via-teal-200 to-emerald-300"
      : tone === "amber"
        ? "from-amber via-orange-300 to-amber"
        : tone === "rose"
          ? "from-rose-400 via-orange-300 to-rose-400"
          : tone === "violet"
            ? "from-violet-300 via-cyan-200 to-violet-300"
            : "from-cyan-300 via-teal-200 to-cyan-300";
  return (
    <div className="h-2 overflow-hidden rounded-full bg-black/50">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        transition={{ duration: 0.75, ease: "easeOut" }}
        className={`h-2 rounded-full bg-gradient-to-r ${gradient}`}
      />
    </div>
  );
}

function StockDiscoveryView({
  discovery,
  isLoading,
  onRefresh
}: {
  discovery?: StockDiscovery;
  isLoading: boolean;
  onRefresh: () => Promise<void>;
}) {
  const [riskProfile, setRiskProfile] = useState<InvestorRiskProfile>("balanced");
  const [horizon, setHorizon] = useState<InvestorHorizon>("long");
  const [marketCapFilter, setMarketCapFilter] = useState<MarketCapFilter>("all");
  const [capital, setCapital] = useState(100000);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const candidates = useMemo(() => discovery?.candidates ?? [], [discovery?.candidates]);
  const selected = candidates.find((item) => item.symbol === selectedSymbol) ?? candidates[0];
  const profile = getInvestorProfileConfig(riskProfile, horizon);
  const filtered = candidates.filter(
    (candidate) =>
      profile.allows(candidate.riskLevel) &&
      (marketCapFilter === "all" || candidate.marketCapCategory === marketCapFilter)
  );
  const validity = getDiscoveryValidity(discovery?.validUntil);
  const capCounts = {
    "Large Cap": candidates.filter((item) => item.marketCapCategory === "Large Cap").length,
    "Mid Cap": candidates.filter((item) => item.marketCapCategory === "Mid Cap").length,
    "Small Cap": candidates.filter((item) => item.marketCapCategory === "Small Cap").length,
  };

  useEffect(() => {
    const saved = window.localStorage.getItem("investor-profile");
    if (!saved) {
      return;
    }
    try {
      const parsed = JSON.parse(saved) as {
        riskProfile?: InvestorRiskProfile;
        horizon?: InvestorHorizon;
        capital?: number;
      };
      if (parsed.riskProfile) setRiskProfile(parsed.riskProfile);
      if (parsed.horizon) setHorizon(parsed.horizon);
      if (parsed.capital) setCapital(parsed.capital);
    } catch {
      // Ignore invalid local profile; user can reset it from the controls.
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("investor-profile", JSON.stringify({ riskProfile, horizon, capital }));
  }, [capital, horizon, riskProfile]);

  useEffect(() => {
    if (!selectedSymbol && candidates[0]) {
      setSelectedSymbol(candidates[0].symbol);
    }
  }, [candidates, selectedSymbol]);

  return (
    <div className="overflow-hidden rounded-lg border border-sky-200/14 bg-[#07111d] shadow-[0_28px_90px_rgba(14,165,233,0.16)]">
      <div className="relative border-b border-sky-200/14 bg-[radial-gradient(circle_at_10%_0%,rgba(14,165,233,0.28),transparent_34%),linear-gradient(135deg,rgba(12,74,110,0.42),rgba(7,17,29,0.96))] p-4">
        <div className="market-scanline" />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="mb-2 flex items-center gap-2 text-sm text-sky-100">
              <Search size={18} />
              New Share Discovery
            </div>
            <h2 className="text-2xl font-semibold tracking-normal">Find new shares beyond your current portfolio</h2>
            <p className="mt-2 text-sm leading-6 text-sky-50/70">
              Professional discovery scans large, mid and small-cap NSE candidates, removes stocks you already hold, scores fundamentals, valuation, quality, technical context and AI analysis, then expires the recommendation after 2 days.
            </p>
          </div>
          <Button type="button" onClick={onRefresh} disabled={isLoading}>
            <RefreshCw size={18} className={isLoading ? "animate-spin" : ""} />
            {isLoading ? "Scanning" : "Scan Market"}
          </Button>
        </div>
      </div>

      <div className="grid gap-3 border-b border-sky-200/10 bg-black/16 p-4 md:grid-cols-2 xl:grid-cols-5">
        <ProfileControl
          label="Risk profile"
          value={riskProfile}
          options={[
            ["conservative", "Conservative"],
            ["balanced", "Balanced"],
            ["aggressive", "Aggressive"]
          ]}
          onChange={(value) => setRiskProfile(value as InvestorRiskProfile)}
        />
        <ProfileControl
          label="Time horizon"
          value={horizon}
          options={[
            ["short", "Short"],
            ["swing", "Swing"],
            ["long", "Long term"]
          ]}
          onChange={(value) => setHorizon(value as InvestorHorizon)}
        />
        <ProfileControl
          label="Market cap"
          value={marketCapFilter}
          options={[
            ["all", "All caps"],
            ["Large Cap", `Large (${capCounts["Large Cap"]})`],
            ["Mid Cap", `Mid (${capCounts["Mid Cap"]})`],
            ["Small Cap", `Small (${capCounts["Small Cap"]})`]
          ]}
          onChange={(value) => setMarketCapFilter(value as MarketCapFilter)}
        />
        <label className="rounded-md border border-sky-200/12 bg-white/[0.045] p-3">
          <span className="mb-2 block text-xs text-muted">Deployable capital</span>
          <input
            type="number"
            min={0}
            step={5000}
            value={capital}
            onChange={(event) => setCapital(Number(event.target.value))}
            className="w-full rounded-md border border-white/10 bg-black/24 px-3 py-2 text-sm outline-none focus:border-sky-200/60"
          />
        </label>
        <div className="rounded-md border border-sky-200/12 bg-white/[0.045] p-3">
          <div className="text-xs text-muted">Recommendation validity</div>
          <div className={`mt-2 text-sm leading-5 ${validity.expired ? "text-loss" : "text-sky-50/80"}`}>
            {validity.label}
          </div>
        </div>
      </div>

      <div className="grid gap-3 border-b border-sky-200/10 bg-black/22 p-4 md:grid-cols-2 xl:grid-cols-4">
        <DiscoveryKpi label="Universe" value={discovery?.universe ?? "Loading"} detail={`${candidates.length} shortlisted ideas`} icon={<Database size={18} />} />
        <DiscoveryKpi label="Large / Mid / Small" value={`${capCounts["Large Cap"]}/${capCounts["Mid Cap"]}/${capCounts["Small Cap"]}`} detail="Balanced cap buckets" icon={<PieChart size={18} />} />
        <DiscoveryKpi label="Advisory expiry" value={validity.shortLabel} detail="Refresh after expiry for new shares" icon={<CalendarClock size={18} />} />
        <DiscoveryKpi label="Profile rule" value={profile.label} detail={profile.rule} icon={<ShieldCheck size={18} />} />
      </div>

      <div className="grid gap-4 p-4 xl:grid-cols-[0.95fr_1.05fr]">
        <section className="rounded-md border border-sky-200/12 bg-white/[0.045] p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">Ranked candidates</h3>
              <p className="text-sm text-sky-50/58">
                {filtered.length}/{candidates.length} match your profile
              </p>
            </div>
            <Sparkles className="text-sky-200" size={20} />
          </div>
          <div className="space-y-2">
            {(filtered.length ? filtered : candidates).map((candidate, index) => (
              <motion.button
                key={candidate.symbol}
                type="button"
                initial={{ opacity: 0, x: -14 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.035, duration: 0.22 }}
                onClick={() => setSelectedSymbol(candidate.symbol)}
                className={`holo-card w-full rounded-md border p-3 text-left transition hover:-translate-y-0.5 ${
                  selected?.symbol === candidate.symbol
                    ? "border-sky-200/45 bg-sky-300/12"
                    : "border-sky-200/12 bg-black/22 hover:border-sky-200/28"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium">{candidate.symbol}</div>
                    <div className="truncate text-xs text-muted">{candidate.companyName}</div>
                  </div>
                  <div className="text-right">
                    <div className={scoreTone(candidate.discoveryScore)}>{candidate.discoveryScore}</div>
                    <div className="text-xs text-muted">{candidate.conviction}</div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <span className="rounded-md border border-cyan-200/16 bg-cyan-300/10 px-2 py-1 text-cyan-100">
                    {candidate.marketCapCategory}
                  </span>
                  <span className={`rounded-md border px-2 py-1 ${riskPill(candidate.riskLevel)}`}>{candidate.riskLevel} risk</span>
                  <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-muted">
                    Data {candidate.dataQualityScore}/100
                  </span>
                  <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-muted">
                    {candidate.sector ?? "Sector N/A"}
                  </span>
                </div>
              </motion.button>
            ))}
          </div>
        </section>

        <section className="rounded-md border border-sky-200/12 bg-white/[0.045] p-4">
          {selected ? (
            <>
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-sm text-sky-50/58">{selected.marketCapCategory} · {selected.sector ?? "Sector unavailable"}</div>
                  <h3 className="text-2xl font-semibold">{selected.symbol}</h3>
                  <p className="text-sm text-muted">{selected.companyName}</p>
                </div>
                <span className={`rounded-md border px-2 py-1 text-sm ${riskPill(selected.riskLevel)}`}>
                  {selected.recommendation}
                </span>
              </div>

              <div className="mb-4 grid gap-3 sm:grid-cols-4">
                <ReportFact label="Discovery" value={`${selected.discoveryScore}/100`} tone={scoreTone(selected.discoveryScore)} />
                <ReportFact label="Conviction" value={selected.conviction} />
                <ReportFact label="Risk" value={selected.riskLevel} tone={selected.riskLevel === "High" ? "text-loss" : selected.riskLevel === "Medium" ? "text-amber" : "text-profit"} />
                <ReportFact label="Starter size" value={formatCurrency(recommendedStarterSize(capital, selected.riskLevel, riskProfile))} />
              </div>

              <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <AdvancedDiscoveryScore label="Fundamental" value={selected.fundamentalScore} />
                <AdvancedDiscoveryScore label="Technical" value={selected.technicalScore} />
                <AdvancedDiscoveryScore label="Valuation" value={selected.valuationScore} />
                <AdvancedDiscoveryScore label="Quality" value={selected.qualityScore} />
              </div>

              <div className="rounded-md border border-sky-200/12 bg-black/24 p-4">
                <div className="mb-2 text-sm font-semibold text-sky-100">AI + research decision view</div>
                <p className="text-sm leading-6 text-foreground/84">{selected.researchView}</p>
              </div>

              {selected.aiView ? (
                <div className="mt-4 rounded-md border border-violet-200/18 bg-violet-300/[0.08] p-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-violet-100">
                    <Bot size={18} />
                    AI company analysis
                  </div>
                  <p className="text-sm leading-6 text-foreground/84">{selected.aiView}</p>
                </div>
              ) : (
                <div className="mt-4 rounded-md border border-violet-200/12 bg-black/20 p-3 text-sm leading-6 text-muted">
                  AI company analysis appears here after Gemini/OpenAI is configured. Deterministic research scoring is still available above.
                </div>
              )}

              <div className="mt-4 grid gap-3 xl:grid-cols-2">
                <DiscoveryList title="Why consider buying" items={selected.whyBuy} tone="text-profit" />
                <DiscoveryList title="Company potential" items={selected.companyPotential} tone="text-sky-200" />
                <DiscoveryList title="Risks" items={selected.risks} tone="text-loss" />
                <DiscoveryList title="Verify before buying" items={selected.verificationTriggers} tone="text-amber" />
              </div>

              <div className="mt-4 rounded-md border border-amber/20 bg-amber/10 p-3 text-sm leading-6 text-amber/90">
                {selected.entryDiscipline}
              </div>
            </>
          ) : (
            <div className="rounded-md border border-amber/20 bg-amber/10 p-4 text-sm text-amber">
              No discovery candidates are available yet. Click Scan Market after your backend is running.
            </div>
          )}
        </section>
      </div>

      {discovery?.warnings.length ? (
        <div className="border-t border-sky-200/10 bg-black/18 p-4">
          <div className="grid gap-2 lg:grid-cols-2">
            {discovery.warnings.slice(0, 6).map((warning) => (
              <div key={warning} className="rounded-md border border-amber/15 bg-amber/10 p-3 text-sm leading-5 text-amber/90">
                {warning}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ProfileControl({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: Array<[string, string]>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="rounded-md border border-sky-200/12 bg-white/[0.045] p-3">
      <span className="mb-2 block text-xs text-muted">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-white/10 bg-black/24 px-3 py-2 text-sm outline-none focus:border-sky-200/60"
      >
        {options.map(([id, optionLabel]) => (
          <option key={id} value={id}>
            {optionLabel}
          </option>
        ))}
      </select>
    </label>
  );
}

function DiscoveryList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <div className="rounded-md border border-sky-200/12 bg-black/22 p-3">
      <div className={`mb-2 text-sm font-semibold ${tone}`}>{title}</div>
      <div className="space-y-2">
        {items.map((item, index) => (
          <div key={`${item}-${index}`} className="text-sm leading-5 text-muted">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function DiscoveryKpi({ label, value, detail, icon }: { label: string; value: string; detail: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-md border border-sky-200/12 bg-white/[0.045] p-3">
      <div className="mb-3 flex items-center justify-between gap-3 text-sky-100">
        <span className="text-xs uppercase tracking-[0.18em] text-muted">{label}</span>
        {icon}
      </div>
      <div className="truncate text-lg font-semibold text-foreground">{value}</div>
      <div className="mt-1 text-xs leading-5 text-muted">{detail}</div>
    </div>
  );
}

function AdvancedDiscoveryScore({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-sky-200/12 bg-black/22 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs text-muted">{label}</span>
        <span className={scoreTone(value)}>{value}</span>
      </div>
      <ProgressRail percent={value} tone={value >= 72 ? "green" : value >= 52 ? "amber" : "rose"} />
    </div>
  );
}

function PortfolioRisk({
  data,
  intelligence
}: {
  data: PortfolioSummary;
  intelligence?: PortfolioIntelligence;
}) {
  const [stressPct, setStressPct] = useState(-12);
  const [selectedSymbol, setSelectedSymbol] = useState(data.holdings[0]?.symbol ?? "");
  const topHoldings = [...data.holdings].sort((a, b) => b.allocationPct - a.allocationPct);
  const alerts = intelligence?.alerts.length ? intelligence.alerts : buildFallbackAlerts(data);
  const recommendationMap = new Map((intelligence?.recommendations ?? []).map((item) => [item.symbol, item]));
  const selectedHolding = data.holdings.find((holding) => holding.symbol === selectedSymbol) ?? topHoldings[0];
  const highRiskCount = alerts.filter((alert) => alert.severity === "high").length;
  const heavySectors = data.sectorAllocation.filter((sector) => sector.percentage >= 25).length;
  const topThreeAllocation = topHoldings.slice(0, 3).reduce((sum, holding) => sum + holding.allocationPct, 0);
  const projectedStressLoss = data.portfolioValue * (Math.abs(stressPct) / 100);
  const riskLoad = Math.min(100, Math.round((100 - data.healthScore) * 0.44 + topThreeAllocation * 0.42 + highRiskCount * 10 + heavySectors * 8));
  const riskStatus = riskLoad >= 70 ? "High attention" : riskLoad >= 45 ? "Watch closely" : "Controlled";

  return (
    <div className="overflow-hidden rounded-lg border border-rose-300/14 bg-[#120E13] shadow-[0_24px_80px_rgba(251,113,133,0.13)]">
      <div className="border-b border-rose-300/14 bg-[linear-gradient(135deg,rgba(251,113,133,0.18),rgba(251,191,36,0.10),rgba(56,189,248,0.06))] p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm text-rose-200">
              <ShieldCheck size={18} />
              Risk Control Room
            </div>
            <h2 className="text-2xl font-semibold tracking-normal">Risk arranged by exposure, stress and action</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-rose-50/68">
              Each tile shows one decision area, so concentration, drawdown and alerts stay easy to scan.
            </p>
          </div>
          <div className="rounded-md border border-rose-200/20 bg-black/24 px-3 py-2 text-right">
            <div className="text-xs text-rose-50/58">Risk load</div>
            <div className={`text-xl font-semibold ${riskLoad >= 70 ? "text-loss" : riskLoad >= 45 ? "text-amber" : "text-profit"}`}>
              {riskLoad}/100
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4">
        <RiskMetricTile icon={<Gauge size={18} />} label="Status" value={riskStatus} detail={`${data.healthScore}/100 health`} tone="rose" />
        <RiskMetricTile icon={<Layers size={18} />} label="Top 3 weight" value={`${topThreeAllocation.toFixed(1)}%`} detail="Position concentration" tone="amber" />
        <RiskMetricTile icon={<AlertTriangle size={18} />} label="Active alerts" value={`${alerts.length}`} detail={`${highRiskCount} high severity`} tone="red" />
        <RiskMetricTile icon={<PieChart size={18} />} label="Heavy sectors" value={`${heavySectors}`} detail="Above 25% review band" tone="sky" />
      </div>

      <div className="grid gap-4 border-t border-rose-300/10 bg-black/16 p-4 xl:grid-cols-[0.8fr_1.2fr]">
        <section className="rounded-md border border-rose-300/12 bg-white/[0.045] p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">Stress simulator</h3>
              <p className="text-sm text-rose-50/58">Move the slider to see portfolio impact.</p>
            </div>
            <span className="rounded-md border border-loss/30 bg-loss/10 px-2 py-1 text-sm text-loss">{stressPct}%</span>
          </div>
          <input
            aria-label="Risk stress percentage"
            type="range"
            min={-30}
            max={-3}
            value={stressPct}
            onChange={(event) => setStressPct(Number(event.target.value))}
            className="w-full accent-rose-400"
          />
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <ReportFact label="Drawdown estimate" value={formatCurrency(projectedStressLoss)} tone="text-loss" />
            <ReportFact label="Value after stress" value={formatCurrency(Math.max(0, data.portfolioValue - projectedStressLoss))} />
          </div>
          <div className="mt-4 rounded-md border border-amber/20 bg-amber/10 p-3 text-sm leading-6 text-amber">
            Use this as a sizing check. It is not a price forecast.
          </div>
        </section>

        <section className="rounded-md border border-rose-300/12 bg-white/[0.045] p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold">Holding heat map</h3>
              <p className="text-sm text-rose-50/58">Select a tile to inspect stress and advisor notes.</p>
            </div>
            <Activity className="text-rose-200" size={20} />
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            {topHoldings.slice(0, 8).map((holding) => {
              const riskScore = recommendationMap.get(holding.symbol)?.riskScore ?? getFallbackRisk(holding);
              const isSelected = selectedHolding?.symbol === holding.symbol;
              return (
                <button
                  key={holding.symbol}
                  type="button"
                  onClick={() => setSelectedSymbol(holding.symbol)}
                  className={`rounded-md border p-3 text-left transition duration-200 hover:-translate-y-0.5 ${
                    isSelected ? "border-rose-300/45 bg-rose-300/12" : "border-white/10 bg-black/20 hover:border-rose-300/28"
                  }`}
                >
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="font-medium">{holding.symbol}</span>
                    <span className={riskScore >= 70 ? "text-loss" : riskScore >= 55 ? "text-amber" : "text-profit"}>{riskScore}/100</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-black/40">
                    <div
                      className={riskScore >= 70 ? "h-2 rounded-full bg-loss" : riskScore >= 55 ? "h-2 rounded-full bg-amber" : "h-2 rounded-full bg-profit"}
                      style={{ width: `${riskScore}%` }}
                    />
                  </div>
                  <div className="mt-2 flex justify-between text-xs text-muted">
                    <span>{holding.allocationPct.toFixed(1)}% alloc.</span>
                    <span className={holding.totalPnl >= 0 ? "text-profit" : "text-loss"}>{formatCurrency(holding.totalPnl)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      </div>

      <div className="grid gap-4 border-t border-rose-300/10 p-4 xl:grid-cols-[1fr_0.9fr]">
        <section className="rounded-md border border-rose-300/12 bg-white/[0.045] p-4">
          <div className="mb-4 flex items-center gap-2">
            <PieChart className="text-amber" size={20} />
            <h3 className="text-base font-semibold">Sector exposure tiles</h3>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {data.sectorAllocation.map((sector) => {
              const isHeavy = sector.percentage >= 25;
              return (
                <div key={sector.label} className="rounded-md border border-white/10 bg-black/20 p-3 transition duration-200 hover:-translate-y-0.5 hover:border-amber/28">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="text-sm font-medium">{sector.label}</span>
                    <span className={isHeavy ? "text-amber" : "text-rose-50/70"}>{sector.percentage.toFixed(1)}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-black/40">
                    <div className={`h-2 rounded-full ${isHeavy ? "bg-amber" : "bg-sky-300"}`} style={{ width: `${Math.min(sector.percentage, 100)}%` }} />
                  </div>
                  <p className="mt-2 text-xs text-muted">{isHeavy ? "Trim fresh exposure until weight cools." : "Inside review band."}</p>
                </div>
              );
            })}
          </div>
        </section>

        <section className="rounded-md border border-rose-300/12 bg-white/[0.045] p-4">
          <div className="mb-4 flex items-center gap-2">
            <ClipboardList className="text-rose-200" size={20} />
            <h3 className="text-base font-semibold">Risk log</h3>
          </div>
          <div className="space-y-3">
            {alerts.slice(0, 6).map((alert, index) => (
              <motion.div
                key={`${alert.symbol ?? "portfolio"}-${index}`}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.03, duration: 0.18 }}
                className="rounded-md border border-white/10 bg-black/20 p-3"
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <span className="text-sm font-medium">{alert.symbol ?? "Portfolio"}</span>
                  <SeverityPill severity={alert.severity} />
                </div>
                <p className="text-sm leading-5 text-foreground/82">{alert.message}</p>
                <p className="mt-2 text-xs text-muted">{alert.action}</p>
              </motion.div>
            ))}
          </div>
        </section>
      </div>

      <div className="border-t border-rose-300/10 p-4">
        <PositionDrilldown
          holding={selectedHolding}
          recommendation={selectedHolding ? recommendationMap.get(selectedHolding.symbol) : undefined}
          stressPct={stressPct}
        />
      </div>
    </div>
  );
}

function PortfolioReport({
  data,
  intelligence,
  analytics,
  aiInsight,
  aiInsightError,
  aiSettings,
  isGeneratingAiInsight,
  onGenerateAiInsight,
  onRefresh
}: {
  data: PortfolioSummary;
  intelligence?: PortfolioIntelligence;
  analytics?: PortfolioAnalytics;
  aiInsight: AiAnalyticsInsight | null;
  aiInsightError: string | null;
  aiSettings?: OpenAiSettings;
  isGeneratingAiInsight: boolean;
  onGenerateAiInsight: () => Promise<void>;
  onRefresh: () => void;
}) {
  const [section, setSection] = useState<ReportSection>("summary");
  const [reportMode, setReportMode] = useState<"brief" | "deep">("brief");
  const [activeActionIndex, setActiveActionIndex] = useState(0);
  const generatedAt = new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(intelligence?.generatedAt ?? data.updatedAt));
  const totalCapital = data.portfolioValue + data.cashBalance;
  const cashPct = totalCapital > 0 ? (data.cashBalance / totalCapital) * 100 : 0;
  const topHoldings = [...data.holdings].sort((a, b) => b.allocationPct - a.allocationPct);
  const topThreeAllocation = topHoldings.slice(0, 3).reduce((sum, holding) => sum + holding.allocationPct, 0);
  const highRiskCount = intelligence?.alerts.filter((alert) => alert.severity === "high").length ?? 0;
  const reduceCount =
    intelligence?.recommendations.filter((item) => isReduceCall(item.recommendation)).length ?? 0;
  const addCount = intelligence?.recommendations.filter((item) => isAddCall(item.recommendation)).length ?? 0;
  const holdCount = Math.max(0, (intelligence?.recommendations.length ?? data.holdings.length) - addCount - reduceCount);
  const actions = buildReportActions(data, intelligence);
  const verdict = getPortfolioVerdict(data.healthScore, topThreeAllocation, highRiskCount, cashPct);
  const activeAction = actions[Math.min(activeActionIndex, actions.length - 1)];
  const analyticsRows = buildHoldingDecisionRows(analytics);
  const analyticsAddCount = analyticsRows.filter((row) => row.action === "Add").length;
  const analyticsHoldCount = analyticsRows.filter((row) => row.action === "Hold").length;
  const analyticsReviewCount = analyticsRows.filter((row) => row.action === "Review").length;
  const strongCompanyCount = analytics?.companies.filter((company) => company.overallScore >= 72).length ?? 0;
  const sanityIssueCount = analytics?.sanityChecks.filter((check) => check.status !== "pass").length ?? 0;
  const reportTabs: Array<[ReportSection, typeof Target, string, string]> = [
    ["summary", Target, "Summary", "Decision memo"],
    ["actions", ListChecks, "Actions", "What to do next"],
    ["analytics", Bot, "AI + Analytics", "Combined report"],
    ["quality", Search, "Quality", "Data and method"],
    ["calendar", CalendarClock, "Calendar", "Review rhythm"]
  ];
  const averageConfidence =
    intelligence?.recommendations.length
      ? Math.round(
          intelligence.recommendations.reduce((sum, item) => sum + item.confidenceScore, 0) /
            intelligence.recommendations.length
        )
      : 0;

  return (
    <>
      <div className="overflow-hidden rounded-lg border border-violet-200/14 bg-[#100F1A] shadow-[0_28px_90px_rgba(167,139,250,0.15)]">
        <div className="border-b border-violet-200/14 bg-[radial-gradient(circle_at_82%_0%,rgba(251,191,36,0.18),transparent_32%),linear-gradient(135deg,rgba(167,139,250,0.20),rgba(17,16,26,0.96))] p-4">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div className="max-w-3xl">
              <div className="mb-2 flex items-center gap-2 text-sm text-violet-200">
                <FileText size={18} />
                Report Studio
              </div>
              <h2 className="text-2xl font-semibold tracking-normal">Decision memo and action journal</h2>
              <p className="mt-2 text-sm leading-6 text-violet-50/68">
                A compact consultant-style report. Risk controls stay in Risk; this page keeps conclusions, actions and evidence.
              </p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <div className="inline-flex h-10 rounded-md border border-violet-200/16 bg-black/24 p-1">
                {(["brief", "deep"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setReportMode(mode)}
                    className={`rounded px-3 text-sm capitalize transition ${
                      reportMode === mode ? "bg-violet-300 text-black" : "text-muted hover:text-foreground"
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
              <Button type="button" variant="ghost" onClick={onRefresh}>
                <RefreshCw size={18} />
                Refresh
              </Button>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted">
            <span className="rounded-md border border-violet-200/14 bg-white/5 px-2 py-1">Generated {generatedAt}</span>
            <span className="rounded-md border border-violet-200/14 bg-white/5 px-2 py-1">
              Data quality {intelligence?.dataQuality.score ?? 72}/100
            </span>
            <span className="rounded-md border border-violet-200/14 bg-white/5 px-2 py-1">Advisory only</span>
          </div>
        </div>

        <div className="grid gap-3 border-b border-violet-200/10 bg-black/12 p-4 md:grid-cols-2 xl:grid-cols-4">
          <ReportKpi label="Advisor View" value={verdict.label} detail={verdict.detail} tone={verdict.tone} icon={<ShieldCheck size={18} />} />
          <ReportKpi label="Action Calls" value={`${actions.length}`} detail={`${addCount} add, ${reduceCount} reduce`} icon={<ClipboardList size={18} />} />
          <ReportKpi label="Conviction" value={averageConfidence ? `${averageConfidence}/100` : "Pending"} detail="Avg. recommendation confidence" icon={<Bot size={18} />} />
          <ReportKpi
            label="Confirmed Cash"
            value={data.cashBalance > 0 ? `${cashPct.toFixed(1)}%` : "Not synced"}
            detail={data.cashBalance > 0 ? formatCurrency(data.cashBalance) : "Broker cash data unavailable"}
            icon={<Wallet size={18} />}
          />
        </div>

        <div className="grid gap-2 border-b border-violet-200/10 bg-black/20 p-3 md:grid-cols-2 xl:grid-cols-5">
          {reportTabs.map(([id, Icon, label, detail]) => (
            <button
              key={id}
              type="button"
              onClick={() => setSection(id)}
              className={`rounded-md border p-3 text-left transition ${
                section === id
                  ? "border-violet-200/45 bg-violet-300/12 text-foreground"
                  : "border-transparent bg-white/5 text-muted hover:border-violet-200/22 hover:text-foreground"
              }`}
            >
              <div className="flex items-center gap-2 text-sm font-medium">
                <Icon size={17} />
                {label}
              </div>
              <div className="mt-1 text-xs text-muted">{detail}</div>
            </button>
          ))}
        </div>

        <div className="p-4">
          <AnimatePresence mode="wait">
            {section === "summary" ? (
              <ReportSectionShell key="summary">
                <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                    <div className="mb-3 flex items-center gap-2">
                      <Target className="text-violet-200" size={20} />
                      <h3 className="text-base font-semibold">Executive memo</h3>
                    </div>
                    <p className="text-sm leading-6 text-foreground/86">{data.aiSummary}</p>
                    {reportMode === "deep" ? (
                      <div className="mt-4 rounded-md border border-violet-200/12 bg-black/24 p-3 text-sm leading-6 text-violet-50/76">
                        The model refreshes live market snapshots before analysis where the provider returns valid data. Use the report as a review aid, then validate entries, liquidity and taxes before acting.
                      </div>
                    ) : null}
                  </section>

                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                    <div className="mb-4 flex items-center justify-between">
                      <div>
                        <h3 className="text-base font-semibold">Recommendation mix</h3>
                        <p className="text-sm text-violet-50/55">Calls from latest analysis run</p>
                      </div>
                      <BarChart3 className="text-amber" size={20} />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
                      <GlassStat label="Add / Buy" value={`${addCount}`} />
                      <GlassStat label="Hold / Watch" value={`${holdCount}`} />
                      <GlassStat label="Reduce / Exit" value={`${reduceCount}`} />
                    </div>
                  </section>
                </div>

                <div className="grid gap-4 xl:grid-cols-3">
                  <ReportNote
                    icon={<Activity size={18} />}
                    title="Market posture"
                    text={getMarketPosture(data.healthScore, data.totalPnlPct, cashPct)}
                  />
                  <ReportNote
                    icon={<CheckCircle2 size={18} />}
                    title="Quality filter"
                    text="Prefer adding only to names where earnings visibility, balance sheet strength and price trend agree."
                  />
                  <ReportNote
                    icon={<ShieldCheck size={18} />}
                    title="Risk rule"
                    text="No fresh capital should increase a stock or sector that is already beyond the review band."
                  />
                </div>
              </ReportSectionShell>
            ) : null}

            {section === "actions" ? (
              <ReportSectionShell key="actions">
                <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-4">
                    <div className="mb-4 flex items-center gap-2">
                      <ClipboardList className="text-violet-200" size={20} />
                      <h3 className="text-base font-semibold">Priority action sheet</h3>
                    </div>
                    <div className="space-y-2">
                      {actions.map((action, index) => (
                        <button
                          key={`${action.title}-${index}`}
                          type="button"
                          onClick={() => setActiveActionIndex(index)}
                          className={`grid w-full gap-3 rounded-md border p-3 text-left transition sm:grid-cols-[96px_1fr] ${
                            activeActionIndex === index
                              ? "border-violet-200/45 bg-violet-300/12"
                              : "border-violet-200/12 bg-black/20 hover:border-violet-200/28"
                          }`}
                        >
                          <PriorityPill priority={action.priority} />
                          <span>
                            <span className="block font-medium">{action.title}</span>
                            <span className="mt-1 block text-sm text-muted">{action.timing}</span>
                          </span>
                        </button>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <ListChecks className="text-profit" size={20} />
                      <h3 className="text-base font-semibold">Execution note</h3>
                    </div>
                    {activeAction ? (
                      <div className="rounded-md border border-violet-200/12 bg-black/22 p-4">
                        <PriorityPill priority={activeAction.priority} />
                        <h4 className="mt-4 text-lg font-semibold">{activeAction.title}</h4>
                        <p className="mt-2 text-sm leading-6 text-foreground/84">{activeAction.reason}</p>
                        <div className="mt-4 rounded-md border border-violet-200/12 bg-black/30 p-3 text-sm text-muted">
                          {activeAction.timing}
                        </div>
                      </div>
                    ) : null}
                    <div className="mt-4 grid gap-3 sm:grid-cols-3">
                      <ReportFact label="High priority" value={`${actions.filter((item) => item.priority === "High").length}`} />
                      <ReportFact label="Medium priority" value={`${actions.filter((item) => item.priority === "Medium").length}`} />
                      <ReportFact label="Low priority" value={`${actions.filter((item) => item.priority === "Low").length}`} />
                    </div>
                  </section>
                </div>
              </ReportSectionShell>
            ) : null}

            {section === "analytics" ? (
              <ReportSectionShell key="analytics">
                <div className="grid gap-4 xl:grid-cols-[1fr_0.95fr]">
                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="mb-2 flex items-center gap-2 text-violet-100">
                          <Building2 size={18} />
                          <h3 className="text-base font-semibold text-foreground">Analytics engine report</h3>
                        </div>
                        <p className="text-sm leading-6 text-violet-50/70">
                          Deterministic business-intelligence output from company fundamentals, valuation, cash flow, price context, news coverage and sanity checks.
                        </p>
                      </div>
                      <span className="rounded-md border border-violet-200/16 bg-violet-300/12 px-2 py-1 text-sm text-violet-100">
                        {analytics ? `${analytics.dataQualityScore}/100 quality` : "No analytics"}
                      </span>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      <ReportFact label="Companies" value={`${analytics?.companies.length ?? 0}`} />
                      <ReportFact label="Strong BI" value={`${strongCompanyCount}`} tone="text-profit" />
                      <ReportFact label="Sanity watch" value={`${sanityIssueCount}`} tone={sanityIssueCount ? "text-amber" : "text-profit"} />
                      <ReportFact label="Next refresh" value={analytics ? formatShortDateTime(analytics.nextRefreshAt) : "Pending"} />
                    </div>

                    <div className="mt-4 rounded-md border border-violet-200/12 bg-black/24 p-4">
                      <div className="mb-2 flex items-center gap-2 text-violet-100">
                        <Database size={18} />
                        <span className="text-sm font-medium text-foreground">Engine conclusion</span>
                      </div>
                      <p className="text-sm leading-6 text-foreground/84">
                        {analytics?.summary ?? "Analytics data is not available yet. Sync holdings or refresh Daily BI."}
                      </p>
                    </div>
                  </section>

                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="mb-2 flex items-center gap-2 text-violet-100">
                          <Sparkles size={18} />
                          <h3 className="text-base font-semibold text-foreground">AI interpretation report</h3>
                        </div>
                        <p className="text-sm leading-6 text-violet-50/70">
                          Consultant-style interpretation of the analytics engine, limited to your current holdings and backend evidence.
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={onGenerateAiInsight}
                        disabled={isGeneratingAiInsight || !aiSettings?.configured || !analytics?.companies.length}
                      >
                        <Bot size={18} className={isGeneratingAiInsight ? "animate-pulse" : ""} />
                        {isGeneratingAiInsight ? "Generating" : aiInsight ? "Regenerate" : "Generate AI"}
                      </Button>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <ReportFact
                        label="AI provider"
                        value={aiSettings?.configured ? providerLabel(aiSettings.provider) : "Not configured"}
                      />
                      <ReportFact label="AI model" value={aiSettings?.model ?? "Pending"} />
                    </div>

                    {aiInsightError ? (
                      <div className="mt-4 rounded-md border border-loss/20 bg-loss/10 p-3 text-sm leading-6 text-loss">
                        {aiInsightError}
                      </div>
                    ) : null}

                    <div className="mt-4 rounded-md border border-violet-200/12 bg-black/24 p-4">
                      <div className="mb-2 flex items-center gap-2 text-violet-100">
                        <Bot size={18} />
                        <span className="text-sm font-medium text-foreground">AI conclusion</span>
                      </div>
                      <AiFormattedText
                        text={
                          aiInsight?.summary ??
                          (aiSettings?.configured
                            ? "Generate AI analysis to add the consultant interpretation into this report."
                            : "Configure Gemini in AI Config, then generate AI analysis.")
                        }
                        className="text-sm leading-6 text-foreground/84"
                      />
                    </div>
                  </section>
                </div>

                <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                  <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="mb-2 flex items-center gap-2 text-violet-100">
                        <CircleDollarSign size={18} />
                        <h3 className="text-base font-semibold text-foreground">Combined decision matrix</h3>
                      </div>
                      <p className="text-sm leading-6 text-violet-50/70">
                        Analytics provides the score and rule-based signal. AI provides the narrative explanation and risk-control framing.
                      </p>
                    </div>
                    <div className="grid w-full grid-cols-3 gap-2 sm:w-auto sm:min-w-[300px]">
                      <DecisionCount label="Add" value={analyticsAddCount} tone="text-profit" />
                      <DecisionCount label="Hold" value={analyticsHoldCount} tone="text-amber" />
                      <DecisionCount label="Review" value={analyticsReviewCount} tone="text-loss" />
                    </div>
                  </div>

                  {analyticsRows.length ? (
                    <div className="grid gap-3 xl:grid-cols-3">
                      {analyticsRows.slice(0, reportMode === "deep" ? 9 : 6).map((row) => (
                        <div key={row.symbol} className="rounded-md border border-violet-200/12 bg-black/22 p-4">
                          <div className="mb-3 flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <div className="font-medium">{row.symbol}</div>
                              <div className="truncate text-xs text-muted">{row.companyName}</div>
                            </div>
                            <span className={`rounded-md border px-2 py-1 text-xs ${decisionBadgeTone(row.action)}`}>
                              {row.action}
                            </span>
                          </div>
                          <div className="mb-3 grid grid-cols-3 gap-2">
                            <DecisionMiniStat label="BI" value={`${row.score}`} tone={scoreTone(row.score)} />
                            <DecisionMiniStat label="Conv." value={`${row.conviction}`} tone={scoreTone(row.conviction)} />
                            <DecisionMiniStat label="Conf." value={`${row.confidence}`} tone={scoreTone(row.confidence)} />
                          </div>
                          <p className="text-sm leading-5 text-foreground/82">{row.reason}</p>
                          {reportMode === "deep" ? (
                            <p className="mt-3 rounded-md border border-white/10 bg-white/[0.04] p-2 text-xs leading-5 text-muted">
                              {row.entryDiscipline}
                            </p>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-md border border-amber/20 bg-amber/10 p-4 text-sm leading-6 text-amber/90">
                      No analytics decision rows are available. Sync/import holdings, then refresh Daily BI.
                    </div>
                  )}
                </section>

                <div className="grid gap-4 xl:grid-cols-2">
                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                    <div className="mb-4 flex items-center gap-2">
                      <ListChecks className="text-profit" size={20} />
                      <h3 className="text-base font-semibold">AI action interpretation</h3>
                    </div>
                    <div className="grid gap-3">
                      <ReportInsightBlock title="Buy focus" items={aiInsight?.buyFocus ?? []} tone="text-profit" />
                      <ReportInsightBlock title="Hold focus" items={aiInsight?.holdFocus ?? []} tone="text-amber" />
                      <ReportInsightBlock title="Review or sell focus" items={aiInsight?.sellOrReviewFocus ?? []} tone="text-loss" />
                    </div>
                  </section>

                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                    <div className="mb-4 flex items-center gap-2">
                      <ShieldCheck className="text-sky-200" size={20} />
                      <h3 className="text-base font-semibold">Controls and warnings</h3>
                    </div>
                    <div className="grid gap-3">
                      <ReportInsightBlock title="Risk controls" items={aiInsight?.riskControls ?? []} tone="text-sky-200" />
                      <ReportInsightBlock
                        title="AI data warnings"
                        items={aiInsight?.dataWarnings ?? []}
                        tone="text-amber"
                        emptyText="No AI warning has been generated yet."
                      />
                      <ReportInsightBlock
                        title="Analytics warnings"
                        items={[...(analytics?.warnings ?? []), ...(analytics?.sanityChecks.filter((check) => check.status !== "pass").map((check) => `${check.label}: ${check.detail}`) ?? [])]}
                        tone="text-amber"
                        emptyText="Analytics sanity checks are currently clear."
                      />
                    </div>
                  </section>
                </div>
              </ReportSectionShell>
            ) : null}

            {section === "quality" ? (
              <ReportSectionShell key="quality">
                <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                    <div className="mb-4 flex items-center justify-between">
                      <div>
                        <h3 className="text-base font-semibold">Data quality</h3>
                        <p className="text-sm text-violet-50/55">Live enrichment and confidence inputs</p>
                      </div>
                      <span className="rounded-md border border-violet-200/18 bg-violet-300/12 px-2 py-1 text-sm text-violet-100">
                        {intelligence?.dataQuality.score ?? 72}/100
                      </span>
                    </div>
                    <div className="h-3 overflow-hidden rounded-full bg-black/35">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${intelligence?.dataQuality.score ?? 72}%` }}
                        transition={{ duration: 0.55, ease: "easeOut" }}
                        className="h-3 rounded-full bg-violet-300"
                      />
                    </div>
                    <p className="mt-4 text-sm leading-6 text-violet-50/70">
                      Recommendations combine broker holdings, live market snapshots, technical indicators and conservative missing-data penalties.
                    </p>
                  </section>
                  <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                    <div className="mb-4 flex items-center gap-2">
                      <Search className="text-amber" size={20} />
                      <h3 className="text-base font-semibold">Analysis log</h3>
                    </div>
                    <div className="space-y-2">
                      {(intelligence?.dataQuality.warnings.length ? intelligence.dataQuality.warnings : ["No provider warnings in the latest run."]).map((warning) => (
                        <div key={warning} className="rounded-md border border-violet-200/12 bg-black/22 p-3 text-sm leading-5 text-muted">
                          {warning}
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              </ReportSectionShell>
            ) : null}

            {section === "calendar" ? (
              <ReportSectionShell key="calendar">
                <section className="rounded-md border border-violet-200/12 bg-white/[0.045] p-5">
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <CalendarClock className="text-amber" size={20} />
                      <h3 className="text-base font-semibold">Review calendar</h3>
                    </div>
                    <span className="rounded-md border border-amber/20 bg-amber/10 px-2 py-1 text-sm text-amber">
                      {data.upcomingEvents.length ? `${data.upcomingEvents.length} events` : "Review rhythm"}
                    </span>
                  </div>
                  <div className="grid gap-3 lg:grid-cols-3">
                    {(data.upcomingEvents.length ? data.upcomingEvents : buildReviewRhythm(data, intelligence, analytics)).map((event, index) => (
                      <motion.div
                        key={event}
                        initial={{ opacity: 0, y: 14, scale: 0.96, rotateX: -12 }}
                        animate={{ opacity: 1, y: 0, scale: 1, rotateX: 0 }}
                        transition={{ delay: index * 0.05, duration: 0.28, ease: "easeOut" }}
                        className="holo-card min-h-[112px] rounded-md border border-violet-200/12 bg-black/22 p-4 text-sm text-muted"
                      >
                        <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-md bg-amber/12 text-amber">
                          <CalendarClock size={16} />
                        </div>
                        {event}
                      </motion.div>
                    ))}
                  </div>
                </section>
              </ReportSectionShell>
            ) : null}
          </AnimatePresence>
        </div>
      </div>
    </>
  );
}

function Metric({
  title,
  value,
  detail,
  tone = "text-foreground",
  icon
}: {
  title: string;
  value: string;
  detail?: string;
  tone?: string;
  icon: React.ReactNode;
}) {
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between text-muted">
        <span className="text-sm">{title}</span>
        {icon}
      </div>
      <div className={`text-2xl font-semibold tracking-normal ${tone}`}>{value}</div>
      {detail ? <div className="mt-1 text-sm text-muted">{detail}</div> : null}
    </Card>
  );
}

function GlassStat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ duration: 0.18 }}
      className="min-h-[82px] rounded-md border border-white/10 bg-white/[0.055] p-3"
    >
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-2 text-base font-semibold text-foreground">{value}</div>
      {detail ? <div className="mt-1 text-xs text-muted">{detail}</div> : null}
    </motion.div>
  );
}

type HoldingDecisionRow = {
  symbol: string;
  companyName: string;
  action: "Add" | "Hold" | "Review";
  score: number;
  confidence: number;
  conviction: number;
  reason: string;
  entryDiscipline: string;
  rank: number;
};

function buildHoldingDecisionRows(analytics?: PortfolioAnalytics): HoldingDecisionRow[] {
  if (!analytics) {
    return [];
  }
  const companies = new Map(analytics.companies.map((company) => [company.symbol, company]));
  return analytics.decisionSignals.map((signal) => {
    const company = companies.get(signal.symbol);
    return {
      symbol: signal.symbol,
      companyName: company?.companyName ?? signal.symbol,
      action: normalizeDecisionAction(signal.action),
      score: company?.overallScore ?? signal.convictionScore,
      confidence: signal.confidence,
      conviction: signal.convictionScore,
      reason: signal.reasoning,
      entryDiscipline: signal.entryDiscipline,
      rank: signal.convictionScore
    };
  });
}

function normalizeDecisionAction(action: string): HoldingDecisionRow["action"] {
  if (action.includes("Add")) {
    return "Add";
  }
  if (action.includes("Risk") || action.includes("Verify")) {
    return "Review";
  }
  return "Hold";
}

function decisionBadgeTone(action: HoldingDecisionRow["action"]) {
  if (action === "Add") {
    return "border-profit/24 bg-profit/10 text-profit";
  }
  if (action === "Hold") {
    return "border-amber/24 bg-amber/10 text-amber";
  }
  return "border-loss/24 bg-loss/10 text-loss";
}

function DecisionCount({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/24 p-3 text-center">
      <div className={`text-xl font-semibold ${tone}`}>{value}</div>
      <div className="mt-1 text-xs text-muted">{label}</div>
    </div>
  );
}

function DecisionMiniStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.045] px-2 py-2">
      <div className="text-[11px] text-muted">{label}</div>
      <div className={`mt-1 text-sm font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

function AnalyticsHeroTile({
  icon,
  label,
  value,
  detail,
  tone
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  tone: "teal" | "sky" | "green" | "amber";
}) {
  const className = {
    teal: "border-teal-200/18 bg-teal-300/10 text-teal-100",
    sky: "border-sky-300/18 bg-sky-300/10 text-sky-100",
    green: "border-profit/18 bg-profit/10 text-profit",
    amber: "border-amber/22 bg-amber/10 text-amber"
  }[tone];

  return (
    <motion.div whileHover={{ y: -3 }} transition={{ duration: 0.18 }} className={`min-h-[118px] rounded-md border p-4 ${className}`}>
      <div className="mb-3 flex items-center justify-between text-current/78">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className="text-xl font-semibold tracking-normal text-foreground">{value}</div>
      <div className="mt-1 text-sm text-current/70">{detail}</div>
    </motion.div>
  );
}

function CompanyScore({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-teal-200/12 bg-black/22 p-3">
      <div className="mb-2 flex items-center justify-between text-xs text-muted">
        <span>{label}</span>
        <span className={scoreTone(value)}>{value}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-black/40">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(100, value)}%` }}
          transition={{ duration: 0.45, ease: "easeOut" }}
          className={`h-2 rounded-full ${value >= 72 ? "bg-profit" : value >= 52 ? "bg-amber" : "bg-loss"}`}
        />
      </div>
    </div>
  );
}

function SignalPanel({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <section className="rounded-md border border-teal-200/12 bg-black/22 p-4">
      <h4 className={`mb-3 text-base font-semibold ${tone}`}>{title}</h4>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item} className="text-sm leading-5 text-muted">
            {item}
          </div>
        ))}
      </div>
    </section>
  );
}

function AiAnalysisProgress({
  elapsedSeconds,
  holdingsCount,
  provider,
  model
}: {
  elapsedSeconds: number;
  holdingsCount: number;
  provider: AiProvider;
  model: string;
}) {
  const activeStep = getAiAnalysisStep(elapsedSeconds);
  const activeIndex = AI_ANALYSIS_STEPS.findIndex((step) => step.title === activeStep.title);

  return (
    <section className="rounded-md border border-violet-200/16 bg-[linear-gradient(135deg,rgba(139,92,246,0.13),rgba(14,165,233,0.07),rgba(0,0,0,0.22))] p-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-2 flex items-center gap-2 text-violet-100">
            <RefreshCw size={18} className="animate-spin" />
            <h3 className="text-base font-semibold text-foreground">AI analysis running</h3>
          </div>
          <p className="text-sm leading-6 text-violet-50/72">{activeStep.detail}</p>
        </div>
        <div className="grid min-w-[210px] grid-cols-2 gap-2 text-sm">
          <div className="rounded-md border border-white/10 bg-black/24 p-3">
            <div className="text-xs text-muted">Done</div>
            <div className="mt-1 text-lg font-semibold text-foreground">{activeStep.percent}%</div>
          </div>
          <div className="rounded-md border border-white/10 bg-black/24 p-3">
            <div className="text-xs text-muted">Elapsed</div>
            <div className="mt-1 text-lg font-semibold text-foreground">{formatElapsed(elapsedSeconds)}</div>
          </div>
        </div>
      </div>

      <div className="mb-4 h-2 overflow-hidden rounded-full bg-black/40">
        <motion.div
          animate={{ width: `${activeStep.percent}%` }}
          transition={{ duration: 0.45, ease: "easeOut" }}
          className="h-full rounded-full bg-[linear-gradient(90deg,#22d3ee,#a78bfa,#34d399)]"
        />
      </div>

      <div className="mb-4 grid gap-2 text-sm md:grid-cols-3">
        <div className="rounded-md border border-white/10 bg-black/22 p-3">
          <div className="text-xs text-muted">Current step</div>
          <div className="mt-1 font-medium text-foreground">{activeStep.title}</div>
        </div>
        <div className="rounded-md border border-white/10 bg-black/22 p-3">
          <div className="text-xs text-muted">Scope</div>
          <div className="mt-1 font-medium text-foreground">{holdingsCount} holdings only</div>
        </div>
        <div className="rounded-md border border-white/10 bg-black/22 p-3">
          <div className="text-xs text-muted">Provider</div>
          <div className="mt-1 truncate font-medium text-foreground">
            {providerLabel(provider)} · {model}
          </div>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {AI_ANALYSIS_STEPS.map((step, index) => {
          const isComplete = index < activeIndex;
          const isActive = index === activeIndex;
          return (
            <div
              key={step.title}
              className={`rounded-md border p-3 transition ${
                isActive
                  ? "border-violet-200/36 bg-violet-300/12 text-foreground"
                  : isComplete
                    ? "border-profit/18 bg-profit/10 text-foreground"
                    : "border-white/10 bg-black/20 text-muted"
              }`}
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{step.title}</span>
                {isComplete ? (
                  <CheckCircle2 size={16} className="text-profit" />
                ) : isActive ? (
                  <Activity size={16} className="text-violet-100" />
                ) : (
                  <CircleDollarSign size={16} className="text-muted" />
                )}
              </div>
              <div className="text-xs leading-5 text-current/70">{isComplete ? "Completed" : isActive ? "In progress" : "Waiting"}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function AiInsightList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <section className="rounded-md border border-white/10 bg-black/22 p-4">
      <h4 className={`mb-3 text-base font-semibold ${tone}`}>{title}</h4>
      <div className="space-y-2">
        {items.length ? (
          items.map((item, index) => (
            <div key={`${item}-${index}`} className="rounded-md border border-white/10 bg-white/[0.035] p-3 text-sm leading-5 text-muted">
              <AiFormattedText text={item} />
            </div>
          ))
        ) : (
          <div className="text-sm text-muted">No item returned.</div>
        )}
      </div>
    </section>
  );
}

function getAiAnalysisStep(elapsedSeconds: number) {
  let activeStep = AI_ANALYSIS_STEPS[0];
  for (const step of AI_ANALYSIS_STEPS) {
    if (elapsedSeconds >= step.at) {
      activeStep = step;
    }
  }
  return activeStep;
}

function formatElapsed(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

type PipelineTone = "teal" | "cyan" | "green" | "amber" | "rose" | "violet";

function buildDataProvenanceProfile(analytics?: PortfolioAnalytics) {
  const companies = analytics?.companies ?? [];
  const companyCount = companies.length;
  const pct = (count: number) => (companyCount ? Math.round((count / companyCount) * 100) : 0);
  const noteBlob = companies.flatMap((company) => company.sourceNotes).join(" \n ").toLowerCase();
  const notesFor = (pattern: string) => companies.filter((company) => company.sourceNotes.some((note) => note.toLowerCase().includes(pattern))).length;
  const livePriceCoverage = pct(companies.filter((company) => company.lastPrice !== null && company.lastPrice !== undefined).length);
  const fundamentalsCoverage = pct(
    companies.filter((company) => company.financials.filter((metric) => metric.value !== "N/A").length >= 7).length
  );
  const newsCoverage = pct(companies.filter((company) => company.news.length > 0).length);
  const yahooCoverage = pct(notesFor("yahoo finance"));
  const alphaCoverage = pct(notesFor("alpha vantage"));
  const finnhubCoverage = pct(notesFor("finnhub"));
  const consensusCoverage = pct(notesFor("validated market snapshot source"));
  const withheldCoverage = pct(notesFor("withheld live price") + notesFor("rejected consensus"));
  const passChecks = analytics?.sanityChecks.filter((check) => check.status === "pass").length ?? 0;
  const totalChecks = analytics?.sanityChecks.length ?? 0;
  const sanityPassRate = totalChecks ? Math.round((passChecks / totalChecks) * 100) : 0;
  const blockers = analytics?.sanityChecks.filter((check) => check.status === "fail").length ?? 0;
  const warningPenalty = Math.min(35, (analytics?.warnings.length ?? 0) * 7 + withheldCoverage * 0.35);
  const sanitizationScore = Math.max(0, Math.round((analytics?.dataQualityScore ?? 0) - warningPenalty * 0.3));
  const sourceFetchCoverage = Math.round((livePriceCoverage + fundamentalsCoverage + newsCoverage) / 3);

  return {
    companyCount,
    analyticsReadiness: analytics?.dataQualityScore ?? 0,
    blockers,
    issues: [
      ...(analytics?.warnings ?? []),
      ...(analytics?.sanityChecks.filter((check) => check.status !== "pass").map((check) => `${check.label}: ${check.detail}`) ?? []),
      ...(noteBlob.includes("withheld live price") ? ["Live price was withheld for at least one holding because validation did not pass."] : []),
    ],
    checks:
      analytics?.sanityChecks.length
        ? analytics.sanityChecks
        : [
            {
              label: "Waiting for analytics",
              status: "watch" as const,
              detail: "Refresh Daily BI to calculate source coverage, validation, and sanity checks.",
            },
          ],
    sources: [
      {
        label: "Holdings database",
        detail: "Zerodha sync or CSV import, used as portfolio truth.",
        percent: companyCount ? 100 : 0,
        tone: "green" as PipelineTone,
      },
      {
        label: "Yahoo Finance",
        detail: "Chart, profile/news, fundamentals, and no-key fallback.",
        percent: yahooCoverage,
        tone: "cyan" as PipelineTone,
      },
      {
        label: "Alpha Vantage",
        detail: "Optional independent daily OHLCV validation when key is configured.",
        percent: alphaCoverage,
        tone: alphaCoverage ? "violet" as PipelineTone : "amber" as PipelineTone,
      },
      {
        label: "Finnhub",
        detail: "Optional quote/candle validation when key is configured.",
        percent: finnhubCoverage,
        tone: finnhubCoverage ? "teal" as PipelineTone : "amber" as PipelineTone,
      },
      {
        label: "Consensus market snapshot",
        detail: "Accepted live price after provider sanitization and cross-checking.",
        percent: consensusCoverage || livePriceCoverage,
        tone: "green" as PipelineTone,
      },
      {
        label: "AI engineer layer",
        detail: "Optional explanation/cross-check after validated analytics, not raw market data.",
        percent: analytics ? analytics.dataQualityScore : 0,
        tone: "violet" as PipelineTone,
      },
    ],
    stages: [
      {
        label: "1. Ingest",
        detail: "Holdings loaded",
        percent: companyCount ? 100 : 0,
        tone: "green" as PipelineTone,
      },
      {
        label: "2. Source fetch",
        detail: "Price, financials, news",
        percent: sourceFetchCoverage,
        tone: "cyan" as PipelineTone,
      },
      {
        label: "3. Sanitization",
        detail: "Invalid values removed",
        percent: sanitizationScore,
        tone: sanitizationScore >= 70 ? "green" as PipelineTone : "amber" as PipelineTone,
      },
      {
        label: "4. Validation",
        detail: "Consensus and sanity gate",
        percent: Math.round((livePriceCoverage + sanityPassRate) / 2),
        tone: withheldCoverage ? "amber" as PipelineTone : "teal" as PipelineTone,
      },
      {
        label: "5. Analytics feed",
        detail: "BI model readiness",
        percent: analytics?.dataQualityScore ?? 0,
        tone: (analytics?.dataQualityScore ?? 0) >= 75 ? "green" as PipelineTone : "amber" as PipelineTone,
      },
    ],
  };
}

function scoreTone(score: number) {
  if (score >= 72) {
    return "text-profit";
  }
  if (score >= 52) {
    return "text-amber";
  }
  return "text-loss";
}

function metricTone(tone: CompanyAnalytics["financials"][number]["tone"]) {
  if (tone === "good") {
    return "text-profit";
  }
  if (tone === "watch") {
    return "text-amber";
  }
  if (tone === "bad") {
    return "text-loss";
  }
  return "text-foreground";
}

function sanityTone(status: PortfolioAnalytics["sanityChecks"][number]["status"]) {
  if (status === "pass") {
    return "text-profit";
  }
  if (status === "watch") {
    return "text-amber";
  }
  return "text-loss";
}

function providerLabel(provider: AiProvider) {
  return provider === "gemini" ? "Gemini" : "OpenAI";
}

function formatShortDateTime(value: string) {
  return new Intl.DateTimeFormat("en-IN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function RiskMetricTile({
  icon,
  label,
  value,
  detail,
  tone
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  tone: "rose" | "amber" | "red" | "sky";
}) {
  const toneClass = {
    rose: "border-rose-300/18 bg-rose-300/10 text-rose-100",
    amber: "border-amber/22 bg-amber/10 text-amber",
    red: "border-loss/22 bg-loss/10 text-loss",
    sky: "border-sky-300/20 bg-sky-300/10 text-sky-200"
  }[tone];

  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ duration: 0.18 }}
      className={`min-h-[122px] rounded-md border p-4 ${toneClass}`}
    >
      <div className="mb-4 flex items-center justify-between text-current/78">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className="text-xl font-semibold tracking-normal text-foreground">{value}</div>
      <div className="mt-1 text-sm text-current/70">{detail}</div>
    </motion.div>
  );
}

function OverviewTile({
  label,
  value,
  detail,
  tone,
  icon
}: {
  label: string;
  value: string;
  detail: string;
  tone: string;
  icon: React.ReactNode;
}) {
  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ duration: 0.18 }}
      className={`min-h-[124px] rounded-md border border-cyan-200/14 bg-gradient-to-br p-4 ${tone}`}
    >
      <div className="mb-4 flex items-center justify-between text-muted">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className="text-2xl font-semibold tracking-normal">{value}</div>
      <div className="mt-1 text-sm text-muted">{detail}</div>
    </motion.div>
  );
}

function ReportSectionShell({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18, scale: 0.975, rotateX: -6, filter: "blur(7px)" }}
      animate={{ opacity: 1, y: 0, scale: 1, rotateX: 0, filter: "blur(0px)" }}
      exit={{ opacity: 0, y: -10, scale: 0.985, rotateX: 4, filter: "blur(6px)" }}
      transition={{ duration: 0.32, ease: "easeOut" }}
      className="grid gap-4"
    >
      {children}
    </motion.div>
  );
}

function CapitalBar({ label, value, total, tone }: { label: string; value: number; total: number; tone: string }) {
  const pct = total > 0 ? Math.min(100, (value / total) * 100) : 0;
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span>{formatCurrency(value)}</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-black/40">
        <div className={`h-3 rounded-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function PositionDrilldown({
  holding,
  recommendation,
  stressPct
}: {
  holding?: Holding;
  recommendation?: PortfolioIntelligence["recommendations"][number];
  stressPct: number;
}) {
  if (!holding) {
    return (
      <div className="rounded-md border border-border bg-white/5 p-4 text-sm text-muted">
        Select a holding to inspect the advisor view.
      </div>
    );
  }

  const stressLoss = holding.marketValue * (Math.abs(stressPct) / 100);
  const call = recommendation?.recommendation ?? getFallbackCall(holding);

  return (
    <div className="rounded-md border border-border bg-[linear-gradient(160deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-xl font-semibold">{holding.symbol}</h4>
          <p className="text-sm text-muted">{holding.companyName}</p>
        </div>
        <RecommendationPill recommendation={call} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <ReportFact label="Market value" value={formatCurrency(holding.marketValue)} />
        <ReportFact label="Allocation" value={`${holding.allocationPct.toFixed(1)}%`} />
        <ReportFact label="Total P&L" value={formatCurrency(holding.totalPnl)} tone={holding.totalPnl >= 0 ? "text-profit" : "text-loss"} />
        <ReportFact label="Stress loss" value={formatCurrency(stressLoss)} tone="text-loss" />
      </div>
      <div className="mt-4 rounded-md border border-border bg-black/30 p-3">
        <div className="mb-1 text-xs text-muted">Advisor watch</div>
        <p className="text-sm leading-6 text-foreground/84">
          {recommendation?.whatChanged ?? getFallbackWatch(holding)}
        </p>
      </div>
      {recommendation ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <SignalList title="Bullish factors" items={recommendation.bullishFactors} tone="text-profit" />
          <SignalList title="Key risks" items={recommendation.keyRisks.length ? recommendation.keyRisks : recommendation.bearishFactors} tone="text-loss" />
        </div>
      ) : null}
    </div>
  );
}

function SignalList({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <div className="rounded-md border border-border bg-white/5 p-3">
      <div className={`mb-2 text-sm font-medium ${tone}`}>{title}</div>
      <div className="space-y-2">
        {items.slice(0, 3).map((item) => (
          <div key={item} className="text-sm leading-5 text-muted">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

function ReportKpi({
  label,
  value,
  detail,
  tone = "text-foreground",
  icon
}: {
  label: string;
  value: string;
  detail: string;
  tone?: string;
  icon: React.ReactNode;
}) {
  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ duration: 0.18 }}
      className="min-h-[118px] rounded-md border border-violet-200/14 bg-white/[0.045] p-4"
    >
      <div className="mb-3 flex items-center justify-between text-muted">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className={`text-xl font-semibold tracking-normal ${tone}`}>{value}</div>
      <div className="mt-1 text-sm text-muted">{detail}</div>
    </motion.div>
  );
}

function ReportFact({ label, value, tone = "text-foreground" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-md border border-border bg-white/5 p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={`mt-1 text-sm font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

function ReportNote({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <Card>
      <div className="mb-3 flex items-center gap-2 text-accent">
        {icon}
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
      </div>
      <p className="text-sm leading-6 text-foreground/82">{text}</p>
    </Card>
  );
}

function ReportInsightBlock({
  title,
  items,
  tone,
  emptyText = "Generate AI analysis to populate this section."
}: {
  title: string;
  items: string[];
  tone: string;
  emptyText?: string;
}) {
  return (
    <div className="rounded-md border border-violet-200/12 bg-black/22 p-4">
      <h4 className={`mb-3 text-sm font-semibold ${tone}`}>{title}</h4>
      <div className="space-y-2">
        {items.length ? (
          items.slice(0, 5).map((item, index) => (
            <div key={`${item}-${index}`} className="rounded-md border border-white/10 bg-white/[0.035] p-3 text-sm leading-5 text-muted">
              <AiFormattedText text={item} />
            </div>
          ))
        ) : (
          <div className="text-sm leading-5 text-muted">{emptyText}</div>
        )}
      </div>
    </div>
  );
}

function AiFormattedText({ text, className = "" }: { text: string; className?: string }) {
  const parts = formatAiText(text);
  if (!parts.length) {
    return <span className={className}>Not available.</span>;
  }
  if (parts.length === 1) {
    return <span className={className}>{parts[0]}</span>;
  }
  return (
    <div className={`space-y-2 ${className}`}>
      {parts.map((part, index) => (
        <p key={`${part}-${index}`}>{part}</p>
      ))}
    </div>
  );
}

function formatAiText(text: string) {
  return text
    .replaceAll("**", "")
    .replaceAll("__", "")
    .replaceAll("`", "")
    .split(/\n+|(?<=\.)\s+(?=[A-Z0-9]{2,12}:)/)
    .map((part) =>
      part
        .trim()
        .replace(/^[-*•]\s+/, "")
        .replace(/^\d+[.)]\s+/, "")
        .replace(/\s+/g, " ")
    )
    .filter(Boolean);
}

function SeverityPill({ severity }: { severity: "low" | "medium" | "high" }) {
  const className =
    severity === "high"
      ? "border-loss/40 bg-loss/10 text-loss"
      : severity === "medium"
        ? "border-amber/40 bg-amber/10 text-amber"
        : "border-accent/40 bg-accent/10 text-accent";

  return <span className={`rounded-md border px-2 py-1 text-xs capitalize ${className}`}>{severity}</span>;
}

function PriorityPill({ priority }: { priority: ReportAction["priority"] }) {
  const className =
    priority === "High"
      ? "border-loss/40 bg-loss/10 text-loss"
      : priority === "Medium"
        ? "border-amber/40 bg-amber/10 text-amber"
        : "border-accent/40 bg-accent/10 text-accent";

  return <span className={`h-fit rounded-md border px-2 py-1 text-center text-xs font-medium ${className}`}>{priority}</span>;
}

function RecommendationPill({ recommendation }: { recommendation: string }) {
  const normalized = recommendation.toUpperCase();
  const className = isReduceCall(normalized)
    ? "border-loss/40 bg-loss/10 text-loss"
    : isAddCall(normalized)
      ? "border-profit/40 bg-profit/10 text-profit"
      : "border-border bg-white/5 text-foreground";

  return <span className={`rounded-md border px-2 py-1 text-xs font-medium ${className}`}>{recommendation}</span>;
}

function getPortfolioVerdict(healthScore: number, concentrationPct: number, highRiskCount: number, cashPct: number) {
  if (highRiskCount > 0 || concentrationPct > 65) {
    return {
      label: "Defensive review",
      detail: "Risk needs attention before fresh buying",
      tone: "text-amber"
    };
  }
  if (healthScore >= 80 && cashPct >= 8) {
    return {
      label: "Accumulate selectively",
      detail: "Healthy core with room for measured adds",
      tone: "text-profit"
    };
  }
  if (healthScore >= 65) {
    return {
      label: "Hold with rotation",
      detail: "Keep winners, rotate weak or crowded exposure",
      tone: "text-accent"
    };
  }
  return {
    label: "Repair portfolio",
    detail: "Reduce weak names and rebuild cash discipline",
    tone: "text-loss"
  };
}

function getDecisionGrade(qualityScore: number, healthScore: number, concentrationPct: number, highRiskCount: number) {
  if (qualityScore < 55) {
    return {
      label: "Watchlist",
      call: "Do not act yet",
      detail: "Evidence is not strong enough for buy/sell action.",
      tone: "text-loss"
    };
  }
  if (highRiskCount > 0 || concentrationPct > 60) {
    return {
      label: "Risk first",
      call: "Repair before adding",
      detail: "Position sizing or alert severity needs attention.",
      tone: "text-amber"
    };
  }
  if (qualityScore >= 75 && healthScore >= 72) {
    return {
      label: "Staged action",
      call: "Actionable shortlist",
      detail: "Use tranches after valuation and trend confirmation.",
      tone: "text-profit"
    };
  }
  return {
    label: "Verify",
    call: "Review before action",
    detail: "Good enough for screening, not enough for blind execution.",
    tone: "text-cyan-100"
  };
}

function getInvestorProfileConfig(riskProfile: InvestorRiskProfile, horizon: InvestorHorizon) {
  const horizonText = {
    short: "short-term trades need stricter price confirmation",
    swing: "swing trades need trend and result confirmation",
    long: "long-term investing needs business quality and valuation comfort"
  }[horizon];

  if (riskProfile === "conservative") {
    return {
      label: "Conservative",
      rule: `Show low-risk candidates first; ${horizonText}.`,
      allows: (risk: string) => risk === "Low"
    };
  }
  if (riskProfile === "aggressive") {
    return {
      label: "Aggressive",
      rule: `Allow higher-risk ideas, but use smaller starter sizes; ${horizonText}.`,
      allows: () => true
    };
  }
  return {
    label: "Balanced",
    rule: `Prefer low/medium-risk candidates; ${horizonText}.`,
    allows: (risk: string) => risk !== "High"
  };
}

function getDiscoveryValidity(validUntil?: string) {
  if (!validUntil) {
    return { expired: false, label: "Waiting for scan", shortLabel: "Pending" };
  }
  const expiry = new Date(validUntil).getTime();
  const remainingMs = expiry - Date.now();
  if (Number.isNaN(expiry) || remainingMs <= 0) {
    return { expired: true, label: "Expired. Refresh now for new shares.", shortLabel: "Expired" };
  }
  const hours = Math.ceil(remainingMs / (1000 * 60 * 60));
  const days = Math.floor(hours / 24);
  const remainderHours = hours % 24;
  const label = days > 0 ? `${days}d ${remainderHours}h left` : `${hours}h left`;
  return { expired: false, label: `Valid for ${label}`, shortLabel: label };
}

function recommendedStarterSize(capital: number, riskLevel: string, profile: InvestorRiskProfile) {
  const profilePct = profile === "conservative" ? 0.04 : profile === "aggressive" ? 0.075 : 0.055;
  const riskMultiplier = riskLevel === "High" ? 0.35 : riskLevel === "Medium" ? 0.7 : 1;
  return Math.max(0, capital * profilePct * riskMultiplier);
}

function riskPill(riskLevel: string) {
  if (riskLevel === "High") {
    return "border-loss/30 bg-loss/10 text-loss";
  }
  if (riskLevel === "Medium") {
    return "border-amber/30 bg-amber/10 text-amber";
  }
  return "border-profit/30 bg-profit/10 text-profit";
}

function buildReportActions(data: PortfolioSummary, intelligence?: PortfolioIntelligence): ReportAction[] {
  const actions: ReportAction[] = [];
  const topHolding = [...data.holdings].sort((a, b) => b.allocationPct - a.allocationPct)[0];
  const largestSector = [...data.sectorAllocation].sort((a, b) => b.percentage - a.percentage)[0];
  const totalCapital = data.portfolioValue + data.cashBalance;
  const cashPct = totalCapital > 0 ? (data.cashBalance / totalCapital) * 100 : 0;

  intelligence?.alerts
    .filter((alert) => alert.severity === "high")
    .slice(0, 2)
    .forEach((alert) => {
      actions.push({
        priority: "High",
        title: `${alert.symbol ?? "Portfolio"} risk action`,
        reason: alert.message,
        timing: alert.action
      });
    });

  intelligence?.recommendations
    .filter((item) => isReduceCall(item.recommendation))
    .slice(0, 2)
    .forEach((item) => {
      actions.push({
        priority: "High",
        title: `Trim or review ${item.symbol}`,
        reason: item.reasoning || `${item.symbol} has an elevated risk/reward profile.`,
        timing: "Act in phases; avoid selling only because of one weak session."
      });
    });

  if (topHolding && topHolding.allocationPct > 22) {
    actions.push({
      priority: "Medium",
      title: `Cap ${topHolding.symbol} exposure`,
      reason: `${topHolding.symbol} is ${topHolding.allocationPct.toFixed(1)}% of portfolio value. Keep position sizing disciplined even when the stock is working.`,
      timing: "Do not add above the current weight unless portfolio size or conviction materially changes."
    });
  }

  if (largestSector && largestSector.percentage >= 25) {
    actions.push({
      priority: "Medium",
      title: `Rebalance ${largestSector.label}`,
      reason: `${largestSector.label} is above the 25% review band. Sector concentration can hide correlated downside.`,
      timing: "Use rallies or new cash deployment to bring the weight closer to plan."
    });
  }

  intelligence?.recommendations
    .filter((item) => isAddCall(item.recommendation))
    .slice(0, 2)
    .forEach((item) => {
      actions.push({
        priority: "Low",
        title: `Add only on setup: ${item.symbol}`,
        reason: item.reasoning || `${item.symbol} has a favourable recommendation, but entry price still matters.`,
        timing: "Accumulate in tranches after checking valuation, trend and upcoming event risk."
      });
    });

  if (cashPct < 6) {
    actions.push({
      priority: "Medium",
      title: "Rebuild cash buffer",
      reason: `Cash is only ${cashPct.toFixed(1)}% of total capital. A portfolio without cash loses optionality during corrections.`,
      timing: "Target an 8-12% buffer before aggressive fresh deployment."
    });
  }

  if (actions.length === 0) {
    actions.push({
      priority: "Low",
      title: "Maintain the current portfolio plan",
      reason: "No urgent risk signal was detected. Keep reviewing earnings, allocation and price trend before adding fresh capital.",
      timing: "Review again after major results, policy events or a 5% portfolio move."
    });
  }

  return actions.slice(0, 6);
}

function buildFallbackAlerts(data: PortfolioSummary): PortfolioIntelligence["alerts"] {
  const topHolding = [...data.holdings].sort((a, b) => b.allocationPct - a.allocationPct)[0];
  const largestSector = [...data.sectorAllocation].sort((a, b) => b.percentage - a.percentage)[0];
  const alerts: PortfolioIntelligence["alerts"] = [];

  if (topHolding) {
    alerts.push({
      severity: topHolding.allocationPct > 22 ? "medium" : "low",
      alertType: "position_concentration",
      symbol: topHolding.symbol,
      message: `${topHolding.symbol} is the largest position at ${topHolding.allocationPct.toFixed(1)}% of portfolio value.`,
      action: "Review sizing before adding more capital to the same name."
    });
  }

  if (largestSector) {
    alerts.push({
      severity: largestSector.percentage >= 25 ? "medium" : "low",
      alertType: "sector_concentration",
      symbol: null,
      message: `${largestSector.label} is the largest sector exposure at ${largestSector.percentage.toFixed(1)}%.`,
      action: "Compare this weight with your target allocation and risk appetite."
    });
  }

  return alerts;
}

function getFallbackCall(holding: Holding) {
  if (holding.allocationPct > 22) {
    return "HOLD / CAP";
  }
  if (holding.totalPnl < 0) {
    return "REVIEW";
  }
  return "HOLD";
}

function getFallbackRisk(holding: Holding) {
  const concentrationRisk = holding.allocationPct > 22 ? 72 : holding.allocationPct > 16 ? 58 : 42;
  const lossRisk = holding.totalPnl < 0 ? 12 : 0;
  return Math.min(95, concentrationRisk + lossRisk);
}

function getFallbackWatch(holding: Holding) {
  if (holding.allocationPct > 22) {
    return "Position size is near the review band; avoid averaging up blindly.";
  }
  if (holding.totalPnl < 0) {
    return "Price action is weak versus cost; check thesis and stop discipline.";
  }
  return "Track earnings, valuation comfort and sector momentum.";
}

function getMarketPosture(healthScore: number, pnlPct: number, cashPct: number) {
  if (healthScore >= 80 && pnlPct > 0 && cashPct >= 8) {
    return "The portfolio can stay invested, but fresh buying should be selective and staged rather than broad-based.";
  }
  if (cashPct < 6) {
    return "The first job is to rebuild optional cash, then deploy into high-conviction names during volatility.";
  }
  if (pnlPct < 0) {
    return "Treat this as a repair phase: protect capital, cut broken theses and avoid averaging down without fresh evidence.";
  }
  return "Maintain exposure, rotate away from weak risk/reward pockets and keep cash ready for dislocations.";
}

function buildReviewRhythm(
  data: PortfolioSummary,
  intelligence?: PortfolioIntelligence,
  analytics?: PortfolioAnalytics
) {
  const topHolding = [...data.holdings].sort((a, b) => b.allocationPct - a.allocationPct)[0];
  const qualityScore = intelligence?.dataQuality.score ?? analytics?.dataQualityScore ?? 0;
  const sanityIssues = analytics?.sanityChecks.filter((check) => check.status !== "pass") ?? [];
  const rhythm = [
    "Morning: verify live prices, data quality and any overnight news before adding fresh capital.",
    "Weekly: review top position weight, sector weight and stop/review levels for every weak holding.",
    "Monthly: compare holdings against thesis, valuation comfort, cash-flow quality and portfolio concentration."
  ];

  if (topHolding && topHolding.allocationPct > 20) {
    rhythm.unshift(`${topHolding.symbol}: review position size before adding because it is ${topHolding.allocationPct.toFixed(1)}% of portfolio.`);
  }
  if (qualityScore < 70) {
    rhythm.unshift("Data quality: improve broker sync, fundamentals and technical coverage before treating calls as actionable.");
  }
  if (sanityIssues.length) {
    rhythm.unshift(`${sanityIssues[0].label}: ${sanityIssues[0].detail}`);
  }

  return rhythm.slice(0, 6);
}

function isReduceCall(recommendation: string) {
  const normalized = recommendation.toUpperCase();
  return normalized.includes("REDUCE") || normalized.includes("SELL") || normalized.includes("EXIT") || normalized.includes("TRIM");
}

function isAddCall(recommendation: string) {
  const normalized = recommendation.toUpperCase();
  return normalized.includes("BUY") || normalized.includes("ADD") || normalized.includes("ACCUMULATE");
}
