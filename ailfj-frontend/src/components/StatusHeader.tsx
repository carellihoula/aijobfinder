import { Check, Download } from "lucide-react"
import type { AnalysisStatus } from "../lib/designTypes"

interface StatusHeaderProps {
  status: AnalysisStatus
  progress?: number
  step?: string
  jobsEvaluated?: number
  strongMatches?: number
  finishedAt?: string
  onExport?: () => void
}

export default function StatusHeader({
  status,
  progress = 0,
  step,
  jobsEvaluated = 0,
  strongMatches = 0,
  finishedAt,
  onExport,
}: StatusHeaderProps) {
  if (status === "processing") {
    const pct = Math.round(Math.min(100, Math.max(0, progress)))
    return (
      <div className="card rounded-2xl p-5 space-y-3">
        {/* Top row */}
        <div className="flex items-center gap-3">
          {/* Spinner */}
          <span className="relative grid place-items-center h-9 w-9 shrink-0">
            <svg className="absolute inset-0 h-9 w-9 -rotate-90" viewBox="0 0 36 36">
              <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,.07)" strokeWidth="3" />
              <circle
                cx="18" cy="18" r="15" fill="none" stroke="rgb(var(--accent))" strokeWidth="3"
                strokeLinecap="round" strokeDasharray="94" strokeDashoffset="70"
                className="origin-center animate-spin-slow"
              />
            </svg>
          </span>

          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink leading-none">Analyse en cours</p>
            <p className="text-xs text-accent mt-1 font-medium truncate transition-all duration-300">
              {step ?? "Initialisation…"}
            </p>
          </div>

          <span className="font-mono text-sm font-semibold text-ink tabular-nums shrink-0">
            {pct}%
          </span>
        </div>

        {/* Progress bar */}
        <div className="h-1.5 w-full rounded-full bg-line/10 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-[800ms] ease-in-out"
            style={{
              width: `${pct}%`,
              background: "linear-gradient(90deg, rgb(var(--accent)), rgb(var(--accent) / .7))",
            }}
          />
        </div>
      </div>
    )
  }

  if (status === "completed") {
    return (
      <div className="card rounded-2xl p-5 relative overflow-hidden">
        <div
          className="absolute right-0 top-0 h-24 w-40"
          style={{ background: "radial-gradient(12rem 8rem at 100% 0, rgba(52,211,153,.10), transparent)" }}
        />
        <div className="relative flex items-center gap-4">
          <span className="grid place-items-center h-12 w-12 rounded-2xl bg-emerald-500/15 border border-emerald-500/25 shrink-0">
            <Check className="h-6 w-6 text-emerald-500" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink flex items-center gap-2">
              Analyse terminée <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 pulse-dot" />
            </p>
            <p className="text-xs text-muted mt-0.5">
              <span className="text-ink font-medium">{jobsEvaluated} offres</span> évaluées ·{" "}
              <span className="text-emerald-500 font-medium">{strongMatches} fortes correspondances</span>
              {finishedAt ? ` · ${finishedAt}` : ""}
            </p>
          </div>
          {onExport && (
            <button
              onClick={onExport}
              className="hidden sm:flex items-center gap-1.5 text-xs text-muted hover:text-ink border border-line/10 rounded-lg px-2.5 py-1.5 hover:bg-line/5 transition"
            >
              <Download className="h-3.5 w-3.5" /> Exporter
            </button>
          )}
        </div>
      </div>
    )
  }

  return null
}
