import { useEffect, useRef, useState } from "react"
import {
  MapPin, Banknote, Clock, ChevronDown,
  Check, CheckCircle2, CircleDashed, FileText, ExternalLink, Bookmark,
} from "lucide-react"
import { scoreTier } from "../lib/designTypes"
import type { DesignJobMatch } from "../lib/designTypes"
import ScoreBar from "./ScoreBar"
import { isJobSaved, toggleSaveJob } from "../lib/savedJobs"

interface Props {
  match: DesignJobMatch
  analysisId?: string
  onApply?: () => void
  onSaveToggle?: () => void
}

export default function MatchCard({ match, analysisId, onApply, onSaveToggle }: Props) {
  const [open, setOpen] = useState(false)
  const [saved, setSaved] = useState(() => isJobSaved(match.id))
  const wrapRef  = useRef<HTMLDivElement>(null)
  const innerRef = useRef<HTMLDivElement>(null)
  const tier = scoreTier(match.score)

  useEffect(() => {
    const exp = wrapRef.current
    if (!exp) return
    const target = `${innerRef.current?.scrollHeight ?? 0}px`
    if (open) exp.style.maxHeight = target
    else {
      exp.style.maxHeight = target
      void exp.offsetWidth
      exp.style.maxHeight = "0px"
    }
    const t = setTimeout(() => {
      exp.style.transition = "none"
      exp.style.maxHeight = open ? "none" : "0px"
      void exp.offsetWidth
      exp.style.transition = ""
    }, 400)
    return () => clearTimeout(t)
  }, [open])

  const handleSave = (e: React.MouseEvent) => {
    e.stopPropagation()
    const next = toggleSaveJob(match, analysisId ?? "")
    setSaved(next)
    onSaveToggle?.()
  }

  const tags = [match.contract, match.mode, match.seniority].filter(Boolean)

  return (
    <div className="card rounded-2xl overflow-hidden transition hover:border-line/20">
      <button onClick={() => setOpen((v) => !v)} aria-expanded={open} className="w-full p-4 sm:p-5 text-left select-none">
        <div className="flex items-start gap-3.5">
          <span className="grid place-items-center h-11 w-11 rounded-xl bg-line/5 bd font-semibold text-ink shrink-0">
            {match.logo}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-[15px] font-semibold text-ink truncate">{match.title}</h3>
                <p className="text-xs text-muted mt-0.5 flex items-center gap-1.5 flex-wrap">
                  <span className="text-ink font-medium">{match.company}</span>
                  <span className="text-subtle">·</span>
                  <span className="inline-flex items-center gap-1">
                    <MapPin className="h-3 w-3" />{match.location}
                  </span>
                </p>
              </div>
              <div className="text-right shrink-0">
                <div className="font-mono text-lg font-semibold tabular-nums" style={{ color: `rgb(${tier.rgb})` }}>
                  {match.score.toFixed(1)}<span className="text-xs text-subtle">/10</span>
                </div>
                <div className="text-[10px] font-medium uppercase tracking-wide" style={{ color: `rgb(${tier.rgb})` }}>
                  {tier.label}
                </div>
              </div>
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

            <div className="mt-3 flex items-center gap-3 text-[11px] text-subtle">
              {match.posted && (
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-3 w-3" />{match.posted}
                </span>
              )}
              <span className="ml-auto inline-flex items-center gap-1 text-muted">
                Détails <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
              </span>
            </div>
          </div>
        </div>
      </button>

      <div ref={wrapRef} className="exp">
        <div ref={innerRef}>
          <div className="px-4 sm:px-5 pb-5 pt-1">
            <div className="pt-3 border-t border-line/10">
              <p className="text-[11px] font-medium uppercase tracking-wide text-subtle mb-1.5">Description du poste</p>
              <p className="text-[13px] text-muted leading-relaxed">{match.description}</p>

              {match.missions.length > 0 && (
                <>
                  <p className="text-[11px] font-medium uppercase tracking-wide text-subtle mt-4 mb-2">Missions principales</p>
                  <ul className="space-y-1.5">
                    {match.missions.map((m) => (
                      <li key={m} className="flex gap-2 text-[13px] text-muted">
                        <Check className="h-3.5 w-3.5 mt-0.5 shrink-0 text-accent" /><span>{m}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              <div className="grid sm:grid-cols-2 gap-3 mt-4">
                <SkillGroup tone="emerald" title="Compétences en commun"
                  icon={<CheckCircle2 className="h-3.5 w-3.5" />} skills={match.matchedSkills} />
                <SkillGroup tone="rose" title="À renforcer"
                  icon={<CircleDashed className="h-3.5 w-3.5" />} skills={match.missingSkills} />
              </div>

              <div className="mt-4 flex items-center gap-2">
                <button
                  onClick={(e) => { e.stopPropagation(); onApply?.() }}
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
          </div>
        </div>
      </div>
    </div>
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