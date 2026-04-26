import { Coins, DollarSign } from "lucide-react";
import { useDisplayUnit } from "@/contexts/DisplayUnitContext";
import { cn } from "@/lib/utils";

/** Pill-style toggle with a sliding gradient thumb. */
export function DisplayUnitToggle() {
  const { unit, setUnit } = useDisplayUnit();
  const isDollars = unit === "dollars";

  return (
    <div
      role="group"
      aria-label="Display unit"
      className="relative inline-flex items-center rounded-full border border-border bg-card p-0.5 text-xs shadow-sm"
    >
      {/* Sliding thumb */}
      <span
        aria-hidden
        className={cn(
          "absolute top-0.5 bottom-0.5 left-0.5 w-[calc(50%-2px)] rounded-full shadow-md transition-transform duration-300 ease-out",
          isDollars && "translate-x-full",
        )}
        style={{ backgroundImage: "var(--gradient-primary)" }}
      />

      <button
        type="button"
        onClick={() => setUnit("tokens")}
        aria-pressed={!isDollars}
        className={cn(
          "relative z-10 inline-flex w-1/2 items-center justify-center gap-1.5 rounded-full px-3 py-1.5 font-medium transition-colors duration-200",
          !isDollars ? "text-primary-foreground" : "text-muted-foreground hover:text-foreground",
        )}
      >
        <Coins
          className={cn(
            "h-3.5 w-3.5 transition-transform duration-300",
            !isDollars && "scale-110 -rotate-12",
          )}
        />
        Tokens
      </button>
      <button
        type="button"
        onClick={() => setUnit("dollars")}
        aria-pressed={isDollars}
        className={cn(
          "relative z-10 inline-flex w-1/2 items-center justify-center gap-1.5 rounded-full px-3 py-1.5 font-medium transition-colors duration-200",
          isDollars ? "text-primary-foreground" : "text-muted-foreground hover:text-foreground",
        )}
      >
        <DollarSign
          className={cn(
            "h-3.5 w-3.5 transition-transform duration-300",
            isDollars && "scale-110 rotate-12",
          )}
        />
        USD
      </button>
    </div>
  );
}
