import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  delta?: string;
  deltaTone?: "positive" | "negative" | "neutral";
  icon?: ReactNode;
  highlight?: boolean;
}

export function StatCard({ label, value, delta, deltaTone = "neutral", icon, highlight }: StatCardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/40",
        highlight && "shadow-[var(--shadow-glow)] border-primary/40",
      )}
      style={{ backgroundImage: highlight ? "var(--gradient-surface)" : undefined }}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</span>
        {icon && <span className="text-primary">{icon}</span>}
      </div>
      <div className="mt-3 font-display text-3xl font-semibold text-foreground">{value}</div>
      {delta && (
        <div
          className={cn(
            "mt-2 text-xs font-medium",
            deltaTone === "positive" && "text-success",
            deltaTone === "negative" && "text-destructive",
            deltaTone === "neutral" && "text-muted-foreground",
          )}
        >
          {delta}
        </div>
      )}
    </div>
  );
}
