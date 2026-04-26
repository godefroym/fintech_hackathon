import data from "@/data/metrics.json";

export type Category =
  | "high_roi"
  | "efficient_user"
  | "average_user"
  | "low_adoption"
  | "overspender"
  | "quality_risk";

export interface Employee {
  name: string;
  category: Category;
  month: string;
  tokens_used: number;
  story_points: number;
  tickets_resolved: number;
  time_to_completion_days: number;
  bugs_closed: number;
  lines_of_code: number;
  merge_requests: number;
  merge_requests_per_ticket: number;
  recommendation: string;
}

export function findEmployee(name: string): Employee | undefined {
  return employees.find((e) => e.name.toLowerCase() === name.toLowerCase());
}

export function employeeSlug(name: string): string {
  return encodeURIComponent(name);
}

export interface MonthlyEmployee {
  name: string;
  tokens_used: number;
  story_points: number;
}

export interface MonthlyMetric {
  month: string; // YYYY-MM
  employees: MonthlyEmployee[];
}

export const employees = data.employee_metrics as Employee[];

export const monthlyMetrics = data.monthly_metrics as MonthlyMetric[];

export const summary = data.executive_summary as {
  monthly_ai_spend_total: number;
  forecast_next_month_ai_spend: number;
  monthly_ai_spend_growth_percent: number;
  budget_usage_percent: number;
  productivity_gain_percent: number;
  bugs_reduction_percent: number;
  currency: string;
  main_recommendation: string;
};

export const categoryMeta: Record<Category, { label: string; color: string; token: string }> = {
  high_roi: {
    label: "High ROI",
    color: "var(--cat-high-roi)",
    token: "cat-high-roi",
  },
  efficient_user: {
    label: "Efficient user",
    color: "var(--cat-efficient)",
    token: "cat-efficient",
  },
  average_user: {
    label: "Average user",
    color: "var(--cat-average)",
    token: "cat-average",
  },
  low_adoption: {
    label: "Low adoption",
    color: "var(--cat-low-adoption)",
    token: "cat-low-adoption",
  },
  overspender: {
    label: "Overspender",
    color: "var(--cat-overspender)",
    token: "cat-overspender",
  },
  quality_risk: {
    label: "Quality risk",
    color: "var(--cat-quality-risk)",
    token: "cat-quality-risk",
  },
};

// Helpers --------------------------------------------------------------------

export const formatNumber = (n: number) =>
  n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : `${n}`;

export const formatTokens = (n: number) => {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return `${n}`;
};

// Sorted ascending by month
export const monthsSorted = [...monthlyMetrics].sort((a, b) => a.month.localeCompare(b.month));

export const latestMonth = monthsSorted[monthsSorted.length - 1];

export function monthLabel(month: string): string {
  // "2025-03" -> "Mar 2025"
  const [y, m] = month.split("-").map(Number);
  const date = new Date(Date.UTC(y, (m ?? 1) - 1, 1));
  return date.toLocaleString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

export function getEmployeeMonthly(name: string, month: string): MonthlyEmployee | undefined {
  return monthlyMetrics.find((m) => m.month === month)?.employees.find((e) => e.name === name);
}

// Explicit gender map for deterministic, correct avatar selection.
// "Camille" and "Alix" are unisex — assigned arbitrarily but stably.
const GENDER_BY_FIRST_NAME: Record<string, "men" | "women"> = {
  Adrien: "men",
  Alexandre: "men",
  Alix: "women",
  Amina: "women",
  Antoine: "men",
  Baptiste: "men",
  Camille: "women",
  Chloe: "women",
  Clara: "women",
  Eva: "women",
  Fatima: "women",
  Florian: "men",
  Hugo: "men",
  Ines: "women",
  Jade: "women",
  Jules: "men",
  Julien: "men",
  Laure: "women",
  Leila: "women",
  Lena: "women",
  Lucas: "men",
  Maxime: "men",
  Maya: "women",
  Nadia: "women",
  Nicolas: "men",
  Nina: "women",
  Omar: "men",
  Pierre: "men",
  Quentin: "men",
  Remy: "men",
  Romain: "men",
  Sara: "women",
  Simon: "men",
  Sofia: "women",
  Theo: "men",
  Thomas: "men",
  Victor: "men",
  Yasmine: "women",
  Yuna: "women",
  Zoe: "women",
};

function guessGender(firstName: string): "men" | "women" {
  if (GENDER_BY_FIRST_NAME[firstName]) return GENDER_BY_FIRST_NAME[firstName];
  // Heuristic fallback: French female first names commonly end in a/e/i.
  const last = firstName.slice(-1).toLowerCase();
  return ["a", "e", "i"].includes(last) ? "women" : "men";
}

// Stable avatar URL from name (gender-aware + deterministic index for randomuser.me)
export function avatarUrl(name: string): string {
  const first = name.split(" ")[0] ?? name;
  const gender = guessGender(first);
  const num = (name.charCodeAt(0) * 7 + name.length * 13) % 99;
  return `https://randomuser.me/api/portraits/${gender}/${num}.jpg`;
}

