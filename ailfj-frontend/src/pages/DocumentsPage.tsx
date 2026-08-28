import { useEffect, useRef, useState } from "react"
import { useLatestAnalysis } from "../lib/queries"
import { useSearchParams } from "react-router-dom"
import {
  FileText, Mail, ChevronDown, ChevronUp,
  ZoomIn, ZoomOut, Download, Loader2,
  FileX, RefreshCw, Sparkles, RotateCcw, X, Search, Menu,
} from "lucide-react"
import { Document, Page, pdfjs } from "react-pdf"
import Layout from "../components/Layout"
import { fetchCvPdf, fetchCoverLetterPdfBlob, fetchExistingCoverLetterPdfBlob } from "../api/apply"
import { fetchOrRefineApplicationCoverLetter } from "../api/applications"
import { getSavedJobs, unsaveJob } from "../lib/savedJobs"
import {
  cacheCL, cacheCLContent, getCachedCLUrl, getCachedCLContent,
  clearCachedCL, hasCachedCL, getCachedCLTimestamp,
} from "../lib/clCache"

function timeAgo(ms: number): string {
  const diffMin = Math.floor((Date.now() - ms) / 60_000)
  if (diffMin < 1) return "à l'instant"
  if (diffMin < 60) return `il y a ${diffMin} min`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `il y a ${diffH} h`
  const diffD = Math.floor(diffH / 24)
  if (diffD === 1) return "hier"
  if (diffD < 7) return `il y a ${diffD} j`
  return new Date(ms).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })
}

// PDF.js worker - renders PDF to <canvas>, no browser native viewer, no black borders
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString()

// ── Types ─────────────────────────────────────────────────────────────────────

type DocKind    = "cv" | "cl"
type CanvasState = "empty" | "pre-gen" | "loading" | "loaded" | "refine" | "error"

interface DocItem {
  id: string
  kind: DocKind
  label: string
  sub?: string
  // "analysis" - cover letter tied to a Cortex match (analysisId + jobIndex).
  // "application" - cover letter generated for a manually added application (Mes candidatures).
  source: "analysis" | "application"
  analysisId: string
  jobIndex?: number
  applicationId?: string
}

// ── Constants ─────────────────────────────────────────────────────────────────

const ZOOM_MIN   = 0.5
const ZOOM_MAX   = 3.0
const ZOOM_STEP  = 0.25
const LIST_LIMIT = 4

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DocumentsPage() {
  const [searchParams] = useSearchParams()
  const initAnalysisId    = searchParams.get("analysisId")
  const initJobIndex      = searchParams.get("jobIndex")
  const initApplicationId = searchParams.get("applicationId")
  const initCompany       = searchParams.get("company")
  const initTitle         = searchParams.get("title")

  const [docs, setDocs]               = useState<DocItem[]>([])
  const [active, setActive]           = useState<DocItem | null>(null)
  const [canvasState, setCanvasState] = useState<CanvasState>("empty")
  const [fetchError, setFetchError]   = useState<string | null>(null)
  const [pdfUrl, setPdfUrl]           = useState<string | null>(null)
  const [zoom, setZoom]               = useState(1)
  const [suggestion, setSuggestion]   = useState("")
  const [refineInstruction, setRefineInstruction] = useState("")
  const [listOpen, setListOpen]       = useState(true)
  const [showAll, setShowAll]         = useState(false)
  const [query, setQuery]             = useState("")
  const [mobileListOpen, setMobileListOpen] = useState(false)
  const prevUrl = useRef<string | null>(null)

  const { data: latestAnalysis } = useLatestAnalysis()

  // ── Build doc list when analysis is available ────────────────────────────────

  useEffect(() => {
    if (!latestAnalysis) return
    const id    = latestAnalysis.id
    const saved = getSavedJobs()

    const items: DocItem[] = [
      { id: "cv", kind: "cv", label: "Mon CV", sub: "Profil principal", source: "analysis", analysisId: id },
    ]

    if (initAnalysisId && initJobIndex !== null) {
      const fromOffer: DocItem = {
        id: `cl-offer-${initJobIndex}`,
        kind: "cl",
        label: initCompany ? `Lettre - ${initCompany}` : "Lettre de motivation",
        sub: initTitle ?? undefined,
        source: "analysis",
        analysisId: initAnalysisId,
        jobIndex: Number(initJobIndex),
      }
      items.push(fromOffer)
      setActive(fromOffer)
      setCanvasState("pre-gen")
    }

    const offerKey = initAnalysisId && initJobIndex !== null
      ? `${initAnalysisId}-${initJobIndex}`
      : null

    for (const j of saved.slice(0, 20)) {
      const key = `${j.analysisId}-${j.originalIndex}`
      if (key === offerKey) continue
      items.push({
        id: `cl-${j.id}`,
        kind: "cl",
        label: `Lettre - ${j.company}`,
        sub: j.title,
        source: "analysis",
        analysisId: j.analysisId,
        jobIndex: j.originalIndex,
      })
    }

    setDocs((prev) => [...items, ...prev.filter((d) => d.source === "application")])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestAnalysis?.id])

  // ── Open a cover letter generated from "Mes candidatures" (independent of any analysis) ──

  useEffect(() => {
    if (!initApplicationId) return
    const fromApplication: DocItem = {
      id: `cl-application-${initApplicationId}`,
      kind: "cl",
      label: initCompany ? `Lettre - ${initCompany}` : "Lettre de motivation",
      sub: initTitle ?? undefined,
      source: "application",
      analysisId: "",
      applicationId: initApplicationId,
    }
    setDocs((prev) => [fromApplication, ...prev.filter((d) => d.id !== fromApplication.id)])
    setActive(fromApplication)
    doLoad(fromApplication, "")
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initApplicationId])

  // ── Blob URL cleanup ────────────────────────────────────────────────────────

  function revokePdf() {
    if (prevUrl.current) {
      URL.revokeObjectURL(prevUrl.current)
      prevUrl.current = null
    }
    setPdfUrl(null)
  }

  useEffect(() => () => revokePdf(), [])

  // ── Actions ─────────────────────────────────────────────────────────────────

  async function selectDoc(doc: DocItem) {
    setMobileListOpen(false)
    if (active?.id === doc.id && canvasState !== "error") return
    setActive(doc)
    setSuggestion("")
    revokePdf()
    if (doc.kind === "cv" || doc.source === "application") {
      // Applications' cover letters are already generated by the time they show up
      // here - no suggestion prompt needed, just fetch and display.
      doLoad(doc, "")
      return
    }

    // Check localStorage cache first - skip Generate screen if already generated
    const cached = getCachedCLUrl(doc.analysisId, doc.jobIndex ?? 0)
    if (cached) {
      prevUrl.current = cached
      setPdfUrl(cached)
      setCanvasState("loaded")
      setZoom(1)
      return
    }

    // Not in the local cache (cleared, different device, cap evicted it) - the
    // server persists the structured content durably, so check there before
    // asking the user to regenerate from scratch.
    setCanvasState("loading")
    try {
      const result = await fetchExistingCoverLetterPdfBlob(doc.analysisId, doc.jobIndex ?? 0)
      if (!result) {
        setCanvasState("pre-gen")
        return
      }
      await cacheCL(doc.analysisId, doc.jobIndex ?? 0, result.blob)
      if (result.content) cacheCLContent(doc.analysisId, doc.jobIndex ?? 0, result.content)
      const url = URL.createObjectURL(result.blob)
      prevUrl.current = url
      setPdfUrl(url)
      setCanvasState("loaded")
      setZoom(1)
    } catch {
      setCanvasState("pre-gen")
    }
  }

  async function doLoad(
    doc: DocItem,
    sug: string,
    previousContent: Record<string, unknown> | null = null,
  ) {
    setCanvasState("loading")
    setFetchError(null)
    try {
      let url: string
      if (doc.kind === "cv") {
        url = await fetchCvPdf(doc.analysisId)
      } else if (doc.source === "application" && doc.applicationId) {
        const { blob } = await fetchOrRefineApplicationCoverLetter(doc.applicationId, sug)
        url = URL.createObjectURL(blob)
      } else {
        const { blob, content } = await fetchCoverLetterPdfBlob(
          doc.analysisId, doc.jobIndex ?? 0, sug, previousContent,
        )
        await cacheCL(doc.analysisId, doc.jobIndex ?? 0, blob)
        if (content) cacheCLContent(doc.analysisId, doc.jobIndex ?? 0, content)
        url = URL.createObjectURL(blob)
      }
      prevUrl.current = url
      setPdfUrl(url)
      setCanvasState("loaded")
      setZoom(1)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erreur inconnue"
      console.error("[Documents] fetch failed:", msg)
      setFetchError(msg)
      setCanvasState("error")
    }
  }

  function handleGenerate() {
    if (!active) return
    doLoad(active, suggestion, null)
  }

  function handleRegenerate() {
    // Keep the PDF visible - switch to "refine" overlay instead of wiping to pre-gen
    setRefineInstruction("")
    setCanvasState("refine")
  }

  function handleRefine() {
    if (!active) return
    const prevContent = getCachedCLContent(active.analysisId, active.jobIndex ?? 0)
    clearCachedCL(active.analysisId, active.jobIndex ?? 0)
    revokePdf()
    doLoad(active, refineInstruction, prevContent)
  }

  function handleCancelRefine() {
    setRefineInstruction("")
    setCanvasState("loaded")
  }

  function handleRemoveDoc(doc: DocItem) {
    // Clear PDF cache
    if (doc.kind === "cl") clearCachedCL(doc.analysisId, doc.jobIndex ?? 0)
    // Unsave the job if it came from saved jobs
    const savedJob = getSavedJobs().find(
      (j) => j.analysisId === doc.analysisId && j.originalIndex === doc.jobIndex
    )
    if (savedJob) unsaveJob(savedJob.id)
    // Remove from local list
    setDocs((prev) => prev.filter((d) => d.id !== doc.id))
    if (active?.id === doc.id) {
      setActive(null)
      revokePdf()
      setCanvasState("empty")
    }
  }

  function handleDownload() {
    if (!pdfUrl || !active) return
    const a = document.createElement("a")
    a.href = pdfUrl
    a.download = active.kind === "cv"
      ? "mon_cv.pdf"
      : `lettre_${active.label.replace(/[^a-z0-9]/gi, "_")}.pdf`
    a.click()
  }

  const zoomIn  = () => setZoom((z) => Math.min(ZOOM_MAX, +(z + ZOOM_STEP).toFixed(2)))
  const zoomOut = () => setZoom((z) => Math.max(ZOOM_MIN, +(z - ZOOM_STEP).toFixed(2)))

  const q = query.trim().toLowerCase()
  const filteredDocs = q
    ? docs.filter((d) => d.label.toLowerCase().includes(q) || (d.sub ?? "").toLowerCase().includes(q))
    : docs
  const visible = showAll ? filteredDocs : filteredDocs.slice(0, LIST_LIMIT)
  const hasMore = filteredDocs.length > LIST_LIMIT

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <Layout title="Documents" subtitle="Gérez et visualisez vos documents">
      <div className="flex relative" style={{ height: "calc(100vh - 56px)" }}>

        {/* ── Mobile backdrop ────────────────────────────────────────────── */}
        {mobileListOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/40 sm:hidden"
            onClick={() => setMobileListOpen(false)}
          />
        )}

        {/* ── Left panel ─────────────────────────────────────────────────── */}
        <div
          className={`flex flex-col shrink-0 fixed sm:static inset-y-0 left-0 z-40 transition-transform sm:translate-x-0 ${
            mobileListOpen ? "translate-x-0" : "-translate-x-full"
          }`}
          style={{
            width: 260,
            borderRight: "1px solid rgb(var(--line) / var(--line-a))",
            background: "rgb(var(--card))",
          }}
        >
          {/* Panel header - clickable to collapse */}
          <button
            onClick={() => setListOpen((v) => !v)}
            className="flex items-center justify-between px-4 h-11 shrink-0 hover:bg-line/4 transition text-left"
            style={{ borderBottom: "1px solid rgb(var(--line) / var(--line-a))" }}
          >
            <span className="text-[11px] font-semibold text-muted uppercase tracking-widest select-none">
              Mes documents
            </span>
            {listOpen
              ? <ChevronUp className="h-3.5 w-3.5 text-subtle" />
              : <ChevronDown className="h-3.5 w-3.5 text-subtle" />
            }
          </button>

          {/* Search */}
          {listOpen && docs.length > 0 && (
            <div className="px-2.5 pt-2 shrink-0">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-subtle pointer-events-none" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Rechercher un document…"
                  className="input-base ring-focus w-full pl-8 h-8 text-[12px]"
                />
              </div>
            </div>
          )}

          {/* List items */}
          {listOpen && (
            <div className="flex-1 overflow-y-auto py-2 px-2 no-scrollbar">
              {docs.length === 0 ? (
                <p className="text-[12px] text-subtle text-center px-3 py-8 leading-relaxed">
                  Aucun document.<br />Lancez d'abord une analyse.
                </p>
              ) : filteredDocs.length === 0 ? (
                <p className="text-[12px] text-subtle text-center px-3 py-8 leading-relaxed">
                  Aucun résultat pour « {query} »
                </p>
              ) : (
                <div className="space-y-0.5">
                  {visible.map((doc) => {
                    const isActive = active?.id === doc.id
                    const Icon     = doc.kind === "cv" ? FileText : Mail
                    const cached   = doc.kind === "cl" && hasCachedCL(doc.analysisId, doc.jobIndex ?? 0)
                    const cachedAt = cached ? getCachedCLTimestamp(doc.analysisId, doc.jobIndex ?? 0) : null
                    return (
                      <div key={doc.id} className="group/item relative">
                        <button
                          onClick={() => selectDoc(doc)}
                          className={`w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-lg text-left transition-colors pr-7 ${
                            isActive ? "bg-accent/10" : "hover:bg-line/5"
                          }`}
                        >
                          <div className={`h-7 w-7 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                            isActive ? "bg-accent/20" : "bg-line/5 bd"
                          }`}>
                            <Icon className={`h-3.5 w-3.5 ${isActive ? "text-accent" : "text-subtle"}`} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className={`text-[12px] font-medium truncate ${isActive ? "text-accent" : "text-ink"}`}>
                              {doc.label}
                            </p>
                            <p className="text-[10px] text-subtle truncate mt-0.5">
                              {cachedAt ? `Généré ${timeAgo(cachedAt)} · ` : ""}{doc.sub ?? ""}
                            </p>
                          </div>
                        </button>
                        {/* Remove button - CL only, visible on hover */}
                        {doc.kind === "cl" && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleRemoveDoc(doc) }}
                            title="Supprimer"
                            className="absolute right-1.5 top-1/2 -translate-y-1/2 h-5 w-5 rounded flex items-center justify-center text-subtle hover:text-red-400 hover:bg-red-400/10 transition opacity-0 group-hover/item:opacity-100"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </div>
                    )
                  })}

                  {/* Show more / less */}
                  {hasMore && (
                    <button
                      onClick={() => setShowAll((v) => !v)}
                      className="w-full flex items-center justify-center gap-1.5 mt-1 py-2 rounded-lg text-[11px] text-subtle hover:text-muted hover:bg-line/5 transition"
                    >
                      {showAll
                        ? <><ChevronUp className="h-3 w-3" /> Réduire</>
                        : <><ChevronDown className="h-3 w-3" /> Voir plus · {filteredDocs.length - LIST_LIMIT} de plus</>
                      }
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Canvas area ────────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0 relative">

          {/* Toolbar */}
          <div
            className="h-12 flex items-center gap-2 px-4 shrink-0"
            style={{
              borderBottom: "1px solid rgb(var(--line) / var(--line-a))",
              background: "rgb(var(--card))",
            }}
          >
            {/* Mobile: open the documents drawer */}
            <button
              onClick={() => setMobileListOpen(true)}
              className="sm:hidden grid place-items-center h-8 w-8 rounded-lg btn-ghost text-muted shrink-0"
              title="Mes documents"
            >
              <Menu className="h-4 w-4" />
            </button>

            {active ? (
              <>
                {/* Doc identity */}
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  {active.kind === "cv"
                    ? <FileText className="h-3.5 w-3.5 text-accent shrink-0" />
                    : <Mail className="h-3.5 w-3.5 text-accent shrink-0" />
                  }
                  <span className="text-[12px] font-medium text-ink truncate">{active.label}</span>
                  {active.sub && (
                    <span className="text-[11px] text-subtle hidden sm:block shrink-0">· {active.sub}</span>
                  )}
                </div>

                {/* Zoom - only when PDF loaded */}
                {canvasState === "loaded" && (
                  <>
                    <div
                      className="flex items-center rounded-lg overflow-hidden shrink-0"
                      style={{ border: "1px solid rgb(var(--line) / var(--line-a))" }}
                    >
                      <button onClick={zoomOut} disabled={zoom <= ZOOM_MIN}
                        className="h-7 w-7 flex items-center justify-center text-muted hover:bg-line/5 hover:text-ink transition disabled:opacity-30"
                        title="Zoom arrière">
                        <ZoomOut className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={() => setZoom(1)}
                        className="h-7 w-14 text-[11px] font-mono text-muted hover:bg-line/5 hover:text-ink transition"
                        title="Réinitialiser"
                        style={{ borderLeft: "1px solid rgb(var(--line) / var(--line-a))", borderRight: "1px solid rgb(var(--line) / var(--line-a))" }}>
                        {Math.round(zoom * 100)}%
                      </button>
                      <button onClick={zoomIn} disabled={zoom >= ZOOM_MAX}
                        className="h-7 w-7 flex items-center justify-center text-muted hover:bg-line/5 hover:text-ink transition disabled:opacity-30"
                        title="Zoom avant">
                        <ZoomIn className="h-3.5 w-3.5" />
                      </button>
                    </div>

                    {/* Regenerate - CL only */}
                    {active.kind === "cl" && (
                      <button onClick={handleRegenerate}
                        className="btn-ghost ring-focus flex items-center gap-1.5 rounded-lg px-3 h-8 text-[12px] shrink-0">
                        <RotateCcw className="h-3.5 w-3.5" />
                        <span className="hidden sm:inline">Régénérer</span>
                      </button>
                    )}

                    {/* Download */}
                    <button onClick={handleDownload}
                      className="btn-accent ring-focus flex items-center gap-1.5 rounded-lg px-3 h-8 text-[12px] font-medium shrink-0">
                      <Download className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">Télécharger</span>
                    </button>
                  </>
                )}
              </>
            ) : (
              <p className="text-[12px] text-subtle">Sélectionnez un document dans la liste</p>
            )}
          </div>

          {/* Canvas viewport - dot grid, style Canva */}
          <div
            className="flex-1 overflow-auto"
            style={{
              backgroundColor: "rgb(var(--well))",
              backgroundImage: "radial-gradient(circle, rgb(var(--line) / 0.25) 1.5px, transparent 1.5px)",
              backgroundSize: "24px 24px",
            }}
          >
            {/* min-width:max-content pour scroll horizontal quand zoomé */}
            <div
              className="relative flex flex-col items-center px-10 py-10"
              style={{ minWidth: "max-content", minHeight: "100%" }}
            >

              {/* ── Empty ── */}
              {canvasState === "empty" && (
                <div className="flex items-center justify-center" style={{ minHeight: "calc(100vh - 56px - 48px)" }}>
                  <EmptyCanvas />
                </div>
              )}

              {/* ── Pre-generate (CL selected) ── */}
              {canvasState === "pre-gen" && active && (
                <div className="flex items-center justify-center w-full" style={{ minHeight: "calc(100vh - 56px - 48px)" }}>
                <GeneratePrompt
                  label={active.label}
                  sub={active.sub}
                  suggestion={suggestion}
                  onSuggestion={setSuggestion}
                  onGenerate={handleGenerate}
                />
                </div>
              )}

              {/* ── Loading ── */}
              {canvasState === "loading" && (
                <div className="flex flex-col items-center justify-center gap-3" style={{ minHeight: "calc(100vh - 56px - 48px)" }}>
                  <div className="relative">
                    <div className="h-14 w-14 rounded-2xl bg-accent/10 flex items-center justify-center">
                      <Sparkles className="h-7 w-7 text-accent" />
                    </div>
                    <Loader2 className="absolute -bottom-1 -right-1 h-5 w-5 text-accent animate-spin" />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-medium text-ink">
                      {active?.kind === "cl" ? "Génération en cours…" : "Chargement…"}
                    </p>
                    <p className="text-xs text-muted mt-0.5">
                      {active?.kind === "cl" ? "L'IA rédige votre lettre de motivation" : "Récupération du document"}
                    </p>
                  </div>
                </div>
              )}

              {/* ── Error ── */}
              {canvasState === "error" && active && (
                <div className="flex flex-col items-center justify-center gap-4 text-center" style={{ minHeight: "calc(100vh - 56px - 48px)" }}>
                  <div className="h-14 w-14 rounded-2xl bg-red-500/10 flex items-center justify-center">
                    <FileX className="h-7 w-7 text-red-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-ink mb-1">Chargement impossible</p>
                    <p className="text-xs text-muted mb-2 max-w-xs">
                      Vérifiez que l'analyse est terminée et réessayez.
                    </p>
                    {fetchError && (
                      <p className="text-[10px] font-mono text-red-400 bg-red-500/8 border border-red-500/15 rounded px-2 py-1 max-w-xs break-all mb-3">
                        {fetchError}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => active.kind === "cl" ? setCanvasState("pre-gen") : doLoad(active, "")}
                    className="btn-ghost ring-focus inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm"
                  >
                    <RefreshCw className="h-3.5 w-3.5" /> Réessayer
                  </button>
                </div>
              )}

              {/* ── PDF loaded - rendered via PDF.js to <canvas>, no browser viewer chrome ── */}
              {(canvasState === "loaded" || canvasState === "refine") && pdfUrl && (
                <PdfViewer url={pdfUrl} zoom={zoom} />
              )}
            </div>
          </div>

          {/* ── Refine panel - slides up from bottom over the canvas ── */}
          {canvasState === "refine" && active && (
            <div
              className="absolute bottom-0 left-0 right-0 z-30 animate-fade-up"
              style={{
                background: "rgb(var(--card))",
                borderTop: "1px solid rgb(var(--line) / var(--line-a))",
                boxShadow: "0 -8px 32px rgba(0,0,0,0.12)",
              }}
            >
              <div className="max-w-xl mx-auto px-6 py-5">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="h-4 w-4 text-accent" />
                  <p className="text-sm font-semibold text-ink">Affiner la lettre</p>
                  <span className="text-xs text-subtle ml-1">- l'IA garde ce qui est bien, modifie ce que vous demandez</span>
                </div>
                <textarea
                  autoFocus
                  value={refineInstruction}
                  onChange={(e) => setRefineInstruction(e.target.value)}
                  placeholder="Ex : rends l'intro plus dynamique, ajoute mon expérience en Python dans le 2e paragraphe, change le ton en plus formel…"
                  rows={3}
                  maxLength={500}
                  className="input-base ring-focus resize-none w-full leading-relaxed text-sm"
                  style={{ borderRadius: "0.625rem" }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleRefine()
                  }}
                />
                <div className="flex items-center justify-between mt-3">
                  <p className="text-[10px] text-subtle">{refineInstruction.length}/500 · Ctrl+Entrée pour lancer</p>
                  <div className="flex items-center gap-2">
                    <button onClick={handleCancelRefine}
                      className="btn-ghost ring-focus rounded-lg px-3 h-8 text-xs">
                      Annuler
                    </button>
                    <button onClick={handleRefine}
                      className="btn-accent ring-focus flex items-center gap-1.5 rounded-lg px-4 h-8 text-xs font-semibold">
                      <Sparkles className="h-3.5 w-3.5" />
                      Affiner
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

// Renders every PDF page to <canvas> via PDF.js - no browser viewer, no dark chrome
function PdfViewer({ url, zoom }: { url: string; zoom: number }) {
  const [numPages, setNumPages] = useState(0)

  return (
    <Document
      file={url}
      onLoadSuccess={({ numPages }) => setNumPages(numPages)}
      loading={
        <div className="flex flex-col items-center gap-2 py-20">
          <Loader2 className="h-6 w-6 text-accent animate-spin" />
          <span className="text-xs text-muted">Rendu du document…</span>
        </div>
      }
      error={
        <div className="flex flex-col items-center gap-2 py-20">
          <FileX className="h-6 w-6 text-red-400" />
          <span className="text-xs text-muted">Impossible de lire ce PDF</span>
        </div>
      }
    >
      {Array.from({ length: numPages }, (_, i) => (
        <div
          key={i}
          style={{
            marginBottom: i < numPages - 1 ? 20 : 0,
            borderRadius: 3,
            overflow: "hidden",
            boxShadow: "0 2px 8px rgba(0,0,0,0.08), 0 8px 32px rgba(0,0,0,0.12)",
            flexShrink: 0,
            lineHeight: 0,      // prevents gap under canvas in some browsers
          }}
        >
          <Page
            pageNumber={i + 1}
            scale={zoom}
            renderTextLayer={false}
            renderAnnotationLayer={false}
          />
        </div>
      ))}
    </Document>
  )
}

function EmptyCanvas() {
  return (
    <div className="flex flex-col items-center justify-center gap-5 my-auto text-center select-none">
      {/* Stacked paper illustration */}
      <div className="relative h-24 w-20 mb-1">
        {[
          { left: 8, rotate: "rotate(5deg)", z: 0 },
          { left: 4, rotate: "rotate(-2.5deg)", z: 1 },
          { left: 0, rotate: "rotate(0deg)", z: 2 },
        ].map((s, i) => (
          <div
            key={i}
            className="absolute bottom-0 right-0 w-16 h-20 rounded-sm"
            style={{
              left: s.left,
              transform: s.rotate,
              zIndex: s.z,
              background: "rgb(var(--card))",
              border: "1px solid rgb(var(--line) / 0.14)",
              boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
            }}
          >
            {i === 2 && (
              <div className="pt-4 px-3 space-y-1.5">
                {[1, 0.6, 0.8, 0.45, 0.7].map((w, j) => (
                  <div key={j} className="h-1 rounded-full" style={{ width: `${w * 100}%`, background: "rgb(var(--line) / 0.10)" }} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <div>
        <p className="text-sm font-medium text-ink mb-1">Aucun document ouvert</p>
        <p className="text-xs text-muted max-w-[200px] leading-relaxed">
          Sélectionnez un document dans le panneau de gauche.
        </p>
      </div>
    </div>
  )
}

interface GeneratePromptProps {
  label: string
  sub?: string
  suggestion: string
  onSuggestion: (v: string) => void
  onGenerate: () => void
}

function GeneratePrompt({ label, sub, suggestion, onSuggestion, onGenerate }: GeneratePromptProps) {
  return (
    <div className="flex items-center justify-center my-auto w-full">
      <div
        className="w-full max-w-md rounded-2xl p-7 flex flex-col gap-5"
        style={{
          background: "rgb(var(--card))",
          border: "1px solid rgb(var(--line) / var(--line-a))",
          boxShadow: "0 8px 40px rgba(0,0,0,0.15), 0 2px 8px rgba(0,0,0,0.08)",
        }}
      >
        {/* Header */}
        <div className="flex items-start gap-3.5">
          <div className="h-10 w-10 rounded-xl bg-accent/10 flex items-center justify-center shrink-0">
            <Sparkles className="h-5 w-5 text-accent" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink leading-none mb-1">{label}</p>
            {sub && <p className="text-xs text-muted">{sub}</p>}
          </div>
        </div>

        {/* Suggestion textarea */}
        <div>
          <label className="block text-[11px] font-medium text-muted uppercase tracking-wide mb-2">
            Instructions pour l'IA <span className="normal-case text-subtle font-normal">(optionnel)</span>
          </label>
          <textarea
            value={suggestion}
            onChange={(e) => onSuggestion(e.target.value)}
            placeholder="Ex : mets en avant mon expérience en Python, adopte un ton dynamique, cite ma passion pour les données…"
            rows={4}
            maxLength={400}
            className="input-base ring-focus resize-none leading-relaxed"
            style={{ borderRadius: "0.625rem" }}
          />
          <p className="text-[10px] text-subtle mt-1 text-right">{suggestion.length}/400</p>
        </div>

        {/* Generate button */}
        <button
          onClick={onGenerate}
          className="btn-accent ring-focus w-full rounded-xl py-3 text-sm font-semibold flex items-center justify-center gap-2"
        >
          <Sparkles className="h-4 w-4" />
          Générer la lettre de motivation
        </button>

        <p className="text-[11px] text-subtle text-center -mt-2">
          Durée estimée : 10–20 secondes
        </p>
      </div>
    </div>
  )
}
