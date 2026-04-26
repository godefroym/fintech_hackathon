import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Activity,
  Coins,
  Target,
  Gauge,
  Lightbulb,
  BarChart3,
  ArrowRight,
  ChevronDown,
} from "lucide-react";
import { StatCard } from "@/components/dashboard/StatCard";
import {
  TokensVsOutputScatter,
  TokensOverTimeBar,
  DeveloperRanking,
  getMonthlyStoryPoints,
} from "@/components/dashboard/Charts";
import { LoadingScreen } from "@/components/LoadingScreen";
import { Header } from "@/components/Header";
import { employees, summary, avatarUrl } from "@/lib/metrics";

export const Route = createFileRoute("/")({
  component: Dashboard,
});

// Split a bullet-list recommendation ("- foo\n- bar") into trimmed items.
function splitBullets(text: string): string[] {
  if (!text) return [];
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.replace(/^\s*[-•]\s*/, "").trim())
    .filter(Boolean);
  return lines.length > 0 ? lines : [text.trim()];
}

interface BulletAccordionProps {
  bullets: string[];
  /** "light" = on gradient bg (white text), "dark" = on light bg (muted text) */
  variant?: "light" | "dark";
  size?: "sm" | "md";
}

function BulletAccordion({ bullets, variant = "dark", size = "md" }: BulletAccordionProps) {
  const [open, setOpen] = useState(false);
  if (bullets.length === 0) return null;
  const [first, ...rest] = bullets;
  const hasMore = rest.length > 0;

  const textCls =
    size === "sm"
      ? variant === "light"
        ? "text-[11px] leading-snug text-primary-foreground"
        : "text-[11px] leading-snug text-muted-foreground"
      : variant === "light"
        ? "text-sm font-medium leading-snug text-primary-foreground"
        : "text-sm leading-snug text-foreground";

  const buttonCls =
    variant === "light"
      ? "mt-2 inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-primary-foreground/90 hover:text-primary-foreground"
      : "mt-1.5 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-primary hover:text-primary/80";

  return (
    <div>
      <p className={textCls}>{first}</p>
      {open &&
        rest.map((b, i) => (
          <p key={i} className={`${textCls} mt-1.5`}>
            {b}
          </p>
        ))}
      {hasMore && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setOpen((v) => !v);
          }}
          className={buttonCls}
        >
          {open ? "Show less" : `Read more (+${rest.length})`}
          <ChevronDown
            className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`}
          />
        </button>
      )}
    </div>
  );
}


function Dashboard() {
  // Start false to keep SSR HTML stable; on mount, decide whether to show
  // the splash loader once per browser session.
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    try {
      if (sessionStorage.getItem("paretokens.loaderShown") !== "1") {
        setLoading(true);
      }
    } catch {
      /* ignore */
    }
  }, []);
  if (loading)
    return (
      <LoadingScreen
        onDone={() => {
          try {
            sessionStorage.setItem("paretokens.loaderShown", "1");
          } catch {
            /* ignore */
          }
          setLoading(false);
        }}
      />
    );

  const budgetPct = summary.budget_usage_percent;
  const budgetTone = budgetPct >= 90 ? "negative" : budgetPct >= 75 ? "neutral" : "positive";

  return (
    <div className="min-h-screen">
      <Header
        rightSlot={
          <div className="ml-2 hidden items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1.5 text-xs text-muted-foreground sm:flex">
            <span className="h-2 w-2 rounded-full bg-success" />
            Live · {employees.length} employees
          </div>
        }
      />

      <main className="mx-auto max-w-7xl space-y-6 px-6 py-8">
        <section>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard
              label="Story points this month"
              value={`${Math.round(getMonthlyStoryPoints())}`}
              delta={`Across ${employees.length} contributors`}
              deltaTone="positive"
              icon={<Target className="h-4 w-4" />}
              highlight
            />
            <StatCard
              label="Monthly spend"
              value={`$${(summary.monthly_ai_spend_total / 1000).toFixed(1)}k`}
              delta={`Forecast next month: $${(summary.forecast_next_month_ai_spend / 1000).toFixed(1)}k`}
              deltaTone="negative"
              icon={<Coins className="h-4 w-4" />}
            />
            <StatCard
              label="Productivity gain"
              value={`+${summary.productivity_gain_percent}%`}
              delta={`Bugs −${summary.bugs_reduction_percent}%`}
              deltaTone="positive"
              icon={<Activity className="h-4 w-4" />}
            />
            <StatCard
              label="Budget usage"
              value={`${summary.budget_usage_percent}%`}
              delta={`+${summary.monthly_ai_spend_growth_percent}% MoM`}
              deltaTone={budgetTone}
              icon={<Gauge className="h-4 w-4" />}
            />
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-4">
            <TokensVsOutputScatter />
          </div>
          <aside
            className="flex max-h-[50vh] min-h-0 flex-col self-start rounded-2xl bg-card p-5"
            style={{ backgroundImage: "var(--gradient-surface)" }}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h3 className="font-display text-lg font-semibold text-foreground">
                  Recommendations
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Strategic action + per-user focus
                </p>
              </div>
              <span className="text-primary">
                <Lightbulb className="h-5 w-5" />
              </span>
            </div>

            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
              <div
                className="rounded-xl border border-primary/30 p-3 text-sm text-foreground"
                style={{ backgroundImage: "var(--gradient-primary)", color: "var(--primary-foreground)" }}
              >
                <div className="text-[10px] font-semibold uppercase tracking-wider opacity-80">
                  Main recommendation
                </div>
                <div className="mt-1">
                  <BulletAccordion
                    bullets={splitBullets(summary.main_recommendation)}
                    variant="light"
                  />
                </div>
              </div>
              {[...employees]
                .filter((e) =>
                  ["overspender", "quality_risk", "low_adoption", "high_roi"].includes(e.category),
                )
                .sort((a, b) => b.tokens_used - a.tokens_used)
                .slice(0, 6)
                .map((emp) => {
                  return (
                    <Link
                      key={emp.name}
                      to="/employee/$name"
                      params={{ name: encodeURIComponent(emp.name) }}
                      className="flex items-start gap-3 rounded-lg border border-border/60 bg-background/50 p-2.5 transition-all hover:border-primary/40 hover:bg-background"
                    >
                      <img
                        src={avatarUrl(emp.name)}
                        alt={emp.name}
                        loading="lazy"
                        decoding="async"
                        className="h-9 w-9 flex-shrink-0 rounded-full object-cover ring-2 ring-primary/20"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-xs font-semibold text-foreground">
                            {emp.name}
                          </span>
                          <span className="text-[10px] font-medium text-muted-foreground">
                            {emp.story_points} SP
                          </span>
                        </div>
                        <div className="mt-0.5">
                          <BulletAccordion
                            bullets={splitBullets(emp.recommendation)}
                            variant="dark"
                            size="sm"
                          />
                        </div>
                      </div>
                    </Link>
                  );
                })}
            </div>
          </aside>
        </section>

        <div className="flex justify-center">
          <Link
            to="/more-statistics"
            className="group inline-flex items-center gap-2.5 rounded-full border border-border bg-card px-5 py-2.5 text-sm font-medium text-foreground shadow-sm transition-all hover:border-primary/50 hover:shadow-md"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary">
              <BarChart3 className="h-3.5 w-3.5" />
            </span>
            More statistics
            <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
          </Link>
        </div>


        <section className="grid gap-6 lg:grid-cols-2">
          <TokensOverTimeBar />
          <DeveloperRanking />
        </section>

        <footer className="pt-6 text-center text-xs text-muted-foreground">
          Paretokens · turning token spend into measurable ROI
        </footer>
      </main>
    </div>
  );
}
