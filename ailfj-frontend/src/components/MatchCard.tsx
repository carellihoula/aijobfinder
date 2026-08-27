import { useEffect } from "react"
import { createPortal } from "react-dom"
import {
  MapPin, Banknote, Clock, X,
  Check, CheckCircle2, CircleDashed, FileText, ExternalLink, Bookmark,
} from "lucide-react"
import { scoreTier } from "../lib/designTypes"
import type { DesignJobMatch } from "../lib/designTypes"
import ScoreBar from "./ScoreBar"
import { isJobSaved, toggleSaveJob } from "../lib/savedJobs"

interface CardProps {
  match: DesignJobMatch
  onOpen: () => void
}

// Compact card for the grid — collapsed summary only, click opens the detail panel.
export default function MatchCard({ match, onOpen }: CardProps) {
  const tier = scoreTier(match.score)
  const tags = [match.contract, match.mode, match.seniority].filter(Boolean)

  return (
    <button
      onClick={onOpen}
      className="card rounded-2xl overflow-hidden transition hover:border-line/20 w-full text-left p-4 sm:p-5"
    >
      <div className="flex items-start gap-3">
        <span className="grid place-items-center h-10 w-10 rounded-xl bg-line/5 bd font-semibold text-ink shrink-0">
          {match.logo}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-[14px] font-semibold text-ink truncate">{match.title}</h3>
            <div className="font-mono text-sm font-semibold tabular-nums shrink-0" style={{ color: `rgb(${tier.rgb})` }}>
              {match.score.toFixed(1)}<span className="text-[10px] text-subtle">/10</span>
            </div>
          </div>
          <p className="text-xs text-muted mt-0.5 flex items-center gap-1.5 flex-wrap">
            <span className="text-ink font-medium truncate">{match.company}</span>
            <span className="text-subtle">·</span>
            <span className="inline-flex items-center gap-1 truncate">
              <MapPin className="h-3 w-3 shrink-0" />{match.location}
            </span>
          </p>
        </div>
      </div>

      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {tags.map((t) => (
          <span key={t} className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-line/5 bd text-muted">{t}</span>
        ))}
        {match.salary && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-line/5 bd text-muted inline-flex items-center gap-1">
            <Banknote className="h-3 w-3" />{match.salary}
          </span>
        )}
      </div>

      <ScoreBar score={match.score} />

      <p className="mt-2.5 text-[12px] text-muted italic leading-relaxed line-clamp-2">{match.reason}</p>

      {match.posted && (
        <p className="mt-2.5 inline-flex items-center gap-1 text-[11px] text-subtle">
          <Clock className="h-3 w-3" />{match.posted}
        </p>
      )}
    </button>
  )
}

interface PanelProps {
  match: DesignJobMatch
  analysisId?: string
  onClose: () => void
  onApply?: () => void
  onSaveToggle?: () => void
}

// Modal — full detail view for the currently selected match.
export function MatchDetailModal({ match, analysisId, onClose, onApply, onSaveToggle }: PanelProps) {
  const tier = scoreTier(match.score)
  const tags = [match.contract, match.mode, match.seniority].filter(Boolean)
  const saved = isJobSaved(match.id)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  const handleSave = () => {
    toggleSaveJob(match, analysisId ?? "")
    onSaveToggle?.()
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 animate-fade-in" onClick={onClose} />

      <div className="relative w-full max-w-xl max-h-[85vh] rounded-2xl bg-[rgb(var(--bg))] shadow-2xl flex flex-col animate-pop-in">
        <div className="flex items-start gap-3 p-5 border-b border-line/10">
          <span className="grid place-items-center h-11 w-11 rounded-xl bg-line/5 bd font-semibold text-ink shrink-0">
            {match.logo}
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="text-[15px] font-semibold text-ink">{match.title}</h3>
            <p className="text-xs text-muted mt-0.5 flex items-center gap-1.5 flex-wrap">
              <span className="text-ink font-medium">{match.company}</span>
              <span className="text-subtle">·</span>
              <span className="inline-flex items-center gap-1"><MapPin className="h-3 w-3" />{match.location}</span>
            </p>
          </div>
          <button onClick={onClose} aria-label="Fermer" className="grid place-items-center h-8 w-8 rounded-lg btn-ghost text-subtle hover:text-ink shrink-0">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <div className="flex items-center justify-between">
            <div className="font-mono text-lg font-semibold tabular-nums" style={{ color: `rgb(${tier.rgb})` }}>
              {match.score.toFixed(1)}<span className="text-xs text-subtle">/10</span>
              <span className="ml-2 text-[10px] font-medium uppercase tracking-wide align-middle">{tier.label}</span>
            </div>
            {match.posted && (
              <span className="inline-flex items-center gap-1 text-[11px] text-subtle">
                <Clock className="h-3 w-3" />{match.posted}
              </span>
            )}
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <span key={t} className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-line/5 bd text-muted">{t}</span>
            ))}
            {match.salary && (
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-line/5 bd text-muted inline-flex items-center gap-1">
                <Banknote className="h-3 w-3" />{match.salary}
              </span>
            )}
          </div>

          <ScoreBar score={match.score} />

          <p className="mt-3 text-[13px] text-muted italic leading-relaxed">{match.reason}</p>

          {match.missions.length > 0 && (
            <>
              <p className="text-[11px] font-medium uppercase tracking-wide text-subtle mt-5 mb-2">Missions principales</p>
              <ul className="space-y-1.5">
                {match.missions.map((m) => (
                  <li key={m} className="flex gap-2 text-[13px] text-muted">
                    <Check className="h-3.5 w-3.5 mt-0.5 shrink-0 text-accent" /><span>{m}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="grid sm:grid-cols-2 gap-3 mt-5">
            <SkillGroup tone="emerald" title="Compétences en commun"
              icon={<CheckCircle2 className="h-3.5 w-3.5" />} skills={match.matchedSkills} />
            <SkillGroup tone="rose" title="À renforcer"
              icon={<CircleDashed className="h-3.5 w-3.5" />} skills={match.missingSkills} />
          </div>
        </div>

        <div className="flex items-center gap-2 p-5 border-t border-line/10">
          <button
            onClick={onApply}
            className="btn-accent inline-flex items-center gap-1.5 text-xs font-medium rounded-lg px-3 py-2 transition"
          >
            <FileText className="h-3.5 w-3.5" /> Préparer ma candidature
          </button>
          {match.url ? (
            <a href={match.url} target="_blank" rel="noreferrer"
              className="btn-ghost inline-flex items-center gap-1.5 text-xs font-medium text-ink rounded-lg px-3 py-2 transition">
              <ExternalLink className="h-3.5 w-3.5" /> Voir l'offre
            </a>
          ) : (
            <button
              disabled
              title="URL non disponible"
              className="btn-ghost inline-flex items-center gap-1.5 text-xs font-medium text-subtle rounded-lg px-3 py-2 opacity-40 cursor-not-allowed"
            >
              <ExternalLink className="h-3.5 w-3.5" /> Voir l'offre
            </button>
          )}
          <button
            aria-label={saved ? "Retirer des favoris" : "Sauvegarder"}
            onClick={handleSave}
            className={`ml-auto grid place-items-center h-8 w-8 rounded-lg transition ${
              saved
                ? "text-accent bg-accent/10 hover:bg-accent/20"
                : "btn-ghost text-subtle hover:text-ink"
            }`}
          >
            <Bookmark className={`h-3.5 w-3.5 ${saved ? "fill-current" : ""}`} />
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}

function SkillGroup({ tone, title, icon, skills }: {
  tone: "emerald" | "rose"
  title: string
  icon: React.ReactNode
  skills: string[]
}) {
  const tones = {
    emerald: {
      label: "text-emerald-500",
      chip: "bg-emerald-500/10 border-emerald-500/25 text-emerald-600 dark:text-emerald-300",
    },
    rose: {
      label: "text-rose-500",
      chip: "bg-rose-500/10 border-rose-500/25 text-rose-600 dark:text-rose-300",
    },
  }[tone]

  return (
    <div>
      <p className={`text-[11px] font-medium uppercase tracking-wide mb-2 flex items-center gap-1.5 ${tones.label}`}>
        {icon} {title}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {skills.length ? (
          skills.map((s) => (
            <span key={s} className={`text-[11px] px-2 py-1 rounded-md border ${tones.chip}`}>{s}</span>
          ))
        ) : (
          <span className="text-[11px] text-subtle">—</span>
        )}
      </div>
    </div>
  )
}
