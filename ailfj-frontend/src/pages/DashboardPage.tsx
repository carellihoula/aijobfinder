import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { FileText, RefreshCw, AlertCircle, Search, Loader2, Clock, ChevronDown, Plus, Radar } from "lucide-react"
import { getAnalysis, getCvData, launchSearch, SEARCH_COOLDOWN_MS } from "../api/analysis"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { QK, useLatestAnalysis } from "../lib/queries"
import type { Analysis, JobMatch as BackendJobMatch } from "../types"
import Layout from "../components/Layout"
import { MatchSkeletonList } from "../components/Skeletons"

import MatchCard, { MatchDetailModal } from "../components/MatchCard"
import MarkdownReport from "../components/MarkdownReport"
import FilterBar from "../components/FilterBar"
import Pagination from "../components/Pagination"
import EmptyState from "../components/states/EmptyState"
import {
  DEFAULT_FILTERS,
  applyFilters,
} from "../lib/designTypes"
import type {
  DesignJobMatch,
  MatchFilters,
  ContractType,
  WorkMode,
} from "../lib/designTypes"

const POLL_MS = 3_000

const NODE_PROGRESS: Record<string, number> = {
  pdf_parser:        12,
  cv_structurer:     28,
  cortex_search:     45,
  keyword_extractor: 50,
  job_search:        62,
  cortex_feed:       65,
  prepare_retry:     67,
  embeddings_filter: 75,
  llm_reranker:      88,
  report_generator:  97,
}

const CONTRACT_MAP: Record<string, ContractType> = {
  "CDI":        "CDI",
  "CDD":        "CDD",
  "Stage":      "Stage",
  "Alternance": "Alternance",
  "Freelance":  "Freelance",
}

function formatPosted(raw: string): { label: string; days: number } | undefined {
  if (!raw) return undefined
  try {
    const date = new Date(raw)
    const days = Math.floor((Date.now() - date.getTime()) / 86_400_000)
    const label =
      days === 0 ? "Aujourd'hui" :
      days === 1 ? "Hier" :
      days < 7   ? `Il y a ${days} j` :
      days < 30  ? `Il y a ${Math.floor(days / 7)} sem.` :
      date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })
    return { label, days }
  } catch { return undefined }
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })
  } catch { return iso }
}

function adaptMatch(m: BackendJobMatch, index: number): DesignJobMatch {
  const posted = formatPosted(m.job.date)
  return {
    id: `${m.job.company}_${m.job.title}_${index}`.replace(/\s+/g, "_"),
    originalIndex: index,
    title:    m.job.title,
    company:  m.job.company,
    logo:     m.job.company?.[0]?.toUpperCase() ?? "?",
    location: m.job.location || "Non précisé",
    mode:     (m.job.remote ? "Remote" : "Sur site") as WorkMode,
    contract: CONTRACT_MAP[m.job.contract_type] ?? "Autres",
    seniority: "",
    score:    m.score,
    posted:   posted?.label,
    postedDays: posted?.days,
    reason:   m.reason,
    description: m.job.desc,
    missions: [],
    matchedSkills: m.matching_skills,
    missingSkills: m.missing_skills,
    url:      m.job.url || undefined,
  }
}

// ─── Processing view ─────────────────────────────────────────────────────────
function ProcessingView({ progress, step }: { progress: number; step: string }) {
  return (
    <div className="animate-fade-up">
      <div className="card rounded-xl p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="h-2 w-2 rounded-full bg-accent pulse-dot" />
          <span className="text-sm font-medium text-ink">Analyse en cours</span>
          <span className="ml-auto text-sm font-mono text-accent">{progress}%</span>
        </div>
        {/* Progress bar */}
        <div className="h-1.5 bg-line/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-accent rounded-full transition-all duration-700"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="mt-3 text-xs text-muted">{step}</p>
      </div>
      <MatchSkeletonList count={3} />
    </div>
  )
}

// ─── Dashboard header ─────────────────────────────────────────────────────────
function AnalysisHeader({ analysis }: { analysis: Analysis }) {
  const count  = analysis.matches?.length ?? 0
  const strong = analysis.matches?.filter((m) => m.score >= 5).length ?? 0

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-6">
      <div>
        <h1 className="text-lg font-semibold text-ink">Résultats de votre analyse</h1>
        <p className="text-xs text-muted mt-0.5">
          Mise à jour le {formatDate(analysis.created_at)} · Actualisation automatique chaque nuit
        </p>
      </div>
      <div className="flex items-center gap-3 sm:ml-auto">
        <div className="card rounded-lg px-3 py-2 text-center min-w-[64px]">
          <div className="text-lg font-semibold text-ink">{count}</div>
          <div className="text-[10px] text-muted uppercase tracking-wide">offres</div>
        </div>
        <div className="card rounded-lg px-3 py-2 text-center min-w-[64px]">
          <div className="text-lg font-semibold text-accent">{strong}</div>
          <div className="text-[10px] text-muted uppercase tracking-wide">forts matchs</div>
        </div>
      </div>
    </div>
  )
}

// ─── No-search CTA ───────────────────────────────────────────────────────────
// The cooldown is enforced server-side, per user, against Analysis.created_at
// (see POST /analysis/search) - nothing about it is ever persisted client-side,
// so there's nothing here to leak across accounts on the same browser or to tamper
// with. `rateLimitHours` only ever reflects a 429 this session's own request hit.
function NoSearchCTA({
  onLaunch, launching, rateLimitHours, inProgress,
}: {
  onLaunch: () => void
  launching: boolean
  rateLimitHours: number | null
  inProgress: boolean
}) {
  const blocked = rateLimitHours !== null || inProgress
  const tooltip = rateLimitHours !== null
    ? `Limite atteinte - réessayez dans ${rateLimitHours}h`
    : inProgress ? "Une recherche est déjà en cours" : null

  return (
    <div className="animate-fade-up py-16 flex flex-col items-center gap-4 text-center">
      <div className="h-14 w-14 rounded-2xl bg-accent/10 flex items-center justify-center">
        <Search className="h-7 w-7 text-accent" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-ink mb-1">Votre profil est prêt</h2>
        <p className="text-sm text-muted max-w-xs">
          Lancez une recherche pour trouver les offres qui correspondent à votre profil et vos préférences.
        </p>
      </div>
      <div className="relative group">
        <button
          onClick={onLaunch}
          disabled={launching || blocked}
          className="btn-accent ring-focus inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {launching
            ? <><Loader2 className="h-4 w-4 animate-spin" /> Lancement…</>
            : <><Search className="h-4 w-4" /> Lancer une recherche</>}
        </button>
        {tooltip && (
          <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 flex flex-col items-center opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-20">
            <div
              className="rounded-lg px-3 py-1.5 text-[11px] font-medium text-white whitespace-nowrap flex items-center gap-1.5"
              style={{ background: "rgb(var(--ink))" }}
            >
              <Clock className="h-3 w-3 shrink-0" />
              {tooltip}
            </div>
            <div className="w-0 h-0" style={{ borderLeft: "5px solid transparent", borderRight: "5px solid transparent", borderTop: "5px solid rgb(var(--ink))" }} />
          </div>
        )}
      </div>
      <p className="text-xs text-subtle">Durée estimée : 30–60 secondes</p>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const navigate = useNavigate()

  const queryClient = useQueryClient()
  const { data: analysis, error: analysisError, isLoading: analysisLoading } = useLatestAnalysis()
  const is404 = (analysisError as any)?.response?.status === 404

  // Only fetch CV data when analysis returns 404 (to decide: noSearch vs redirect to onboarding)
  const { isLoading: cvCheckLoading, isError: noCv } = useQuery({
    queryKey: QK.cvData,
    queryFn:  () => getCvData().then(r => r.data),
    enabled:  is404,
    staleTime: 5 * 60 * 1000,
    retry:    (_, err: any) => err?.response?.status !== 404,
  })

  const noSearch  = is404 && !cvCheckLoading && !noCv
  const loadError = !!analysisError && !is404

  const [launching, setLaunching] = useState(false)
  // Set only from a 429 this session's own request received - never persisted,
  // so it can't leak across accounts sharing a browser or be edited to fake a
  // block/unblock. The server remains the sole source of truth for enforcement.
  const [rateLimitHours, setRateLimitHours] = useState<number | null>(null)
  const [inProgress, setInProgress] = useState(false)
  const [progress, setProgress]   = useState(8)
  const [step, setStep]           = useState("Initialisation…")
  const [filters, setFilters]     = useState<MatchFilters>(DEFAULT_FILTERS)
  const [page, setPage]           = useState(1)
  const [selected, setSelected]   = useState<DesignJobMatch | null>(null)
  const [reportOpen, setReportOpen] = useState(false)

  // Navigate to onboarding when 404 on analysis AND no CV profile exists
  useEffect(() => {
    if (is404 && !cvCheckLoading && noCv) navigate("/setup", { replace: true })
  }, [is404, cvCheckLoading, noCv, navigate])

  // Proactively compute (and keep live) whether the cooldown is still
  // active from the already-loaded analysis, instead of waiting for a failed
  // click to reveal it - a button that looks clickable until you try it is
  // confusing, and one that never re-enables itself once the cooldown passes
  // is just as bad. The server remains the sole source of truth for
  // enforcement (see handleLaunchSearch's 429 handling below) - this only
  // drives what the button looks like before that request is even made.
  useEffect(() => {
    if (!analysis || analysis.status !== "completed") return

    const createdAt = new Date(analysis.created_at).getTime()
    const update = () => {
      const remainingMs = SEARCH_COOLDOWN_MS - (Date.now() - createdAt)
      setRateLimitHours(remainingMs > 0 ? Math.ceil(remainingMs / 3_600_000) : null)
    }

    update()
    const interval = setInterval(update, 60_000)
    return () => clearInterval(interval)
  }, [analysis?.status, analysis?.created_at])

  const handleLaunchSearch = async () => {
    setLaunching(true)
    try {
      const res = await launchSearch()
      queryClient.setQueryData(QK.latestAnalysis, res.data)
    } catch (e: unknown) {
      const err = e as { response?: { status?: number; data?: { detail?: { wait_hours?: number } } } }
      const status = err.response?.status
      if (status === 429) {
        const waitHours = err.response?.data?.detail?.wait_hours
        setRateLimitHours(waitHours ? Math.ceil(waitHours) : 4)
      } else if (status === 409) {
        setInProgress(true)
      }
    } finally {
      setLaunching(false)
    }
  }

  // SSE - only while processing
  const isProcessing = analysis?.status === "processing" || analysis?.status === "pending"

  useEffect(() => {
    if (!analysis?.id || !isProcessing) return
    let cancelled = false
    const ctrl = new AbortController()

    const listenSSE = async () => {
      try {
        const res = await fetch(`/api/analysis/${analysis.id}/stream`, {
          credentials: "include",
          signal: ctrl.signal,
        })
        if (!res.ok || !res.body) return
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ""
        while (!cancelled) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const lines = buf.split("\n\n")
          buf = lines.pop() ?? ""
          for (const line of lines) {
            const data = line.startsWith("data: ") ? line.slice(6) : null
            if (!data) continue
            try {
              const event = JSON.parse(data)
              if (event.node) {
                const p = NODE_PROGRESS[event.node]
                if (p !== undefined) setProgress(p)
                setStep(event.label ?? event.node)
              }
            } catch { /* ignore */ }
          }
        }
      } catch { /* aborted */ }
    }

    listenSSE()
    return () => { cancelled = true; ctrl.abort() }
  }, [analysis?.id, isProcessing])

  // Polling - while processing
  useEffect(() => {
    if (!analysis?.id || !isProcessing) return
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const res = await getAnalysis(analysis.id)
        queryClient.setQueryData(QK.latestAnalysis, res.data)
        if (res.data.status === "processing" || res.data.status === "pending") {
          timer = setTimeout(poll, POLL_MS)
        } else if (res.data.status === "completed") {
          setProgress(100)
          setStep("Terminé")
        }
      } catch { /* ignore polling errors */ }
    }
    timer = setTimeout(poll, POLL_MS)
    return () => clearTimeout(timer)
  }, [analysis?.id, isProcessing])

  const adaptedMatches = useMemo(
    () => (analysis?.matches ?? []).map((m, i) => adaptMatch(m, i)),
    [analysis?.matches]
  )
  const visible = useMemo(() => applyFilters(adaptedMatches, filters), [adaptedMatches, filters])

  const PAGE_SIZE = 12
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE))
  useEffect(() => { setPage(1) }, [filters, analysis?.id])
  const pageItems = useMemo(
    () => visible.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [visible, page]
  )

  // No analysis and no CV yet - a brand new user. The redirect effect above
  // handles navigation to /setup, but it only fires *after* this render
  // commits - without this guard, this render would still fall through to the
  // main dashboard tree below with `analysis` undefined and crash.
  if (analysisLoading || (is404 && cvCheckLoading) || (is404 && noCv)) {
    return (
      <Layout>
        {/* Same wide container as the real grid below (max-w-400, not the
            narrower max-w-3xl used by the "processing"/error states) - the
            common case on reload is an existing user with existing results,
            so the skeleton should already be shaped like that grid instead
            of reflowing into columns the moment real data arrives. */}
        <div className="mx-auto px-4 sm:px-6 py-8 max-w-400">
          <MatchSkeletonList count={6} />
        </div>
      </Layout>
    )
  }

  if (noSearch) {
    return (
      <Layout title="Tableau de bord">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
          <NoSearchCTA onLaunch={handleLaunchSearch} launching={launching} rateLimitHours={rateLimitHours} inProgress={inProgress} />
        </div>
      </Layout>
    )
  }

  if (loadError) {
    return (
      <Layout>
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16 text-center">
          <AlertCircle className="h-10 w-10 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-ink mb-2">Impossible de charger vos résultats</h2>
          <p className="text-sm text-muted mb-6">Vérifiez votre connexion et réessayez.</p>
          <button onClick={() => window.location.reload()}
            className="btn-accent ring-focus inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm">
            <RefreshCw className="h-4 w-4" /> Réessayer
          </button>
        </div>
      </Layout>
    )
  }

  if (analysis?.status === "failed") {
    return (
      <Layout>
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-16 text-center">
          <AlertCircle className="h-10 w-10 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-ink mb-2">L'analyse a échoué</h2>
          <p className="text-sm text-muted mb-6">{analysis.error ?? "Une erreur inattendue s'est produite."}</p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={handleLaunchSearch}
              disabled={launching}
              className="btn-accent ring-focus inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {launching
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Lancement…</>
                : <><RefreshCw className="h-4 w-4" /> Relancer la recherche</>}
            </button>
            <a href="/settings" className="btn-ghost ring-focus inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm">
              Mettre à jour votre profil
            </a>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout
      title="Tableau de bord"
      subtitle="Vos offres d'emploi correspondantes"
      actions={
        <>
          <div className="relative group">
            <button
              onClick={handleLaunchSearch}
              disabled={launching || inProgress || rateLimitHours !== null || isProcessing}
              className="relative btn-accent ring-focus rounded-xl px-4 py-2.5 text-[13px] font-semibold flex items-center gap-2 shadow-[0_4px_18px_-2px_rgba(5,150,105,0.55)] hover:shadow-[0_6px_22px_-2px_rgba(5,150,105,0.7)] hover:-translate-y-0.5 transition disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none disabled:translate-y-0"
            >
              {launching ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Recherche…</>
              ) : (
                <>
                  <span className="relative flex h-4 w-4 items-center justify-center shrink-0">
                    {!(inProgress || rateLimitHours !== null || isProcessing) && (
                      <span className="absolute inline-flex h-full w-full rounded-full bg-white/40 animate-ping" />
                    )}
                    <Radar className="relative h-4 w-4" />
                  </span>
                  Trouver mes offres
                </>
              )}
            </button>

            {(rateLimitHours !== null || inProgress) && (
              <div className="pointer-events-none absolute top-full left-1/2 -translate-x-1/2 mt-2 flex flex-col items-center opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-20">
                <div className="w-0 h-0" style={{ borderLeft: "5px solid transparent", borderRight: "5px solid transparent", borderBottom: "5px solid rgb(var(--ink))" }} />
                <div
                  className="rounded-lg px-3 py-2 text-[11px] font-medium text-white whitespace-nowrap flex items-center gap-1.5"
                  style={{ background: "rgb(var(--ink))" }}
                >
                  <Clock className="h-3 w-3 shrink-0" />
                  {rateLimitHours !== null ? `Prochaine recherche possible dans ${rateLimitHours}h` : "Une recherche est déjà en cours"}
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => navigate("/applications?new=1")}
            className="btn-accent ring-focus rounded-lg px-3 py-1.5 text-[12px] font-medium flex items-center gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" /> Nouvelle candidature
          </button>
        </>
      }
    >
      <div className={`mx-auto px-4 sm:px-6 py-8 ${isProcessing ? "max-w-3xl" : "max-w-400"}`}>
        {isProcessing ? (
          <ProcessingView progress={progress} step={step} />
        ) : (
          <div className="animate-fade-up">
            <AnalysisHeader analysis={analysis!} />

            {analysis?.keywords && analysis.keywords.length > 0 && (
              <div className="card rounded-xl px-4 py-3 flex flex-wrap items-center gap-1.5 mb-5">
                <span className="text-xs text-subtle mr-1">Mots-clés :</span>
                {analysis.keywords.map((k) => (
                  <span key={k} className="text-xs font-mono px-2 py-0.5 rounded-md bg-line/5 bd text-muted">{k}</span>
                ))}
              </div>
            )}

            <FilterBar filters={filters} onChange={setFilters} />

            <div className="mt-5 flex items-center justify-between mb-3">
              <p className="text-sm font-medium text-ink">
                Correspondances <span className="text-muted font-normal">({visible.length})</span>
              </p>
            </div>

            {visible.length === 0 ? (
              <EmptyState onAction={() => setFilters(DEFAULT_FILTERS)} actionLabel="Réinitialiser les filtres" />
            ) : (
              <>
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {pageItems.map((m) => (
                    <MatchCard key={m.id} match={m} onOpen={() => setSelected(m)} />
                  ))}
                </div>
                <Pagination page={page} pageCount={pageCount} onChange={setPage} />
              </>
            )}

            {selected && (
              <MatchDetailModal
                match={selected}
                analysisId={analysis!.id}
                onClose={() => setSelected(null)}
                onApply={() => navigate(
                  `/documents?analysisId=${analysis!.id}&jobIndex=${selected.originalIndex}` +
                  `&company=${encodeURIComponent(selected.company)}&title=${encodeURIComponent(selected.title)}`
                )}
                onSaveToggle={() => setSelected({ ...selected })}
              />
            )}

            {analysis?.final_report && (
              <div className="mt-8 card rounded-xl overflow-hidden">
                <button
                  onClick={() => setReportOpen((v) => !v)}
                  aria-expanded={reportOpen}
                  className={`w-full flex items-center gap-2.5 px-5 py-3.5 text-left ${reportOpen ? "border-b border-line/10" : ""}`}
                >
                  <FileText className="h-4 w-4 text-accent" />
                  <h3 className="text-sm font-semibold text-ink flex-1">Rapport de synthèse</h3>
                  <ChevronDown className={`h-4 w-4 text-subtle transition-transform ${reportOpen ? "rotate-180" : ""}`} />
                </button>
                {reportOpen && (
                  <div className="px-5 py-5">
                    <MarkdownReport markdown={analysis.final_report} />
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}