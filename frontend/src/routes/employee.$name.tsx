import { useMemo } from "react";
import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import {
  ArrowLeft,
  Target,
  Coins,
  Bug,
  Code2,
  GitMerge,
  Ticket,
  Clock,
  Lightbulb,
  TrendingUp,
  Mail,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { StatCard } from "@/components/dashboard/StatCard";
import { ChartCard } from "@/components/dashboard/ChartCard";
import {
  findEmployee,
  avatarUrl,
  categoryMeta,
  monthsSorted,
  monthLabel,
  formatTokens,
  employees,
} from "@/lib/metrics";
import { useTokenFormatter } from "@/contexts/DisplayUnitContext";

// Locale-stable integer formatter to avoid SSR/CSR hydration mismatches.
const fmtInt = (n: number) => n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");

export const Route = createFileRoute("/employee/$name")({
  loader: ({ params }) => {
    const decoded = decodeURIComponent(params.name);
    const employee = findEmployee(decoded);
    if (!employee) throw notFound();
    return { employee };
  },
  notFoundComponent: () => (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="max-w-md text-center">
        <h1 className="font-display text-3xl font-semibold text-foreground">
          Employee not found
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          We couldn't find this developer in the dataset.
        </p>
        <Link
          to="/"
          className="mt-6 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <ArrowLeft className="h-4 w-4" /> Back to dashboard
        </Link>
      </div>
    </div>
  ),
  component: EmployeeDetail,
  head: ({ params }) => {
    const decoded = decodeURIComponent(params.name);
    return {
      meta: [
        { title: `${decoded} — Paretokens` },
        {
          name: "description",
          content: `AI usage, productivity and ROI breakdown for ${decoded}.`,
        },
      ],
    };
  },
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

function EmployeeDetail() {
  const { employee } = Route.useLoaderData();
  const meta = categoryMeta[employee.category];
  const tk = useTokenFormatter();

  // Monthly history for this employee
  const history = useMemo(
    () =>
      monthsSorted.map((m) => {
        const row = m.employees.find((e) => e.name === employee.name);
        return {
          month: monthLabel(m.month).split(" ")[0],
          fullMonth: monthLabel(m.month),
          tokens: row?.tokens_used ?? 0,
          storyPoints: row?.story_points ?? 0,
          efficiency:
            row && row.tokens_used > 0
              ? +(row.story_points / (row.tokens_used / 1_000_000)).toFixed(2)
              : 0,
        };
      }),
    [employee.name],
  );

  // Team medians for context
  const teamMedians = useMemo(() => {
    const sortedSp = [...employees].map((e) => e.story_points).sort((a, b) => a - b);
    const sortedTk = [...employees].map((e) => e.tokens_used).sort((a, b) => a - b);
    const sortedTickets = [...employees]
      .map((e) => e.tickets_resolved)
      .sort((a, b) => a - b);
    const sortedTime = [...employees]
      .map((e) => e.time_to_completion_days)
      .sort((a, b) => a - b);
    const median = (arr: number[]) => arr[Math.floor(arr.length / 2)] ?? 0;
    return {
      sp: median(sortedSp),
      tokens: median(sortedTk),
      tickets: median(sortedTickets),
      time: median(sortedTime),
    };
  }, []);

  // Rank in story points (latest month)
  const rank = useMemo(() => {
    const sorted = [...employees].sort((a, b) => b.story_points - a.story_points);
    return sorted.findIndex((e) => e.name === employee.name) + 1;
  }, [employee.name]);

  const tokensPerSp =
    employee.story_points > 0
      ? Math.round(employee.tokens_used / employee.story_points)
      : 0;

  const spTone =
    employee.story_points >= teamMedians.sp ? "positive" : "negative";
  const tokensTone =
    employee.tokens_used <= teamMedians.tokens ? "positive" : "negative";
  const ticketsTone =
    employee.tickets_resolved >= teamMedians.tickets ? "positive" : "negative";
  const timeTone =
    employee.time_to_completion_days <= teamMedians.time ? "positive" : "negative";

  return (
    <div className="min-h-screen">
      <header className="border-b border-border/60 backdrop-blur-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> Back to dashboard
          </Link>
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold"
            style={{
              backgroundColor: `color-mix(in oklab, ${meta.color} 16%, transparent)`,
              color: meta.color,
            }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: meta.color }} />
            {meta.label}
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        {/* Profile header */}
        <section
          className="flex flex-col items-start gap-5 rounded-2xl border border-border bg-card p-6 sm:flex-row sm:items-center"
          style={{ backgroundImage: "var(--gradient-surface)" }}
        >
          <div className="relative">
            <img
              src={avatarUrl(employee.name)}
              alt={employee.name}
              loading="lazy"
              decoding="async"
              className="h-24 w-24 rounded-full object-cover"
              style={{ boxShadow: `0 0 0 4px ${meta.color}` }}
            />
          </div>
          <div className="flex-1">
            <h1 className="font-display text-3xl font-semibold tracking-tight text-foreground">
              {employee.name}
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Current month · {monthLabel(employee.month)} · Rank #{rank} of {employees.length} by story points
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <TrendingUp className="h-3.5 w-3.5" />
                {fmtInt(tokensPerSp)} tokens / story point
              </span>
              <span>·</span>
              <span>{employee.merge_requests_per_ticket} MR per ticket</span>
            </div>
          </div>
          <a
            href={`mailto:manager@acmecorp.com?subject=${encodeURIComponent(
              `About ${employee.name} — ${monthLabel(employee.month)}`,
            )}&body=${encodeURIComponent(
              `Hi,\n\nI'd like to discuss ${employee.name}'s recent activity (category: ${meta.label}, ${employee.story_points} SP this month).\n\nContext:\n${employee.recommendation}\n\nThanks,`,
            )}`}
            className="inline-flex flex-shrink-0 items-center gap-2 self-start rounded-full px-4 py-2 text-sm font-semibold shadow-sm transition-all hover:shadow-md sm:self-center"
            style={{
              backgroundImage: "var(--gradient-primary)",
              color: "var(--primary-foreground)",
            }}
          >
            <Mail className="h-4 w-4" />
            Contact manager
          </a>
        </section>

        {/* Recommendation — moved to top, larger */}
        <section
          className="rounded-2xl border border-primary/30 p-7"
          style={{
            backgroundImage: "var(--gradient-primary)",
            color: "var(--primary-foreground)",
          }}
        >
          <div className="flex items-start gap-4">
            <span className="mt-1 flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-white/15">
              <Lightbulb className="h-6 w-6" />
            </span>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider opacity-80">
                Personalized recommendation · {monthLabel(employee.month)}
              </div>
              <p className="mt-2 font-display text-xl font-semibold leading-snug sm:text-2xl">
                {employee.recommendation}
              </p>
            </div>
          </div>
        </section>

        {/* Section header for current month metrics */}
        <div className="flex items-end justify-between pt-2">
          <div>
            <h2 className="font-display text-xl font-semibold text-foreground">
              This month at a glance
            </h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              All KPIs below reflect {monthLabel(employee.month)} only.
            </p>
          </div>
        </div>

        {/* KPI grid */}
        <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard
            label="Story points"
            value={`${employee.story_points}`}
            delta={`Team median: ${teamMedians.sp}`}
            deltaTone={spTone}
            icon={<Target className="h-4 w-4" />}
            highlight={rank <= 3}
          />
          <StatCard
            label={tk.unit === "dollars" ? "$ spent" : "Tokens used"}
            value={tk.format(employee.tokens_used)}
            delta={`Team median: ${tk.format(teamMedians.tokens)}`}
            deltaTone={tokensTone}
            icon={<Coins className="h-4 w-4" />}
          />
          <StatCard
            label="Tickets resolved"
            value={`${employee.tickets_resolved}`}
            delta={`Team median: ${teamMedians.tickets}`}
            deltaTone={ticketsTone}
            icon={<Ticket className="h-4 w-4" />}
          />
          <StatCard
            label="Time to completion"
            value={`${employee.time_to_completion_days}d`}
            delta={`Team median: ${teamMedians.time}d`}
            deltaTone={timeTone}
            icon={<Clock className="h-4 w-4" />}
          />
        </section>

        {/* Secondary KPIs */}
        <section className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          <StatCard
            label="Bugs closed"
            value={`${employee.bugs_closed}`}
            icon={<Bug className="h-4 w-4" />}
          />
          <StatCard
            label="Lines of code"
            value={fmtInt(employee.lines_of_code)}
            icon={<Code2 className="h-4 w-4" />}
          />
          <StatCard
            label="Merge requests"
            value={`${employee.merge_requests}`}
            delta={`${employee.merge_requests_per_ticket} per ticket`}
            deltaTone="neutral"
            icon={<GitMerge className="h-4 w-4" />}
          />
        </section>

        {/* History section header */}
        <div className="pt-2">
          <h2 className="font-display text-xl font-semibold text-foreground">
            Historical trends
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Month-by-month evolution across the full tracking period.
          </p>
        </div>

        {/* History charts */}
        <section className="grid gap-6 lg:grid-cols-2">
          <ChartCard
            title="Story points over time"
            subtitle="Monthly delivery for this developer"
          >
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={history} margin={{ top: 10, right: 16, bottom: 8, left: 0 }}>
                <defs>
                  <linearGradient id="spArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={meta.color} stopOpacity={0.55} />
                    <stop offset="100%" stopColor={meta.color} stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
                <XAxis dataKey="month" stroke={axisStroke} fontSize={11} tickLine={false} />
                <YAxis stroke={axisStroke} fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(v: number) => [`${v} SP`, "Story points"]}
                  labelFormatter={(_, p) => p?.[0]?.payload?.fullMonth ?? ""}
                />
                <Area
                  type="monotone"
                  dataKey="storyPoints"
                  stroke={meta.color}
                  strokeWidth={2.5}
                  fill="url(#spArea)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title={tk.unit === "dollars" ? "$ spent over time" : "Token spend over time"}
            subtitle={
              tk.unit === "dollars"
                ? "Monthly $ spent by this developer"
                : "Monthly tokens consumed by this developer"
            }
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={history} margin={{ top: 10, right: 16, bottom: 8, left: 0 }}>
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
                  formatter={(v: number) => [tk.formatFull(v), tk.unit === "dollars" ? "Spent" : "Tokens"]}
                  labelFormatter={(_, p) => p?.[0]?.payload?.fullMonth ?? ""}
                />
                <Bar dataKey="tokens" radius={[8, 8, 0, 0]} fill={meta.color} fillOpacity={0.85} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </section>

        <footer className="pt-2 text-center text-xs text-muted-foreground">
          Paretokens · turning token spend into measurable ROI
        </footer>
      </main>
    </div>
  );
}
