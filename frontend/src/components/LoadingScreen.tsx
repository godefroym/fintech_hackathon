import { useEffect, useState } from "react";
import logo from "@/assets/paretokens-logo.png";

const PHRASES = [
  "Computing value…",
  "Crunching token streams…",
  "Aligning ROI vectors…",
  "Calibrating efficiency models…",
  "Synthesizing developer signals…",
  "Optimizing the Pareto frontier…",
];

export function LoadingScreen({ onDone, durationMs = 5000 }: { onDone: () => void; durationMs?: number }) {
  const [phraseIdx, setPhraseIdx] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const phraseInterval = setInterval(() => {
      setPhraseIdx((i) => (i + 1) % PHRASES.length);
    }, 1000);

    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / durationMs);
      setProgress(p);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    const done = setTimeout(onDone, durationMs);

    return () => {
      clearInterval(phraseInterval);
      clearTimeout(done);
      cancelAnimationFrame(raf);
    };
  }, [durationMs, onDone]);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{ backgroundImage: "var(--gradient-surface)" }}
    >
      <div className="absolute inset-0" style={{ backgroundImage: "var(--gradient-glow)" }} />

      <div className="relative flex flex-col items-center gap-8 px-6 text-center">
        <img src={logo} alt="Paretokens" className="h-14 w-auto animate-pulse" />

        {/* Spinner */}
        <div className="relative h-16 w-16">
          <div
            className="absolute inset-0 rounded-full border-2 border-border"
            style={{ borderTopColor: "transparent" }}
          />
          <div
            className="absolute inset-0 animate-spin rounded-full border-2 border-transparent"
            style={{
              borderTopColor: "var(--brand-violet)",
              borderRightColor: "var(--brand-pink)",
            }}
          />
          <div
            className="absolute inset-2 animate-spin rounded-full border-2 border-transparent"
            style={{
              borderTopColor: "var(--brand-coral)",
              animationDirection: "reverse",
              animationDuration: "1.5s",
            }}
          />
        </div>

        {/* Rotating phrase */}
        <div className="h-6 overflow-hidden">
          <p
            key={phraseIdx}
            className="font-display text-base font-medium tracking-tight text-foreground"
            style={{
              animation: "fade-slide 0.5s ease-out",
              backgroundImage: "var(--gradient-primary)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            {PHRASES[phraseIdx]}
          </p>
        </div>

        {/* Progress bar */}
        <div className="h-1 w-64 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full transition-[width] duration-100 ease-linear"
            style={{
              width: `${progress * 100}%`,
              backgroundImage: "var(--gradient-primary)",
            }}
          />
        </div>

        <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          Paretokens · turning AI spend into ROI
        </p>
      </div>

      <style>{`
        @keyframes fade-slide {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
