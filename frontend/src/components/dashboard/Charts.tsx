import { useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  ZAxis,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChartCard } from "@/components/dashboard/ChartCard";
import {
  Category,
  categoryMeta,
  employees,
  monthsSorted,
  monthLabel,
  getEmployeeMonthly,
  formatTokens,
  avatarUrl,
} from "@/lib/metrics";
import { useTokenFormatter } from "@/contexts/DisplayUnitContext";
import { cn } from "@/lib/utils";

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

// --- Story-points scatter (real monthly data) -------------------------------

type EffBucket = "low" | "mid" | "high";

interface MonthlyPoint {
  name: string;
  category: Category;
  tokens: number;
  storyPoints: number;
  efficiency: number; // SP per 1M tokens
  bucket: EffBucket;
  avatar: string;
}

const BUCKET_META: Record<EffBucket, { label: string; color: string }> = {
  low: { label: "Low efficiency", color: "oklch(0.62 0.22 27)" }, // red
  mid: { label: "Average efficiency", color: "oklch(0.78 0.17 85)" }, // amber/yellow
  high: { label: "High efficiency", color: "oklch(0.68 0.18 150)" }, // green
};

function buildMonthlyData(monthIdx: number): MonthlyPoint[] {
  const month = monthsSorted[monthIdx];
  if (!month) return [];
  const catByName = new Map(employees.map((e) => [e.name, e.category]));
  const base = month.employees.map((e) => ({
    name: e.name,
    category: catByName.get(e.name) ?? ("average_user" as Category),
    tokens: e.tokens_used,
    storyPoints: e.story_points,
    efficiency: e.tokens_used > 0 ? +(e.story_points / (e.tokens_used / 1_000_000)).toFixed(2) : 0,
    avatar: avatarUrl(e.name),
  }));

  // Tercile thresholds on efficiency
  const sorted = [...base].map((d) => d.efficiency).sort((a, b) => a - b);
  const t1 = sorted[Math.floor(sorted.length / 3)] ?? 0;
  const t2 = sorted[Math.floor((sorted.length * 2) / 3)] ?? 0;
  return base.map((d) => ({
    ...d,
    bucket: (d.efficiency <= t1 ? "low" : d.efficiency <= t2 ? "mid" : "high") as EffBucket,
  }));
}

export function getMonthlyStoryPoints(monthIdx: number = monthsSorted.length - 1) {
  return buildMonthlyData(monthIdx).reduce((acc, d) => acc + d.storyPoints, 0);
}

// Custom shape: colored dot, swaps to avatar on hover --------------------

interface DotShapeProps {
  cx?: number;
  cy?: number;
  payload?: MonthlyPoint;
  hoveredName?: string | null;
}

function ScatterDot({ cx, cy, payload, hoveredName, onNavigate }: DotShapeProps & { onNavigate?: (name: string) => void }) {
  if (cx == null || cy == null || !payload) return null;
  const ringColor = BUCKET_META[payload.bucket].color;
  const isHover = hoveredName === payload.name;
  const r = isHover ? 18 : 6;
  const ringWidth = isHover ? 2.5 : 0;
  const clipId = `clip-${payload.name.replace(/\W+/g, "-")}`;
  return (
    <g
      style={{ transition: "all 150ms ease-out", cursor: "pointer" }}
      onClick={() => onNavigate?.(payload.name)}
    >
      {isHover && <circle cx={cx} cy={cy} r={r + 4} fill={ringColor} opacity={0.18} />}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill={isHover ? "oklch(1 0 0)" : ringColor}
        stroke={isHover ? ringColor : "oklch(1 0 0)"}
        strokeWidth={isHover ? ringWidth : 1.5}
        fillOpacity={isHover ? 1 : 0.9}
      />
      {isHover && (
        <>
          <defs>
            <clipPath id={clipId}>
              <circle cx={cx} cy={cy} r={r - ringWidth / 2} />
            </clipPath>
          </defs>
          <image
            href={payload.avatar}
            x={cx - (r - ringWidth / 2)}
            y={cy - (r - ringWidth / 2)}
            width={(r - ringWidth / 2) * 2}
            height={(r - ringWidth / 2) * 2}
            clipPath={`url(#${clipId})`}
            preserveAspectRatio="xMidYMid slice"
          />
        </>
      )}
    </g>
  );
}


export function TokensVsOutputScatter() {
  const [monthIdx, setMonthIdx] = useState(monthsSorted.length - 1);
  const [hoveredName, setHoveredName] = useState<string | null>(null);
  const navigate = useNavigate();
  const tk = useTokenFormatter();
  const goToEmployee = (name: string) =>
    navigate({ to: "/employee/$name", params: { name: encodeURIComponent(name) } });
  const data = useMemo(() => buildMonthlyData(monthIdx), [monthIdx]);

  // Median SP-per-token slope for the team in the selected month
  const slope = useMemo(() => {
    const vals = data
      .filter((d) => d.tokens > 0)
      .map((d) => d.storyPoints / d.tokens)
      .sort((a, b) => a - b);
    return vals[Math.floor(vals.length / 2)] ?? 0;
  }, [data]);

  const maxTokens = useMemo(() => Math.max(...data.map((d) => d.tokens), 1) * 1.05, [data]);
  const maxSp = useMemo(() => Math.max(...data.map((d) => d.storyPoints), 1) * 1.1, [data]);
  const lineData = useMemo(() => {
    // End the regression line where it would exit the visible area
    const endX = slope > 0 ? Math.min(maxTokens, maxSp / slope) : maxTokens;
    return [
      { tokens: 0, storyPoints: 0 },
      { tokens: endX, storyPoints: endX * slope },
    ];
  }, [maxTokens, maxSp, slope]);

  const canPrev = monthIdx > 0;
  const canNext = monthIdx < monthsSorted.length - 1;

  return (
    <ChartCard
      title={tk.unit === "dollars" ? "Story points vs $ spent" : "Story points vs token spend"}
      subtitle="Above the line = efficient. Below = burning tokens for too few story points."
      action={
        <div className="flex items-center gap-1.5 rounded-full border border-border bg-card px-1.5 py-1">
          <button
            onClick={() => canPrev && setMonthIdx((i) => i - 1)}
            disabled={!canPrev}
            aria-label="Previous month"
            className="rounded-full p-1 text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span className="min-w-[84px] text-center text-xs font-semibold text-foreground tabular-nums">
            {monthLabel(monthsSorted[monthIdx].month)}
          </span>
          <button
            onClick={() => canNext && setMonthIdx((i) => i + 1)}
            disabled={!canNext}
            aria-label="Next month"
            className="rounded-full p-1 text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      }
    >
      <ResponsiveContainer width="100%" height={420}>
        <ScatterChart margin={{ top: 20, right: 30, bottom: 24, left: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis
            type="number"
            dataKey="tokens"
            name={tk.unit === "dollars" ? "USD spent" : "Tokens used"}
            stroke={axisStroke}
            fontSize={11}
            domain={[0, maxTokens]}
            tickFormatter={(v) => tk.format(v)}
            label={{
              value: tk.unit === "dollars" ? "USD spent" : "Tokens used",
              position: "insideBottom",
              offset: -8,
              fill: axisStroke,
              fontSize: 11,
            }}
          />
          <YAxis
            type="number"
            dataKey="storyPoints"
            name="Story points"
            stroke={axisStroke}
            fontSize={11}
            domain={[0, maxSp]}
            allowDataOverflow
            label={{
              value: "Story points",
              angle: -90,
              position: "insideLeft",
              fill: axisStroke,
              fontSize: 11,
            }}
          />
          <ZAxis range={[100, 100]} />
          <Tooltip
            contentStyle={tooltipStyle}
            cursor={{ strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as MonthlyPoint;
              if (!p.name) return null;
              return (
                <div style={tooltipStyle}>
                  <div className="font-display font-semibold">{p.name}</div>
                  <div style={{ opacity: 0.75 }}>
                    {tk.formatFull(p.tokens)} · {p.storyPoints} story points
                  </div>
                  <div style={{ opacity: 0.75 }}>
                    {BUCKET_META[p.bucket].label} · {p.efficiency} SP / 1M tokens
                  </div>
                </div>
              );
            }}
          />
          <Scatter
            data={lineData}
            line={{ stroke: "oklch(0.55 0.02 285 / 0.5)", strokeDasharray: "4 4", strokeWidth: 1.5 }}
            shape={() => <g />}
            legendType="none"
          />
          <Scatter
            data={data}
            shape={(props: DotShapeProps) => (
              <ScatterDot {...props} hoveredName={hoveredName} onNavigate={goToEmployee} />
            )}
            onMouseEnter={(p: { name?: string }) => setHoveredName(p?.name ?? null)}
            onMouseLeave={() => setHoveredName(null)}
          />
        </ScatterChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="mt-2 flex flex-wrap items-center justify-center gap-4 text-[11px] text-muted-foreground">
        {(["high", "mid", "low"] as EffBucket[]).map((b) => (
          <div key={b} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: BUCKET_META[b].color }}
            />
            {BUCKET_META[b].label}
          </div>
        ))}
      </div>
    </ChartCard>
  );
}

// --- Tokens over time -------------------------------------------------------

export function TokensOverTimeBar() {
  const tk = useTokenFormatter();
  const data = useMemo(
    () =>
      monthsSorted.map((m) => ({
        month: monthLabel(m.month).split(" ")[0],
        tokens: m.employees.reduce((acc, e) => acc + e.tokens_used, 0),
      })),
    [],
  );

  return (
    <ChartCard
      title={tk.unit === "dollars" ? "Total $ spend over time" : "Total token usage over time"}
      subtitle={
        tk.unit === "dollars"
          ? "Sum of $ spent on AI by all developers, per month"
          : "Sum of tokens consumed by all developers, per month"
      }
    >
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 10, right: 16, bottom: 8, left: 0 }}>
          <defs>
            <linearGradient id="tokenBar" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--cat-high-roi)" stopOpacity={0.95} />
              <stop offset="100%" stopColor="var(--cat-efficient)" stopOpacity={0.6} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
          <XAxis dataKey="month" stroke={axisStroke} fontSize={11} tickLine={false} />
          <YAxis
            stroke={axisStroke}
            fontSize={11}
            tickFormatter={(v) => tk.format(v)}
            tickLine={false}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            cursor={{ fill: "oklch(0.9 0.02 285 / 0.4)" }}
            formatter={(v: number) => [tk.formatFull(v), "Total"]}
          />
          <Bar dataKey="tokens" radius={[8, 8, 0, 0]} fill="url(#tokenBar)" />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// --- Developer ranking ------------------------------------------------------

export function DeveloperRanking() {
  const tk = useTokenFormatter();
  const ranked = useMemo(() => {
    const latest = monthsSorted[monthsSorted.length - 1];
    const spByName = new Map(latest.employees.map((m) => [m.name, m.story_points]));
    const tkByName = new Map(latest.employees.map((m) => [m.name, m.tokens_used]));
    return [...employees]
      .map((e) => {
        const sp = spByName.get(e.name) ?? 0;
        const tkn = tkByName.get(e.name) ?? e.tokens_used;
        return {
          ...e,
          monthStoryPoints: sp,
          monthTokens: tkn,
          storyPointsPerMTokens: tkn > 0 ? +(sp / (tkn / 1_000_000)).toFixed(2) : 0,
        };
      })
      .sort((a, b) => b.monthStoryPoints - a.monthStoryPoints)
      .map((e, i) => ({ ...e, rank: i + 1 }));
  }, []);

  return (
    <ChartCard
      title="Developer ranking"
      subtitle="Ordered by story points delivered this month"
    >
      <div className="mb-2 flex items-start gap-2 rounded-lg border border-border/50 bg-muted/40 p-2 text-[11px] leading-snug text-muted-foreground">
        <span className="mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-primary/15 text-[9px] font-bold text-primary">
          i
        </span>
        <span>
          <span className="font-semibold text-foreground">Efficiency</span> is shown as
          {" "}
          <span className="font-semibold text-foreground">SP / 1M tokens</span> — story points
          delivered for every 1 million tokens consumed this month. Higher = more output per token spent.
        </span>
      </div>
      <div className="max-h-[280px] space-y-1.5 overflow-y-auto pr-1">
        {ranked.map((e) => {
          const meta = categoryMeta[e.category];
          const medal = e.rank === 1 ? "🥇" : e.rank === 2 ? "🥈" : e.rank === 3 ? "🥉" : null;
          return (
            <Link
              key={e.name}
              to="/employee/$name"
              params={{ name: encodeURIComponent(e.name) }}
              className="flex items-center gap-3 rounded-lg border border-border/60 bg-background/50 p-2.5 transition-all hover:border-primary/40 hover:bg-background hover:shadow-sm"
            >
              <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center text-xs font-bold tabular-nums text-muted-foreground">
                {medal ?? e.rank}
              </div>
              <div className="relative flex-shrink-0">
                <img
                  src={avatarUrl(e.name)}
                  alt={e.name}
                  loading="lazy"
                  decoding="async"
                  className="h-9 w-9 rounded-full object-cover"
                  style={{ boxShadow: `0 0 0 2px ${meta.color}` }}
                />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold text-foreground">{e.name}</span>
                  <span className="text-xs font-bold tabular-nums text-foreground">
                    {e.monthStoryPoints} SP
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span
                    className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                    style={{
                      backgroundColor: `color-mix(in oklab, ${meta.color} 18%, transparent)`,
                      color: meta.color,
                    }}
                  >
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: meta.color }} />
                    {meta.label}
                  </span>
                  <span
                    className="text-[10px] text-muted-foreground tabular-nums"
                    title={`${e.monthStoryPoints} story points ÷ ${e.monthTokens.toLocaleString()} tokens × 1,000,000 = ${e.storyPointsPerMTokens} story points per 1M tokens`}
                  >
                    {tk.format(e.monthTokens)}{tk.unit === "tokens" ? " tokens" : ""} ·{" "}
                    <span className="font-semibold text-foreground">
                      {e.storyPointsPerMTokens}
                    </span>{" "}
                    SP per 1M tokens
                  </span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </ChartCard>
  );
}

// --- Category donut ---------------------------------------------------------

export function CategoryDonut() {
  const data = useMemo(() => {
    const counts: Record<string, number> = {};
    employees.forEach((e) => {
      counts[e.category] = (counts[e.category] ?? 0) + 1;
    });
    return Object.entries(counts).map(([cat, value]) => ({
      name: categoryMeta[cat as Category].label,
      key: cat as Category,
      value,
    }));
  }, []);

  return (
    <ChartCard title="Workforce mix" subtitle="Distribution by category">
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={data}
            innerRadius={60}
            outerRadius={95}
            paddingAngle={3}
            dataKey="value"
            stroke="none"
          >
            {data.map((d) => (
              <Cell key={d.key} fill={categoryMeta[d.key].color} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} />
        </PieChart>
      </ResponsiveContainer>
      <ul className="mt-2 grid grid-cols-2 gap-2 text-xs">
        {data.map((d) => (
          <li key={d.key} className="flex items-center gap-2 text-muted-foreground">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: categoryMeta[d.key].color }}
            />
            <span className="text-foreground">{d.name}</span>
            <span className="ml-auto tabular-nums">{d.value}</span>
          </li>
        ))}
      </ul>
    </ChartCard>
  );
}

// --- Top 12 most efficient (SP per million tokens) --------------------------

export function EfficiencyBarChart() {
  const sorted = useMemo(() => {
    return [...employees]
      .map((e) => ({
        ...e,
        sp_per_m_tokens:
          e.tokens_used > 0 ? +(e.story_points / (e.tokens_used / 1_000_000)).toFixed(2) : 0,
      }))
      .sort((a, b) => b.sp_per_m_tokens - a.sp_per_m_tokens)
      .slice(0, 12);
  }, []);
  return (
    <ChartCard title="Story points per 1M tokens" subtitle="Top 12 most token-efficient teammates">
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={sorted} margin={{ left: 0, right: 10, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis
            dataKey="name"
            stroke={axisStroke}
            fontSize={10}
            angle={-35}
            textAnchor="end"
            interval={0}
          />
          <YAxis stroke={axisStroke} fontSize={11} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "oklch(0.9 0.02 285 / 0.4)" }} />
          <Bar dataKey="sp_per_m_tokens" radius={[6, 6, 0, 0]} fill="var(--cat-high-roi)" />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// --- Employee table ---------------------------------------------------------

export function EmployeeTable() {
  const tk = useTokenFormatter();
  const [filter, setFilter] = useState<Category | "all">("all");
  const rows = useMemo(() => {
    const list = filter === "all" ? employees : employees.filter((e) => e.category === filter);
    return [...list].sort((a, b) => b.story_points - a.story_points);
  }, [filter]);

  return (
    <ChartCard
      title="All employees"
      subtitle={`${rows.length} of ${employees.length} shown`}
      action={
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilter("all")}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              filter === "all"
                ? "bg-primary text-primary-foreground"
                : "border border-border text-muted-foreground hover:text-foreground",
            )}
          >
            All
          </button>
          {(Object.keys(categoryMeta) as Category[]).map((c) => (
            <button
              key={c}
              onClick={() => setFilter(c)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium transition-colors border",
                filter === c
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground border-border",
              )}
              style={
                filter === c
                  ? {
                      borderColor: categoryMeta[c].color,
                      backgroundColor: `color-mix(in oklab, ${categoryMeta[c].color} 18%, transparent)`,
                    }
                  : undefined
              }
            >
              {categoryMeta[c].label}
            </button>
          ))}
        </div>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wider text-muted-foreground">
              <th className="py-2 pr-3 font-medium">Name</th>
              <th className="py-2 pr-3 font-medium">Category</th>
              <th className="py-2 pr-3 font-medium text-right">{tk.unit === "dollars" ? "$ spent" : "Tokens"}</th>
              <th className="py-2 pr-3 font-medium text-right">Story pts</th>
              <th className="py-2 pr-3 font-medium text-right">SP / 1M tk</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => {
              const eff =
                e.tokens_used > 0 ? +(e.story_points / (e.tokens_used / 1_000_000)).toFixed(2) : 0;
              return (
                <tr key={e.name} className="border-b border-border/60 hover:bg-secondary/40">
                  <td className="py-2.5 pr-3">
                    <span className="font-medium text-foreground">{e.name}</span>
                  </td>
                  <td className="py-2.5 pr-3">
                    <span
                      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs"
                      style={{
                        backgroundColor: `color-mix(in oklab, ${categoryMeta[e.category].color} 18%, transparent)`,
                        color: categoryMeta[e.category].color,
                      }}
                    >
                      <span
                        className="h-1.5 w-1.5 rounded-full"
                        style={{ background: categoryMeta[e.category].color }}
                      />
                      {categoryMeta[e.category].label}
                    </span>
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums text-muted-foreground">
                    {tk.format(e.tokens_used)}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums font-semibold text-foreground">
                    {e.story_points}
                  </td>
                  <td className="py-2.5 pr-3 text-right tabular-nums text-muted-foreground">
                    {eff}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </ChartCard>
  );
}

// Re-export helper for index page
export { getEmployeeMonthly };
