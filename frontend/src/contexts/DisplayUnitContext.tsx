import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { summary, monthlyMetrics } from "@/lib/metrics";

export type DisplayUnit = "tokens" | "dollars";

interface DisplayUnitContextValue {
  unit: DisplayUnit;
  setUnit: (u: DisplayUnit) => void;
  toggle: () => void;
  /** USD cost per single token, derived from latest month spend / latest month tokens */
  costPerToken: number;
}

const STORAGE_KEY = "paretokens.displayUnit";

// Derive $ per token from latest monthly tokens vs the executive monthly spend.
// Latest month total tokens / monthly_ai_spend_total => cost per token (USD).
function deriveCostPerToken(): number {
  const latest = monthlyMetrics[monthlyMetrics.length - 1];
  if (!latest) return 0;
  const totalTokens = latest.employees.reduce((acc, e) => acc + e.tokens_used, 0);
  if (totalTokens <= 0) return 0;
  return summary.monthly_ai_spend_total / totalTokens;
}

const COST_PER_TOKEN = deriveCostPerToken();

const DisplayUnitContext = createContext<DisplayUnitContextValue | null>(null);

export function DisplayUnitProvider({ children }: { children: ReactNode }) {
  const [unit, setUnitState] = useState<DisplayUnit>("tokens");

  // Hydrate from localStorage after mount (avoids SSR mismatch).
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "tokens" || saved === "dollars") setUnitState(saved);
    } catch {
      /* ignore */
    }
  }, []);

  const setUnit = (u: DisplayUnit) => {
    setUnitState(u);
    try {
      localStorage.setItem(STORAGE_KEY, u);
    } catch {
      /* ignore */
    }
  };

  const toggle = () => setUnit(unit === "tokens" ? "dollars" : "tokens");

  return (
    <DisplayUnitContext.Provider value={{ unit, setUnit, toggle, costPerToken: COST_PER_TOKEN }}>
      {children}
    </DisplayUnitContext.Provider>
  );
}

export function useDisplayUnit(): DisplayUnitContextValue {
  const ctx = useContext(DisplayUnitContext);
  if (!ctx) {
    // Fallback for components rendered outside provider — default to tokens.
    return { unit: "tokens", setUnit: () => {}, toggle: () => {}, costPerToken: COST_PER_TOKEN };
  }
  return ctx;
}

// ---- Formatters -----------------------------------------------------------

export function tokensToDollars(tokens: number): number {
  return tokens * COST_PER_TOKEN;
}

export function formatDollars(amount: number): string {
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `$${(amount / 1_000).toFixed(amount >= 10_000 ? 0 : 1)}k`;
  if (amount >= 10) return `$${amount.toFixed(0)}`;
  if (amount >= 1) return `$${amount.toFixed(2)}`;
  return `$${amount.toFixed(2)}`;
}

/** Long $ form for tooltips: "$12,345" */
export function formatDollarsFull(amount: number): string {
  return `$${Math.round(amount).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;
}

/** Hook returning a formatter that respects the current display unit. */
export function useTokenFormatter() {
  const { unit, costPerToken } = useDisplayUnit();
  return {
    unit,
    /** Short form, e.g. "1.2M" tokens or "$12k" */
    format: (tokens: number) => {
      if (unit === "dollars") return formatDollars(tokens * costPerToken);
      // tokens short form
      if (tokens >= 1_000_000_000) return `${(tokens / 1_000_000_000).toFixed(1)}B`;
      if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
      if (tokens >= 1_000) return `${(tokens / 1_000).toFixed(0)}k`;
      return `${tokens}`;
    },
    /** Full form for tooltips: "1,234,567 tokens" or "$9,876" */
    formatFull: (tokens: number) => {
      if (unit === "dollars") return formatDollarsFull(tokens * costPerToken);
      return `${tokens.toLocaleString("en-US")} tokens`;
    },
    /** Suffix label */
    label: unit === "dollars" ? "USD" : "tokens",
  };
}
