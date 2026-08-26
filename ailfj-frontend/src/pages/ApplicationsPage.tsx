import { useEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import {
  Briefcase, Plus, Link2, ClipboardPaste, Loader2, X,
  Trash2, ExternalLink, Download, RefreshCw, Sparkles, AlertCircle,
  ArrowRight, ArrowLeft, GraduationCap, FileText, Eye,
} from "lucide-react"
import Layout from "../components/Layout"
import { Select, SelectValue, SelectTrigger, SelectContent, SelectItem } from "../components/ui/select"
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody } from "../components/ui/dialog"
import { QK, useApplications } from "../lib/queries"
import {
  previewJob, createApplication, pollApplication, fetchApplicationCoverLetterPdf, refineCoverLetter,
  updateApplication, deleteApplication,
} from "../api/applications"
import type { Application, ApplicationStatus, JobPreview } from "../api/applications"

// ── Status vocabulary ───────────────────────────────────────────────────────

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  applied: "Postulé",
  in_progress: "En cours",
  rejected: "Refusé",
  accepted: "Accepté",
}

const STATUS_DOTS: Record<ApplicationStatus, string> = {
  applied: "bg-accent",
  in_progress: "bg-amber-500",
  rejected: "bg-red-400",
  accepted: "bg-emerald-500",
}

function AppStatusSelect({ value, onChange, disabled }: { value: ApplicationStatus; onChange: (s: ApplicationStatus) => void; disabled?: boolean }) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as ApplicationStatus)} disabled={disabled}>
      <SelectTrigger className="min-w-[132px]">
        <span className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${STATUS_DOTS[value]}`} />
          <SelectValue />
        </span>
      </SelectTrigger>
      <SelectContent>
        {(Object.keys(STATUS_LABELS) as ApplicationStatus[]).map((s) => (
          <SelectItem key={s} value={s}>{STATUS_LABELS[s]}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

// ── View pasted offer content (no source link available) ───────────────────

function ViewOfferDialog({ application }: { application: Application }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button className="flex items-center gap-1.5 text-xs text-accent hover:underline">
          <Eye className="h-3.5 w-3.5" /> Visualiser le contenu
        </button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{application.title}</DialogTitle>
          <DialogDescription>{application.company}</DialogDescription>
        </DialogHeader>
        <DialogBody>
          <p className="text-[13px] text-muted leading-relaxed whitespace-pre-wrap">
            {application.description || application.summary || "Contenu indisponible."}
          </p>
        </DialogBody>
      </DialogContent>
    </Dialog>
  )
}

function formatDate(iso: string | null) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })
}

// ── Add application panel: input → preview → generating → ready ────────────

type Phase = "input" | "preview" | "generating" | "ready"

function AddApplicationPanel({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [phase, setPhase] = useState<Phase>("input")
  const [mode, setMode] = useState<"url" | "text">("url")
  const [url, setUrl] = useState("")
  const [text, setText] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [job, setJob] = useState<JobPreview | null>(null)
  const [suggestion, setSuggestion] = useState("")
  const [applicationId, setApplicationId] = useState<string | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const liveRef = useRef(true)
  useEffect(() => () => { liveRef.current = false }, [])

  const handlePreview = async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await previewJob(mode === "url" ? { url: url.trim() } : { text: text.trim() })
      setJob(data)
      setPhase("preview")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec de la récupération de l'offre")
    } finally {
      setLoading(false)
    }
  }

  const pollAndShow = async (id: string) => {
    const result = await pollApplication(id)
    if (!liveRef.current) return
    if (result.cover_letter_status !== "completed") {
      setError("La génération a échoué — vous pouvez réessayer.")
      setPhase("preview")
      return
    }
    const { blob } = await fetchApplicationCoverLetterPdf(id)
    if (!liveRef.current) return
    setPdfUrl(URL.createObjectURL(blob))
    setPhase("ready")
  }

  const handleGenerate = async () => {
    if (!job) return
    setError(null)
    setPhase("generating")
    try {
      if (applicationId) {
        // Retry after a failed generation — reuse the existing record.
        await refineCoverLetter(applicationId, suggestion)
        await pollAndShow(applicationId)
      } else {
        const { data } = await createApplication({
          title: job.title, company: job.company, location: job.location,
          description: job.description, url: job.url, suggestion,
        })
        setApplicationId(data.id)
        await pollAndShow(data.id)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec de la génération")
      setPhase("preview")
    }
  }

  const handleRefine = async () => {
    if (!applicationId || !suggestion.trim()) return
    setPhase("generating")
    setError(null)
    try {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl)
      await refineCoverLetter(applicationId, suggestion)
      await pollAndShow(applicationId)
      setSuggestion("")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Échec de la régénération")
      setPhase("ready")
    }
  }

  const handleDownload = () => {
    if (!pdfUrl) return
    const a = document.createElement("a")
    a.href = pdfUrl
    a.download = "lettre_motivation.pdf"
    a.click()
  }

  const handleFinish = () => {
    if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    onCreated()
  }

  const handleClose = applicationId ? handleFinish : onClose

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={handleClose} />
      <div
        className="relative w-full max-w-2xl max-h-[85vh] rounded-2xl overflow-hidden flex flex-col animate-fade-up"
        style={{ background: "rgb(var(--card))", border: "1px solid rgb(var(--line) / var(--line-a))", boxShadow: "var(--shadow)" }}
      >
        <div className="flex items-center justify-between px-5 py-4 shrink-0" style={{ borderBottom: "1px solid rgb(var(--line) / var(--line-a))" }}>
          <h2 className="text-[15px] font-semibold text-ink">Nouvelle candidature</h2>
          <button onClick={handleClose} className="h-7 w-7 rounded-lg flex items-center justify-center text-subtle hover:text-ink hover:bg-line/8 transition">
            <X className="h-4 w-4" />
          </button>
        </div>

        {phase === "input" && (
          <div className="p-5 flex flex-col gap-4 overflow-y-auto">
            <p className="text-[12px] text-muted leading-relaxed">
              Ajoutez une offre que vous avez déjà repérée — via son lien, ou en collant directement le texte de la page.
              Aucun scoring n'est effectué : ça sert uniquement à générer une lettre de motivation adaptée.
            </p>

            <div className="flex gap-1 p-0.5 rounded-lg bg-line/8 w-fit">
              <button onClick={() => setMode("url")} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition ${mode === "url" ? "bg-accent text-white" : "text-muted hover:text-ink"}`}>
                <Link2 className="h-3.5 w-3.5" /> Lien
              </button>
              <button onClick={() => setMode("text")} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition ${mode === "text" ? "bg-accent text-white" : "text-muted hover:text-ink"}`}>
                <ClipboardPaste className="h-3.5 w-3.5" /> Coller le texte
              </button>
            </div>

            {mode === "url" ? (
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://exemple.com/offres/123"
                className="input-base ring-focus"
              />
            ) : (
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Collez ici le texte complet de l'offre…"
                rows={8}
                className="input-base ring-focus resize-none leading-relaxed"
              />
            )}

            {error && (
              <div className="flex items-center gap-2 text-[12px] text-red-500">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {error}
              </div>
            )}

            <button
              onClick={handlePreview}
              disabled={loading || (mode === "url" ? !url.trim() : text.trim().length < 50)}
              className="btn-accent ring-focus rounded-lg py-2.5 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Récupération…</> : <><ArrowRight className="h-4 w-4" /> Voir l'offre</>}
            </button>
          </div>
        )}

        {phase === "preview" && job && (
          <div className="p-5 flex flex-col gap-4 overflow-y-auto">
            <button onClick={() => setPhase("input")} className="flex items-center gap-1.5 text-[12px] text-muted hover:text-ink transition w-fit">
              <ArrowLeft className="h-3.5 w-3.5" /> Modifier la source
            </button>

            <div className="rounded-xl p-4" style={{ border: "1px solid rgb(var(--line) / var(--line-a))" }}>
              <p className="text-[15px] font-semibold text-ink">{job.title}</p>
              <p className="text-[13px] text-muted mb-3">{job.company}{job.location && ` · ${job.location}`}</p>
              <div className="text-[12px] text-muted leading-relaxed max-h-[220px] overflow-y-auto whitespace-pre-wrap">
                {job.description}
              </div>
            </div>

            <div>
              <p className="text-[12px] font-medium text-ink mb-1.5">Instructions pour la lettre (optionnel)</p>
              <textarea
                value={suggestion}
                onChange={(e) => setSuggestion(e.target.value)}
                placeholder="Ex: Mets en avant mon expérience en recherche…"
                rows={3}
                className="input-base ring-focus resize-none text-[12px]"
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-[12px] text-red-500">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {error}
              </div>
            )}

            <button
              onClick={handleGenerate}
              className="btn-accent ring-focus rounded-lg py-2.5 text-sm font-medium flex items-center justify-center gap-2"
            >
              <Sparkles className="h-4 w-4" /> Générer la lettre de motivation
            </button>
          </div>
        )}

        {phase === "generating" && (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 py-20 text-muted text-center px-8">
            <Loader2 className="h-8 w-8 animate-spin text-accent" />
            <p className="text-sm">Génération de la lettre en cours (jusqu'à une minute)…</p>
            <p className="text-xs text-subtle">Vous pouvez fermer cette fenêtre — la candidature est déjà enregistrée, la lettre sera disponible dans le tableau.</p>
          </div>
        )}

        {phase === "ready" && pdfUrl && (
          <div className="flex flex-1 min-h-0">
            <div className="flex-1 bg-[rgb(var(--bg))]">
              <iframe src={pdfUrl} title="Lettre de motivation" className="w-full h-full border-0" style={{ minHeight: 400 }} />
            </div>
            <div className="w-[260px] shrink-0 p-4 flex flex-col gap-3 overflow-y-auto" style={{ borderLeft: "1px solid rgb(var(--line) / var(--line-a))" }}>
              <textarea
                value={suggestion}
                onChange={(e) => setSuggestion(e.target.value)}
                placeholder="Ajustements souhaités…"
                rows={5}
                className="input-base ring-focus resize-none text-[12px]"
              />
              <button
                onClick={handleRefine}
                disabled={!suggestion.trim()}
                className="btn-ghost ring-focus rounded-lg py-2 text-[12px] flex items-center justify-center gap-1.5 disabled:opacity-40"
              >
                <RefreshCw className="h-3.5 w-3.5" /> Régénérer
              </button>
              <button onClick={handleDownload} className="btn-ghost ring-focus rounded-lg py-2 text-[12px] flex items-center justify-center gap-1.5">
                <Download className="h-3.5 w-3.5" /> Télécharger
              </button>
              <button onClick={handleFinish} className="btn-accent ring-focus rounded-lg py-2 text-[12px] font-medium mt-auto">
                Ajouter à mes candidatures
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Cover letter cell (status / link to Documents page) ─────────────────────

function CoverLetterCell({ application }: { application: Application }) {
  if (application.cover_letter_status === "processing" || application.cover_letter_status === "pending") {
    return <span className="flex items-center gap-1.5 text-xs text-muted"><Loader2 className="h-3.5 w-3.5 animate-spin" /> En cours…</span>
  }
  if (application.cover_letter_status === "failed") {
    return <span className="flex items-center gap-1.5 text-xs text-red-400"><AlertCircle className="h-3.5 w-3.5" /> Échec</span>
  }

  const params = new URLSearchParams({
    applicationId: application.id,
    company: application.company,
    title: application.title,
  })

  return (
    <Link to={`/documents?${params}`} className="flex items-center gap-1.5 text-xs text-accent hover:underline">
      <FileText className="h-3.5 w-3.5" /> Voir la lettre
    </Link>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ApplicationsPage() {
  const { data: applications = [], isLoading, refetch } = useApplications()
  const queryClient = useQueryClient()
  const [showAdd, setShowAdd] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: QK.applications })

  // Poll the list while at least one cover letter is still generating.
  const hasProcessing = applications.some((a) => a.cover_letter_status === "processing" || a.cover_letter_status === "pending")
  useEffect(() => {
    if (!hasProcessing) return
    const id = setInterval(() => refetch(), 3000)
    return () => clearInterval(id)
  }, [hasProcessing, refetch])

  const handleStatusChange = async (id: string, status: ApplicationStatus) => {
    setBusyId(id)
    try {
      await updateApplication(id, { status })
      invalidate()
    } finally {
      setBusyId(null)
    }
  }

  const handleDelete = async (id: string) => {
    setBusyId(id)
    try {
      await deleteApplication(id)
      invalidate()
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Layout
      title="Mes candidatures"
      subtitle="Suivi des offres auxquelles vous avez postulé"
      actions={
        <button onClick={() => setShowAdd(true)} className="btn-accent ring-focus rounded-lg px-3 py-1.5 text-[12px] font-medium flex items-center gap-1.5">
          <Plus className="h-3.5 w-3.5" /> Nouvelle candidature
        </button>
      }
    >
      <div className="p-6">
        {isLoading ? (
          <div className="flex items-center gap-2 py-16 justify-center">
            <Loader2 className="h-4 w-4 animate-spin text-accent" />
            <span className="text-xs text-muted">Chargement…</span>
          </div>
        ) : applications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
            <Briefcase className="h-10 w-10 text-subtle opacity-40" />
            <p className="text-sm text-muted">Aucune candidature pour l'instant.</p>
            <button onClick={() => setShowAdd(true)} className="btn-accent ring-focus rounded-lg px-4 py-2 text-sm font-medium flex items-center gap-2 mt-2">
              <Plus className="h-4 w-4" /> Ajouter une candidature
            </button>
          </div>
        ) : (
          <div className="rounded-xl overflow-hidden" style={{ border: "1px solid rgb(var(--line) / var(--line-a))", background: "rgb(var(--card))" }}>
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-left" style={{ borderBottom: "1px solid rgb(var(--line) / var(--line-a))" }}>
                  <th className="py-2.5 px-4 font-semibold text-muted text-xs">Poste</th>
                  <th className="py-2.5 px-4 font-semibold text-muted text-xs">Entreprise</th>
                  <th className="py-2.5 px-4 font-semibold text-muted text-xs">Source</th>
                  <th className="py-2.5 px-4 font-semibold text-muted text-xs">Lettre</th>
                  <th className="py-2.5 px-4 font-semibold text-muted text-xs">Statut</th>
                  <th className="py-2.5 px-4 font-semibold text-muted text-xs">Entretien</th>
                  <th className="py-2.5 px-4 font-semibold text-muted text-xs">Ajoutée le</th>
                  <th className="py-2.5 px-4 font-semibold text-muted text-xs text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/6">
                {applications.map((app) => (
                  <tr key={app.id} className="hover:bg-line/4 transition">
                    <td className="py-3 px-4 text-ink font-medium">{app.title}</td>
                    <td className="py-3 px-4 text-muted">{app.company}</td>
                    <td className="py-3 px-4">
                      {app.url ? (
                        <a href={app.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-accent hover:underline text-xs">
                          Voir l'offre <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : (
                        <ViewOfferDialog application={app} />
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <CoverLetterCell application={app} />
                    </td>
                    <td className="py-3 px-4">
                      <AppStatusSelect value={app.status} disabled={busyId === app.id} onChange={(s) => handleStatusChange(app.id, s)} />
                    </td>
                    <td className="py-3 px-4">
                      <button
                        disabled
                        title="Bientôt disponible"
                        className="btn-ghost rounded-lg px-2.5 py-1.5 text-[11px] flex items-center gap-1.5 opacity-50 cursor-not-allowed"
                      >
                        <GraduationCap className="h-3.5 w-3.5" /> Préparer
                      </button>
                    </td>
                    <td className="py-3 px-4 text-muted text-xs">{formatDate(app.created_at)}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end">
                        <button
                          onClick={() => handleDelete(app.id)}
                          disabled={busyId === app.id}
                          className="h-7 w-7 rounded-lg flex items-center justify-center text-muted hover:bg-red-500/10 hover:text-red-400 transition disabled:opacity-40"
                          title="Supprimer"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showAdd && (
        <AddApplicationPanel
          onClose={() => setShowAdd(false)}
          onCreated={() => { setShowAdd(false); invalidate() }}
        />
      )}
    </Layout>
  )
}
