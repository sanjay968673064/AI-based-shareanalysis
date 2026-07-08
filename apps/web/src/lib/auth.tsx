"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "portfolio-auth-token";

export type AuthUser = {
  id: string;
  email: string | null;
  fullName: string | null;
  tenantId: string;
};

type AuthSession = {
  token: string;
  expiresAt: string;
  user: AuthUser;
};

type AuthMode = "login" | "register";

type AuthContextValue = {
  token: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (input: { email: string; password: string; fullName: string }) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function getAuthToken() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(TOKEN_KEY);
}

export function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getAuthToken();
  return {
    ...(extra ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const savedToken = getAuthToken();
    if (!savedToken) {
      setIsLoading(false);
      return;
    }
    setToken(savedToken);
    fetch(`${apiBaseUrl}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${savedToken}` },
      cache: "no-store"
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Session expired.");
        }
        return response.json() as Promise<AuthUser>;
      })
      .then(setUser)
      .catch(() => {
        window.localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function applySession(session: AuthSession) {
    window.localStorage.setItem(TOKEN_KEY, session.token);
    setToken(session.token);
    setUser(session.user);
  }

  const submitAuth = useCallback(async (path: string, payload: Record<string, string>) => {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(typeof body?.detail === "string" ? body.detail : "Authentication failed.");
    }
    await applySession((await response.json()) as AuthSession);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      isLoading,
      login: (email, password) => submitAuth("/api/v1/auth/login", { email, password }),
      register: (input) => submitAuth("/api/v1/auth/register", input),
      logout: async () => {
        const savedToken = getAuthToken();
        if (savedToken) {
          await fetch(`${apiBaseUrl}/api/v1/auth/logout`, {
            method: "POST",
            headers: { Authorization: `Bearer ${savedToken}` }
          }).catch(() => undefined);
        }
        window.localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      }
    }),
    [isLoading, submitAuth, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  if (auth.isLoading) {
    return (
      <main className="grid min-h-screen place-items-center bg-background px-4">
        <div className="rounded-md border border-border bg-panel px-4 py-3 text-sm text-muted">Checking session...</div>
      </main>
    );
  }
  if (!auth.user || !auth.token) {
    return <AuthScreen />;
  }
  return <>{children}</>;
}

function AuthScreen() {
  const auth = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      if (mode === "register") {
        await auth.register({ email, password, fullName });
      } else {
        await auth.login(email, password);
      }
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : "Unable to sign in.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(45,212,191,0.16),transparent_32%),#080a0e] px-4 py-8">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] w-full max-w-5xl items-center gap-6 lg:grid-cols-[1fr_420px]">
        <section>
          <div className="mb-3 inline-flex rounded-md border border-accent/20 bg-accent/10 px-3 py-1 text-sm text-accent">
            Read-only portfolio intelligence
          </div>
          <h1 className="max-w-2xl text-4xl font-semibold tracking-normal text-foreground">
            Sign in before syncing real holdings.
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted">
            Your Zerodha, Groww, CSV and AI settings should belong to your account only. This login layer keeps portfolio data separated per tenant before the advisor shows any buy, hold or review signal.
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            <AuthBenefit title="Private tenant" detail="Every account gets separate holdings and settings." />
            <AuthBenefit title="Advisory only" detail="No trade execution is enabled from this app." />
            <AuthBenefit title="Evidence first" detail="Signals include confidence and data-quality warnings." />
          </div>
        </section>

        <form onSubmit={handleSubmit} className="rounded-lg border border-border bg-panel p-5 shadow-glow">
          <div className="mb-5">
            <h2 className="text-xl font-semibold">{mode === "login" ? "Welcome back" : "Create your account"}</h2>
            <p className="mt-1 text-sm text-muted">
              {mode === "login" ? "Use your app account to open the dashboard." : "Start with an empty private portfolio."}
            </p>
          </div>

          <div className="mb-4 inline-flex w-full rounded-md border border-border bg-black/30 p-1">
            {(["login", "register"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setMode(item)}
                className={`h-9 flex-1 rounded text-sm capitalize transition ${
                  mode === item ? "bg-accent text-black" : "text-muted hover:text-foreground"
                }`}
              >
                {item}
              </button>
            ))}
          </div>

          {mode === "register" ? (
            <label className="mb-3 block">
              <span className="mb-2 block text-sm text-muted">Full name</span>
              <input
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required
                className="w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm outline-none transition focus:border-accent"
              />
            </label>
          ) : null}

          <label className="mb-3 block">
            <span className="mb-2 block text-sm text-muted">Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              className="w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm outline-none transition focus:border-accent"
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm text-muted">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={mode === "register" ? 8 : 1}
              required
              className="w-full rounded-md border border-border bg-black/30 px-3 py-2 text-sm outline-none transition focus:border-accent"
            />
          </label>

          {error ? <div className="mt-4 rounded-md border border-loss/20 bg-loss/10 p-3 text-sm text-loss">{error}</div> : null}

          <Button type="submit" className="mt-5 w-full" disabled={isSubmitting || !email || !password || (mode === "register" && !fullName)}>
            {isSubmitting ? "Please wait" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
      </div>
    </main>
  );
}

function AuthBenefit({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-md border border-border bg-white/[0.045] p-4">
      <div className="text-sm font-medium text-foreground">{title}</div>
      <div className="mt-2 text-sm leading-5 text-muted">{detail}</div>
    </div>
  );
}
