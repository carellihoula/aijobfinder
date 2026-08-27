import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import {
  ArrowLeft, ArrowUpRight, Download, FileText, RefreshCw,
  Loader2, AlertCircle, Sparkles,
} from "lucide-react"
import { applyToJob, fetchCoverLetterPdf, fetchCvPdf } from "../api/apply"
import type { ApplyResponse } from "../api/apply"
import Layout from "../components/Layout"

type Doc = "cover_letter" | "cv"

export default function ApplyPage() {
  const { analysisId, jobIndex } = useParams<{ analysisId: string; jobIndex: string }>()
  const navigate = useNavigate()

  const [jobInfo, setJobInfo]       = useState<ApplyResponse["job"] | null>(null)
  const [activeDoc, setActiveDoc]   = useState<Doc>("cover_letter")
  const [cvUrl, setCvUrl]           = useState<string | null>(null)
  const [clUrl, setClUrl]           = useState<string | null>(null)
  const [suggestion, setSuggestion] = useState("")
  const [initError, setInitError]   = useState<string | null>(null)
  const [cvLoading, setCvLoading]   = useState(false)
  const [clLoading, setClLoading]   = useState(true)
  const [regenerating, setRegenerating] = useState(false)
  const prevClUrl = useRef<string | null>(null)

  const idx = Number(jobIndex ?? 0)

  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      if (cvUrl) URL.revokeObjectURL(cvUrl)
      if (clUrl) URL.revokeObjectURL(clUrl)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Initial load: fetch job info + cover letter in parallel, CV lazily
  useEffect(() => {
    if (!analysisId) return

    const loadInitial = async () => {
      try {
        const [applyRes, clBlobUrl] = await Promise.all([
          applyToJob(analysisId, idx),
          fetchCoverLetterPdf(analysisId, idx),
        ])
        setJobInfo(applyRes.data.job)
        setClUrl(clBlobUrl)
        prevClUrl.current = clBlobUrl
      } catch {
        setInitError("Impossible de charger les documents pour cette offre.")
      } finally {
        setClLoading(false)
      }
    }

    loadInitial()
  }, [analysisId, idx])

  // Lazy-load CV only when tab is selected
  const loadCv = useCallback(async () => {
    if (cvUrl || !analysisId) return
    setCvLoading(true)
    try {
      const url = await fetchCvPdf(analysisId)
      setCvUrl(url)
    } catch {
      /* keep null - iframe will show an error */
    } finally {
      setCvLoading(false)
    }
  }, [analysisId, cvUrl])

  const handleTabChange = (doc: Doc) => {
    setActiveDoc(doc)
    if (doc === "cv") loadCv()
  }

  const handleRegenerate = async () => {
    if (!analysisId || regenerating) return
    setRegenerating(true)
    try {
      const newUrl = await fetchCoverLetterPdf(analysisId, idx, suggestion)
      // Revoke old blob URL to free memory
      if (prevClUrl.current) URL.revokeObjectURL(prevClUrl.current)
      prevClUrl.current = newUrl
      setClUrl(newUrl)
      setSuggestion("")
      setActiveDoc("cover_letter")
    } catch {
      /* keep old URL */
    } finally {
      setRegenerating(false)
    }
  }

  const handleDownloadCl = () => {
    if (!clUrl) return
    const a = document.createElement("a")
    a.href = clUrl
    a.download = `lettre_motivation_${jobInfo?.company ?? "offre"}.pdf`
    a.click()
  }

  const activeBlobUrl = activeDoc === "cv" ? cvUrl : clUrl
  const activeLoading = activeDoc === "cv" ? cvLoading : clLoading

  if (initError) {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
          <AlertCircle className="h-10 w-10 text-red-500" />
          <p className="text-sm text-muted">{initError}</p>
          <button onClick={() => navigate(-1)} className="btn-ghost ring-focus px-4 py-2 rounded-lg text-sm flex items-center gap-2">
            <ArrowLeft className="h-4 w-4" /> Retour
          </button>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      {/* Page header */}
      <div className="h-14 flex items-center gap-3 px-6 shrink-0"
        style={{ borderBottom: "1px solid rgb(var(--line) / var(--line-a))" }}>
        <button onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-muted hover:text-ink transition mr-1">
          <ArrowLeft className="h-4 w-4" />
          Retour
        </button>
        <div className="h-4 w-px bg-line/20" />
        {jobInfo ? (
          <>
            <span className="text-sm font-medium text-ink truncate">{jobInfo.title}</span>
            <span className="text-subtle text-sm">·</span>
            <span className="text-sm text-muted truncate">{jobInfo.company}</span>
            {jobInfo.url && (
              <a href={jobInfo.url} target="_blank" rel="noreferrer"
                className="ml-auto flex items-center gap-1.5 text-xs text-muted hover:text-ink transition shrink-0">
                Voir l'offre <ArrowUpRight className="h-3.5 w-3.5" />
              </a>
            )}
          </>
        ) : (
          <span className="text-sm text-muted animate-pulse">Chargement…</span>
        )}
      </div>

      {/* Split layout */}
      <div className="flex" style={{ height: "calc(100vh - 56px)" }}>

        {/* ── Left panel ─────────────────────────────────────────────────────── */}
        <div className="w-[300px] shrink-0 flex flex-col overflow-y-auto"
          style={{ borderRight: "1px solid rgb(var(--line) / var(--line-a))", background: "rgb(var(--card))" }}>

          {/* Document tabs */}
          <div className="p-4 shrink-0" style={{ borderBottom: "1px solid rgb(var(--line) / var(--line-a))" }}>
            <p className="text-xs font-medium text-subtle uppercase tracking-wide mb-3">Document</p>
            <div className="flex flex-col gap-1">
              {(["cover_letter", "cv"] as Doc[]).map((doc) => {
                const isActive = activeDoc === doc
                const label = doc === "cover_letter" ? "Lettre de motivation" : "CV original"
                const Icon  = FileText
                return (
                  <button key={doc} onClick={() => handleTabChange(doc)}
                    className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-left transition ${
                      isActive ? "bg-accent/10 text-accent font-medium" : "text-muted hover:bg-line/5 hover:text-ink"
                    }`}>
                    <Icon className="h-4 w-4 shrink-0" />
                    {label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Suggestion zone - cover letter only */}
          <div className="flex-1 p-4 flex flex-col gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="h-3.5 w-3.5 text-accent shrink-0" />
                <p className="text-xs font-medium text-ink">Modifier la lettre</p>
              </div>
              <p className="text-xs text-muted mb-3 leading-relaxed">
                Décrivez les ajustements souhaités. Le modèle régénèrera la lettre en tenant compte de vos instructions.
              </p>
              <textarea
                value={suggestion}
                onChange={(e) => setSuggestion(e.target.value)}
                placeholder={"Ex: Mets en avant mon expérience en Python, adopte un ton plus dynamique, cite ma passion pour les données…"}
                rows={6}
                className="input-base ring-focus resize-none leading-relaxed"
                style={{ borderRadius: "0.5rem" }}
              />
              <div className="flex items-center justify-between mt-1">
                <span className="text-[10px] text-subtle">{suggestion.length}/400</span>
              </div>
            </div>

            <button
              onClick={handleRegenerate}
              disabled={!suggestion.trim() || regenerating || clLoading}
              className="btn-accent ring-focus w-full rounded-lg py-2.5 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {regenerating ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Génération…</>
              ) : (
                <><RefreshCw className="h-4 w-4" /> Régénérer</>
              )}
            </button>

            {/* Downloads */}
            <div className="border-t border-line/10 pt-4 space-y-2">
              <p className="text-xs font-medium text-subtle uppercase tracking-wide mb-2">Téléchargements</p>
              <button
                onClick={handleDownloadCl}
                disabled={!clUrl}
                className="btn-ghost ring-focus w-full rounded-lg py-2 text-sm flex items-center justify-center gap-2 disabled:opacity-40"
              >
                <Download className="h-4 w-4" /> Lettre de motivation
              </button>
              {cvUrl && (
                <a href={cvUrl} download={`cv_${jobInfo?.company ?? "offre"}.pdf`}
                  className="btn-ghost ring-focus w-full rounded-lg py-2 text-sm flex items-center justify-center gap-2">
                  <Download className="h-4 w-4" /> Mon CV
                </a>
              )}
            </div>
          </div>
        </div>

        {/* ── Right panel - PDF viewer ────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col items-center justify-center bg-[rgb(var(--bg))] relative">
          {activeLoading || regenerating ? (
            <div className="flex flex-col items-center gap-4 text-muted">
              <Loader2 className="h-8 w-8 animate-spin text-accent" />
              <p className="text-sm">{regenerating ? "Régénération de la lettre…" : "Chargement du document…"}</p>
            </div>
          ) : activeBlobUrl ? (
            <iframe
              key={activeBlobUrl}
              src={activeBlobUrl}
              title={activeDoc === "cv" ? "CV" : "Lettre de motivation"}
              className="w-full h-full border-0"
              style={{ minHeight: 0 }}
            />
          ) : (
            <div className="flex flex-col items-center gap-3 text-muted">
              <FileText className="h-10 w-10 opacity-30" />
              <p className="text-sm">Document non disponible</p>
            </div>
          )}
        </div>

      </div>
    </Layout>
  )
}