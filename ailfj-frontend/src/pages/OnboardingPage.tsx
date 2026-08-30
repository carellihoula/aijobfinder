import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { uploadCV, getCvData } from "../api/analysis"
import Dropzone from "../components/Dropzone"
import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react"

// Self-contained - no shared toast system in this codebase yet, and this is
// the only place on this page that needs one.
function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 6000)
    return () => clearTimeout(t)
  }, [onClose])

  return (
    <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 animate-fade-up">
      <div className="flex items-center gap-2.5 rounded-xl px-4 py-3 text-[13px] font-medium bg-rose-500/10 text-rose-500 border border-rose-500/20 shadow-lg">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        {message}
        <button onClick={onClose} className="ml-1 text-rose-500/70 hover:text-rose-500 transition">
          <XCircle className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

const INIT_NODE_LABELS: Record<string, string> = {
  pdf_parser:    "Lecture du CV…",
  cv_structurer: "Analyse du profil…",
}

const INIT_PROGRESS: Record<string, number> = {
  pdf_parser:    40,
  cv_structurer: 80,
}

export default function OnboardingPage() {
  const [file, setFile]       = useState<File | null>(null)
  const [phase, setPhase]     = useState<"upload" | "extracting" | "done">("upload")
  const [progress, setProgress] = useState(0)
  const [step, setStep]       = useState("Préparation…")
  const [checking, setChecking] = useState(true)
  const [error, setError]     = useState<string | null>(null)
  const [toast, setToast]     = useState<string | null>(null)
  const navigate              = useNavigate()
  const sseRef                = useRef<AbortController | null>(null)

  // If user already has a profile, skip onboarding
  useEffect(() => {
    getCvData()
      .then(() => navigate("/dashboard", { replace: true }))
      .catch(() => setChecking(false))
  }, [navigate])

  const listenInitSSE = (cvId: string) => {
    const ctrl  = new AbortController()
    sseRef.current = ctrl

    const run = async () => {
      try {
        const res = await fetch(`/api/analysis/init-stream/${cvId}`, {
          credentials: "include",
          signal: ctrl.signal,
        })
        if (!res.ok || !res.body) return
        const reader  = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ""

        while (true) {
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
                const p = INIT_PROGRESS[event.node]
                if (p !== undefined) setProgress(p)
                setStep(INIT_NODE_LABELS[event.node] ?? event.node)
              }
              if (event.done) {
                if (event.error) {
                  // Stay on this same upload page instead of advancing -
                  // the document was rejected (not a CV, or a technical
                  // failure), the user needs to pick a different file.
                  setToast(event.error)
                  setPhase("upload")
                  return
                }
                setProgress(100)
                setStep("Profil initialisé !")
                setPhase("done")
                setTimeout(() => navigate("/profile?welcome=1", { replace: true }), 1200)
                return
              }
            } catch { /* ignore */ }
          }
        }
      } catch { /* aborted or network error */ }
    }
    run()
  }

  const handleSubmit = async () => {
    if (!file) return
    setError(null)
    setPhase("extracting")
    setProgress(10)
    setStep("Envoi du fichier…")
    try {
      const res = await uploadCV(file)
      const { cv_id, status } = res.data
      if (status === "ready") {
        // Same PDF already extracted
        setProgress(100)
        setPhase("done")
        setTimeout(() => navigate("/profile?welcome=1", { replace: true }), 800)
      } else {
        listenInitSSE(cv_id)
      }
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? "Erreur lors de l'envoi. Réessayez.")
      setPhase("upload")
    }
  }

  useEffect(() => () => { sseRef.current?.abort() }, [])

  if (checking) {
    return (
      <div className="min-h-screen bg-[rgb(var(--bg))] flex items-center justify-center">
        <span className="h-5 w-5 border-2 border-line/20 border-t-accent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[rgb(var(--bg))] flex flex-col">
      {toast && <Toast message={toast} onClose={() => setToast(null)} />}

      {/* Top bar */}
      <header className="h-14 border-b border-line/10 flex items-center px-6">
        <div className="flex items-center gap-2">
          <span className="h-7 w-7 rounded-lg bg-accent flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M8 1L14 4.5V11.5L8 15L2 11.5V4.5L8 1Z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round"/>
              <circle cx="8" cy="8" r="2" fill="#fff"/>
            </svg>
          </span>
          <span className="font-semibold text-sm text-ink tracking-tight">AILFJ</span>
        </div>
      </header>

      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md">

          {phase === "upload" && (
            <div className="animate-fade-up">
              <h1 className="text-xl font-semibold text-ink mb-1">Déposez votre CV</h1>
              <p className="text-sm text-muted mb-2">
                L'IA extrait vos informations et remplit votre profil automatiquement.
              </p>
              <p className="text-xs text-subtle mb-6">
                Vous pourrez ensuite compléter et affiner votre profil, puis lancer une recherche d'offres.
              </p>

              <Dropzone file={file} onFile={setFile} />

              {error && (
                <p className="mt-4 text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <button
                onClick={handleSubmit}
                disabled={!file}
                className="btn-accent ring-focus mt-6 w-full rounded-lg py-2.5 text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Analyser mon CV
              </button>
              <p className="text-center text-xs text-subtle mt-2">Durée : 10–15 secondes</p>
            </div>
          )}

          {phase === "extracting" && (
            <div className="animate-fade-up">
              <h1 className="text-xl font-semibold text-ink mb-1">Extraction en cours…</h1>
              <p className="text-sm text-muted mb-6">Votre profil est en cours de création.</p>

              <div className="card rounded-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-muted">{step}</span>
                  <span className="text-sm font-mono text-accent">{progress}%</span>
                </div>
                <div className="h-1.5 bg-line/10 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent rounded-full transition-all duration-700"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {phase === "done" && (
            <div className="animate-fade-up text-center">
              <CheckCircle2 className="h-12 w-12 text-accent mx-auto mb-4" />
              <h1 className="text-xl font-semibold text-ink mb-1">Profil créé !</h1>
              <p className="text-sm text-muted">Redirection vers votre profil…</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}