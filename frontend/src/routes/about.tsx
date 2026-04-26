import { createFileRoute } from "@tanstack/react-router";
import { Building2, Target, Users, Sparkles } from "lucide-react";
import { Header } from "@/components/Header";

export const Route = createFileRoute("/about")({
  head: () => ({
    meta: [
      { title: "About — Acme Corp · Paretokens" },
      { name: "description", content: "Learn about Acme Corp and how we use Paretokens to turn AI spend into measurable ROI." },
      { property: "og:title", content: "About — Acme Corp · Paretokens" },
      { property: "og:description", content: "Learn about Acme Corp and how we use Paretokens to turn AI spend into measurable ROI." },
    ],
  }),
  component: AboutPage,
});

function AboutPage() {
  return (
    <div className="min-h-screen">
      <Header />

      <main className="mx-auto max-w-4xl space-y-8 px-6 py-12">
        <section>
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground">
            <Building2 className="h-3.5 w-3.5 text-primary" />
            About Acme Corp
          </div>
          <h1 className="mt-4 font-display text-4xl font-bold tracking-tight text-foreground md:text-5xl">
            Building the future, one token at a time.
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted-foreground">
            Acme Corp is a product-led engineering organization where every developer
            is empowered with AI tools to ship faster, learn deeper, and stay focused
            on what matters most: solving real customer problems.
          </p>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {[
            {
              icon: <Target className="h-5 w-5" />,
              title: "Our mission",
              body: "Turn AI spend into measurable ROI by giving every team transparent insight into how tokens become value.",
            },
            {
              icon: <Users className="h-5 w-5" />,
              title: "Our people",
              body: "A globally distributed team of engineers, designers, and operators who treat code quality as a feature.",
            },
            {
              icon: <Sparkles className="h-5 w-5" />,
              title: "Our practice",
              body: "We measure what we ship — story points, bugs avoided, cycle time — not just hours logged or tokens burned.",
            },
          ].map((card) => (
            <div
              key={card.title}
              className="rounded-2xl border border-border bg-card p-5"
              style={{ backgroundImage: "var(--gradient-surface)" }}
            >
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                {card.icon}
              </span>
              <h3 className="mt-3 font-display text-base font-semibold text-foreground">
                {card.title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                {card.body}
              </p>
            </div>
          ))}
        </section>

        <section
          className="rounded-2xl border border-border p-6"
          style={{ backgroundImage: "var(--gradient-surface)" }}
        >
          <h2 className="font-display text-2xl font-semibold text-foreground">
            Why Paretokens?
          </h2>
          <p className="mt-3 leading-relaxed text-muted-foreground">
            Most teams adopt AI tooling without ever quantifying its impact.
            Paretokens gives Acme Corp a single dashboard to compare token spend
            against shipped output, identify high-ROI workflows, and coach
            individual contributors on how to use AI responsibly. We treat the
            80/20 rule as our north star: a small set of behaviors drive most of
            the value.
          </p>
        </section>

        <footer className="pt-4 text-center text-xs text-muted-foreground">
          Acme Corp · Powered by Paretokens
        </footer>
      </main>
    </div>
  );
}
