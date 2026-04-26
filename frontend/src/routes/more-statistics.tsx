import { useMemo } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Cpu,
  GraduationCap,
  Sparkles,
} from "lucide-react";
import { Header } from "@/components/Header";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { ChartCard } from "@/components/dashboard/ChartCard";
import { employees, formatTokens } from "@/lib/metrics";
import { useTokenFormatter } from "@/contexts/DisplayUnitContext";

export const Route = createFileRoute("/more-statistics")({
  head: () => ({
    meta: [
      { title: "More statistics — Paretokens" },
      {
        name: "description",
        content:
          "Deeper breakdowns of token spend by AI model, employee seniority, and shipped features.",
      },
      { property: "og:title", content: "More statistics — Paretokens" },
      {
        property: "og:description",
        content:
          "Deeper breakdowns of token spend by AI model, employee seniority, and shipped features.",
      },
    ],
  }),
  component: MoreStatisticsPage,
});

const tooltipStyle = {
  backgroundColor: "oklch(1 0 0)",
  border: "1px solid oklch(0.92 0.008 320)",
  borderRadius: 12,
  color: "oklch(0.18 0.02 285)",
  fontSize: 12,
  padding: "8px 12px",
  boxShadow: "0 10px 30px -10px oklch(0.55 0.24 305 / 0.2)",
};
const axisStroke = "oklch(0.55 0.02 285)";
const gridStroke = "oklch(0.92 0.008 320)";

// Locale-stable integer formatter (avoids SSR/CSR hydration mismatches).
const fmtInt = (n: number) => n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");

// ---------- 1. Tokens vs Models -------------------------------------------

const MODELS = [
  { key: "claude-sonnet-4.5", label: "Claude Sonnet 4.5", color: "oklch(0.55 0.24 305)" }, // deep violet
  { key: "gpt-5", label: "GPT-5", color: "oklch(0.7 0.24 350)" }, // hot pink
  { key: "gemini-2.5-pro", label: "Gemini 2.5 Pro", color: "oklch(0.65 0.20 340)" }, // mauve
  { key: "claude-haiku", label: "Claude Haiku", color: "oklch(0.78 0.16 355)" }, // soft pink
  { key: "gpt-5-mini", label: "GPT-5 Mini", color: "oklch(0.78 0.14 320)" }, // light pink-violet
];

function buildModelData() {
  const totalTokens = employees.reduce((acc, e) => acc + e.tokens_used, 0);
  // Invented but plausible split
  const splits = [0.42, 0.27, 0.16, 0.1, 0.05];
  const costPerM = [3.0, 2.5, 1.8, 0.25, 0.4]; // $ per 1M tokens (invented)
  return MODELS.map((m, i) => {
    const tokens = Math.round(totalTokens * splits[i]);
    return {
      model: m.label,
      key: m.key,
      color: m.color,
      tokens,
      cost: +(tokens / 1_000_000 * costPerM[i]).toFixed(0),
      share: +(splits[i] * 100).toFixed(1),
    };
  });
}

function TokensVsModels() {
  const data = useMemo(buildModelData, []);
  const tk = useTokenFormatter();
  return (
    <ChartCard
      title="Tokens vs AI models"
      subtitle="Where the team's token budget actually goes, by underlying model"
    >
      <div className="grid gap-6 lg:grid-cols-2">
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={data}
              dataKey="tokens"
              nameKey="model"
              innerRadius={60}
              outerRadius={110}
              paddingAngle={3}
              stroke="none"
            >
              {data.map((d) => (
                <Cell key={d.key} fill={d.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={tooltipStyle}
              formatter={(v: number, _n, item) => [
                `${tk.format(v)}${tk.unit === "tokens" ? " tokens" : ""} (${(item.payload as { share: number }).share}%)`,
                item.payload.model as string,
              ]}
            />
          </PieChart>
        </ResponsiveContainer>

        <div className="flex flex-col justify-center gap-2">
          {data.map((d) => (
            <div
              key={d.key}
              className="flex items-center justify-between gap-3 rounded-lg border border-border/60 bg-background/40 px-3 py-2"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span
                  className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                  style={{ background: d.color }}
                />
                <span className="text-sm font-medium text-foreground truncate">{d.model}</span>
              </div>
              <div className="flex items-center gap-3 text-xs tabular-nums">
                <span className="text-muted-foreground">{tk.format(d.tokens)}</span>
                <span className="font-semibold text-foreground">${fmtInt(d.cost)}</span>
              </div>
            </div>
          ))}
          <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
            Premium reasoning models (Sonnet, GPT-5) drive ~70% of spend while only powering
            ~45% of completions. A routing strategy could shift simple tasks to Haiku / Mini.
          </p>
        </div>
      </div>
    </ChartCard>
  );
}

// ---------- 2. Tokens vs Seniority / Skills -------------------------------

interface DevProfile {
  name: string;
  seniority: number; // years
  skill: number;    // 0-100 background score
  tokens: number;
}

function buildSeniorityData(): DevProfile[] {
  return employees.map((e, i) => {
    // Deterministic "invented" seniority + skill score from the name
    const seed = e.name.charCodeAt(0) + e.name.length * 3 + i;
    const seniority = +(((seed % 12) + 1).toFixed(1)); // 1 - 12 years
    const skill = 35 + ((seed * 7) % 60); // 35 - 95
    return {
      name: e.name,
      seniority,
      skill,
      tokens: e.tokens_used,
    };
  });
}

function TokensVsSeniority() {
  const data = useMemo(buildSeniorityData, []);
  const tk = useTokenFormatter();

  // Bucket by seniority for the bar chart
  const buckets = useMemo(() => {
    const groups = [
      { label: "Junior (0-2y)", min: 0, max: 2 },
      { label: "Mid (3-5y)", min: 3, max: 5 },
      { label: "Senior (6-9y)", min: 6, max: 9 },
      { label: "Staff+ (10y+)", min: 10, max: Infinity },
    ];
    return groups.map((g) => {
      const inGroup = data.filter((d) => d.seniority >= g.min && d.seniority <= g.max);
      const tokens = inGroup.reduce((a, d) => a + d.tokens, 0);
      const avg = inGroup.length ? Math.round(tokens / inGroup.length) : 0;
      return {
        label: g.label,
        avgTokens: avg,
        count: inGroup.length,
      };
    });
  }, [data]);

  return (
    <ChartCard
      title={tk.unit === "dollars" ? "$ spent vs seniority" : "Tokens vs seniority"}
      subtitle="Are senior devs more efficient with AI — or do juniors lean on it more?"
    >
      <div className="mb-2 text-xs font-semibold text-muted-foreground">
        {tk.unit === "dollars" ? "Average monthly $ by seniority bucket" : "Average monthly tokens by seniority bucket"}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={buckets} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <defs>
            <linearGradient id="senBar" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="oklch(0.7 0.24 350)" stopOpacity={0.95} />
              <stop offset="100%" stopColor="oklch(0.55 0.24 305)" stopOpacity={0.85} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
          <XAxis dataKey="label" stroke={axisStroke} fontSize={11} tickLine={false} />
          <YAxis
            stroke={axisStroke}
            fontSize={11}
            tickFormatter={(v) => tk.format(v)}
            tickLine={false}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            cursor={{ fill: "oklch(0.9 0.02 285 / 0.4)" }}
            formatter={(v: number) => [tk.formatFull(v), "Avg / dev"]}
          />
          <Bar dataKey="avgTokens" radius={[8, 8, 0, 0]} fill="url(#senBar)" />
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
        Mid-level developers (3-5y) burn the most tokens on average — they're productive enough
        to ship a lot, but not yet senior enough to know when AI assistance is overkill.
      </p>
    </ChartCard>
  );
}

// ---------- 3. Tokens vs Revenue -----------------------------------------

// Invented monthly series: token spend ($) vs total company revenue ($)
const REVENUE_SERIES = [
  { month: "Jan", tokenSpend: 4_200, revenue: 182_000 },
  { month: "Feb", tokenSpend: 5_100, revenue: 198_000 },
  { month: "Mar", tokenSpend: 6_800, revenue: 221_000 },
  { month: "Apr", tokenSpend: 8_400, revenue: 256_000 },
  { month: "May", tokenSpend: 10_200, revenue: 298_000 },
  { month: "Jun", tokenSpend: 12_500, revenue: 341_000 },
];

// ---------- 3bis. Tokens by developer role --------------------------------

const ROLES = [
  { key: "frontend", label: "Frontend", color: "oklch(0.7 0.24 350)" }, // hot pink
  { key: "backend", label: "Backend", color: "oklch(0.55 0.24 305)" }, // deep violet
  { key: "fullstack", label: "Fullstack", color: "oklch(0.65 0.20 340)" }, // mauve
  { key: "devops", label: "DevOps", color: "oklch(0.78 0.16 355)" }, // soft pink
] as const;
type RoleKey = (typeof ROLES)[number]["key"];

function buildRoleData() {
  // Deterministic role assignment per employee (stable from name)
  const byRole: Record<RoleKey, { tokens: number; count: number }> = {
    frontend: { tokens: 0, count: 0 },
    backend: { tokens: 0, count: 0 },
    fullstack: { tokens: 0, count: 0 },
    devops: { tokens: 0, count: 0 },
  };
  employees.forEach((e, i) => {
    const seed = e.name.charCodeAt(0) + e.name.length + i;
    const role = ROLES[seed % ROLES.length].key;
    byRole[role].tokens += e.tokens_used;
    byRole[role].count += 1;
  });
  return ROLES.map((r) => ({
    role: r.label,
    key: r.key,
    color: r.color,
    tokens: byRole[r.key].tokens,
    devs: byRole[r.key].count,
    avgPerDev: byRole[r.key].count
      ? Math.round(byRole[r.key].tokens / byRole[r.key].count)
      : 0,
  }));
}

function TokensByRole() {
  const data = useMemo(buildRoleData, []);
  const tk = useTokenFormatter();
  const totalTokens = data.reduce((a, d) => a + d.tokens, 0);

  return (
    <ChartCard
      title={tk.unit === "dollars" ? "$ spent by developer role" : "Tokens by developer role"}
      subtitle="Which type of developer relies the most on AI assistance?"
    >
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data} margin={{ top: 10, right: 16, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
              <XAxis dataKey="role" stroke={axisStroke} fontSize={11} tickLine={false} />
              <YAxis
                stroke={axisStroke}
                fontSize={11}
                tickFormatter={(v) => tk.format(v)}
                tickLine={false}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                cursor={{ fill: "oklch(0.9 0.02 285 / 0.4)" }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload as (typeof data)[number];
                  const share = totalTokens
                    ? ((p.tokens / totalTokens) * 100).toFixed(1)
                    : "0";
                  return (
                    <div style={tooltipStyle}>
                      <div className="font-display font-semibold">{p.role}</div>
                      <div style={{ opacity: 0.75 }}>
                        {tk.format(p.tokens)}{tk.unit === "tokens" ? " tokens" : ""} · {share}% of team
                      </div>
                      <div style={{ opacity: 0.75 }}>
                        {p.devs} devs · avg {tk.format(p.avgPerDev)} / dev
                      </div>
                    </div>
                  );
                }}
              />
              <Bar dataKey="tokens" radius={[8, 8, 0, 0]}>
                {data.map((d) => (
                  <Cell key={d.key} fill={d.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-col justify-center gap-2 lg:col-span-2">
          {data
            .slice()
            .sort((a, b) => b.tokens - a.tokens)
            .map((d) => {
              const share = totalTokens ? (d.tokens / totalTokens) * 100 : 0;
              return (
                <div
                  key={d.key}
                  className="rounded-lg border border-border/60 bg-background/40 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="h-2.5 w-2.5 rounded-full flex-shrink-0"
                        style={{ background: d.color }}
                      />
                      <span className="text-sm font-medium text-foreground">
                        {d.role}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        · {d.devs} devs
                      </span>
                    </div>
                    <span className="text-xs font-semibold tabular-nums text-foreground">
                      {tk.format(d.tokens)}
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${share}%`, background: d.color }}
                    />
                  </div>
                  <div className="mt-1 text-[10px] text-muted-foreground">
                    {share.toFixed(1)}% of team spend · avg{" "}
                    {tk.format(d.avgPerDev)} per dev
                  </div>
                </div>
              );
            })}
        </div>
      </div>
      <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
        Frontend and Fullstack roles tend to consume the most tokens — UI iteration and
        cross-stack glue work both benefit heavily from AI assistance, while DevOps work is
        more script-driven and needs fewer completions.
      </p>
    </ChartCard>
  );
}

function TokensVsRevenue() {
  const data = REVENUE_SERIES;
  const totalTokenSpend = data.reduce((a, d) => a + d.tokenSpend, 0);
  const totalRevenue = data.reduce((a, d) => a + d.revenue, 0);
  const ratio = totalRevenue / Math.max(totalTokenSpend, 1);

  return (
    <ChartCard
      title="Tokens spent vs total revenue"
      subtitle="Every $1 spent on tokens this half-year generated ${ratio} of company revenue."
    >
      <div className="mb-4 flex flex-wrap items-baseline gap-6">
        <div>
          <div className="text-xs text-muted-foreground">Token spend (6 mo)</div>
          <div className="font-display text-2xl font-semibold text-foreground">
            ${fmtInt(totalTokenSpend)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Revenue (6 mo)</div>
          <div className="font-display text-2xl font-semibold text-foreground">
            ${fmtInt(Math.round(totalRevenue / 1000))}k
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Revenue per $1 of tokens</div>
          <div className="font-display text-2xl font-semibold text-primary">
            ${ratio.toFixed(0)}
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} margin={{ top: 10, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
          <XAxis dataKey="month" stroke={axisStroke} fontSize={11} tickLine={false} />
          <YAxis
            yAxisId="left"
            stroke={axisStroke}
            fontSize={11}
            tickLine={false}
            tickFormatter={(v) => `$${v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v}`}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            stroke={axisStroke}
            fontSize={11}
            tickLine={false}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            cursor={{ fill: "oklch(0.9 0.02 285 / 0.4)" }}
            formatter={(v: number, name) => {
              const label = name === "tokenSpend" ? "Token spend" : "Revenue";
              return [`$${fmtInt(v)}`, label];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar
            yAxisId="left"
            dataKey="tokenSpend"
            name="Token spend"
            radius={[8, 8, 0, 0]}
            fill="oklch(0.78 0.16 355)"
          />
          <Bar
            yAxisId="right"
            dataKey="revenue"
            name="Revenue"
            radius={[8, 8, 0, 0]}
            fill="oklch(0.55 0.24 305)"
          />
        </BarChart>
      </ResponsiveContainer>

      <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
        Revenue grows faster than token spend — clear positive ROI on AI investment.
      </p>
    </ChartCard>
  );
}

// ---------- Page ----------------------------------------------------------

function MoreStatisticsPage() {
  return (
    <div className="min-h-screen">
      <Header />

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        <section>
          <h1 className="font-display text-3xl font-bold text-foreground">More statistics</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Deeper breakdowns of how tokens are consumed across models, the team's experience
            profile, and the features being shipped.
          </p>
        </section>

        <section className="grid gap-4 sm:grid-cols-3">
          <div
            className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4"
            style={{ backgroundImage: "var(--gradient-surface)" }}
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Cpu className="h-5 w-5" />
            </span>
            <div>
              <div className="text-xs text-muted-foreground">Model mix</div>
              <div className="text-sm font-semibold text-foreground">5 models in production</div>
            </div>
          </div>
          <div
            className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4"
            style={{ backgroundImage: "var(--gradient-surface)" }}
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <GraduationCap className="h-5 w-5" />
            </span>
            <div>
              <div className="text-xs text-muted-foreground">Team profile</div>
              <div className="text-sm font-semibold text-foreground">
                {employees.length} developers · 4 levels
              </div>
            </div>
          </div>
          <div
            className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4"
            style={{ backgroundImage: "var(--gradient-surface)" }}
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Sparkles className="h-5 w-5" />
            </span>
            <div>
              <div className="text-xs text-muted-foreground">Revenue impact</div>
              <div className="text-sm font-semibold text-foreground">
                Tracked over 6 months
              </div>
            </div>
          </div>
        </section>

        <TokensVsModels />
        <TokensByRole />
        <TokensVsSeniority />
        <TokensVsRevenue />

        <footer className="pt-6 text-center text-xs text-muted-foreground">
          Paretokens · turning token spend into measurable ROI
        </footer>
      </main>
    </div>
  );
}
