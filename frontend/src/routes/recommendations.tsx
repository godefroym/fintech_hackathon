import { useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Lightbulb, Filter, ArrowRight, Sparkles } from "lucide-react";
import { Header } from "@/components/Header";
import {
  employees,
  summary,
  avatarUrl,
  categoryMeta,
  type Category,
} from "@/lib/metrics";

export const Route = createFileRoute("/recommendations")({
  head: () => ({
    meta: [
      { title: "Recommendations — Paretokens" },
      {
        name: "description",
        content:
          "Strategic AI spend recommendations and per-developer focus areas to maximize ROI across the team.",
      },
      { property: "og:title", content: "Recommendations — Paretokens" },
      {
        property: "og:description",
        content:
          "Strategic AI spend recommendations and per-developer focus areas to maximize ROI across the team.",
      },
    ],
  }),
  component: RecommendationsPage,
});

function splitBullets(text: string): string[] {
  if (!text) return [];
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.replace(/^\s*[-•]\s*/, "").trim())
    .filter(Boolean);
  return lines.length > 0 ? lines : [text.trim()];
}

const ACTIONABLE_CATEGORIES: Category[] = [
  "overspender",
  "quality_risk",
  "low_adoption",
  "high_roi",
];

type FilterKey = "all" | Category;

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "overspender", label: "Overspenders" },
  { key: "quality_risk", label: "Quality risk" },
  { key: "low_adoption", label: "Low adoption" },
  { key: "high_roi", label: "High ROI" },
];

function RecommendationsPage() {
  const [filter, setFilter] = useState<FilterKey>("all");

  const filtered = useMemo(() => {
    const base = employees.filter((e) =>
      ACTIONABLE_CATEGORIES.includes(e.category),
    );
    const scoped =
      filter === "all" ? base : base.filter((e) => e.category === filter);
    return [...scoped].sort((a, b) => b.tokens_used - a.tokens_used);
  }, [filter]);

  const mainBullets = splitBullets(summary.main_recommendation);

  return (
    <div className="min-h-screen">
      <Header />

      <main className="mx-auto max-w-5xl space-y-8 px-6 py-12">
        <section>
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Action plan
          </div>
          <h1 className="mt-4 font-display text-4xl font-bold tracking-tight text-foreground md:text-5xl">
            Recommendations to maximize AI ROI.
          </h1>
          <p className="mt-3 max-w-2xl text-base text-muted-foreground">
            Strategic actions for the team plus targeted focus areas for
            individual contributors who need attention this month.
          </p>
        </section>

        <section
          className="overflow-hidden rounded-2xl border border-primary/30 p-6 text-foreground shadow-sm"
          style={{
            backgroundImage: "var(--gradient-primary)",
            color: "var(--primary-foreground)",
          }}
        >
          <div className="flex items-start gap-4">
            <div className="rounded-xl bg-white/15 p-2.5 backdrop-blur-sm">
              <Lightbulb className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <div className="text-[11px] font-semibold uppercase tracking-wider opacity-80">
                Main recommendation
              </div>
              <ul className="mt-2 space-y-2">
                {mainBullets.map((b, i) => (
                  <li
                    key={i}
                    className="flex gap-2 text-sm font-medium leading-snug"
                  >
                    <span aria-hidden className="opacity-70">
                      •
                    </span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <h2 className="font-display text-xl font-semibold text-foreground">
                Per-developer focus
              </h2>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {FILTERS.map((f) => {
                const active = filter === f.key;
                return (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => setFilter(f.key)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                      active
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground"
                    }`}
                  >
                    {f.label}
                  </button>
                );
              })}
            </div>
          </div>

          {filtered.length === 0 ? (
            <p className="rounded-xl border border-dashed border-border bg-card/50 p-6 text-center text-sm text-muted-foreground">
              No employees match this filter.
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {filtered.map((emp) => {
                const meta = categoryMeta[emp.category];
                const bullets = splitBullets(emp.recommendation);
                return (
                  <Link
                    key={emp.name}
                    to="/employee/$name"
                    params={{ name: encodeURIComponent(emp.name) }}
                    className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-4 transition-all hover:border-primary/40 hover:shadow-md"
                  >
                    <div className="flex items-center gap-3">
                      <img
                        src={avatarUrl(emp.name)}
                        alt={emp.name}
                        loading="lazy"
                        decoding="async"
                        className="h-10 w-10 flex-shrink-0 rounded-full object-cover ring-2 ring-primary/20"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-foreground">
                          {emp.name}
                        </div>
                        <div className="mt-0.5 flex items-center gap-2">
                          <span
                            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
                            style={{
                              backgroundColor: `color-mix(in oklab, ${meta.color} 15%, transparent)`,
                              color: meta.color,
                            }}
                          >
                            {meta.label}
                          </span>
                          <span className="text-[10px] text-muted-foreground">
                            {emp.story_points} SP
                          </span>
                        </div>
                      </div>
                      <ArrowRight className="h-4 w-4 flex-shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                    </div>
                    <ul className="space-y-1.5 border-t border-border/60 pt-3">
                      {bullets.map((b, i) => (
                        <li
                          key={i}
                          className="flex gap-2 text-xs leading-snug text-muted-foreground"
                        >
                          <span aria-hidden className="text-primary">
                            •
                          </span>
                          <span>{b}</span>
                        </li>
                      ))}
                    </ul>
                  </Link>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
