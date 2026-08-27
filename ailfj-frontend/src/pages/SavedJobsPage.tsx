import { useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { Bookmark, BookmarkX, Search, Inbox } from "lucide-react"
import Layout from "../components/Layout"
import MatchCard, { MatchDetailModal } from "../components/MatchCard"
import { getSavedJobs, unsaveJob } from "../lib/savedJobs"
import type { SavedJob } from "../lib/savedJobs"

function formatSaved(iso: string) {
  try {
    const d = new Date(iso)
    const diff = Math.floor((Date.now() - d.getTime()) / 86400000)
    if (diff === 0) return "Aujourd'hui"
    if (diff === 1) return "Hier"
    return `Il y a ${diff} jours`
  } catch {
    return ""
  }
}

export default function SavedJobsPage() {
  const navigate = useNavigate()
  const [jobs, setJobs] = useState<SavedJob[]>(() => getSavedJobs())
  const [query, setQuery] = useState("")
  const [selected, setSelected] = useState<SavedJob | null>(null)

  const handleUnsave = useCallback((jobId: string) => {
    unsaveJob(jobId)
    setJobs(getSavedJobs())
  }, [])

  const filtered = jobs.filter(
    (j) =>
      !query ||
      j.title.toLowerCase().includes(query.toLowerCase()) ||
      j.company.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <Layout
      title="Offres sauvegardées"
      subtitle={`${jobs.length} offre${jobs.length !== 1 ? "s" : ""} conservée${jobs.length !== 1 ? "s" : ""}`}
    >
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 py-8">

        {jobs.length > 0 && (
          <div className="relative mb-6">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-subtle pointer-events-none" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher dans vos offres sauvegardées…"
              className="input-base ring-focus pl-9"
            />
          </div>
        )}

        {jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
            <div className="h-14 w-14 rounded-2xl bg-line/5 bd flex items-center justify-center">
              <Inbox className="h-7 w-7 text-subtle" />
            </div>
            <div>
              <p className="text-sm font-medium text-ink mb-1">Aucune offre sauvegardée</p>
              <p className="text-xs text-muted max-w-xs">
                Cliquez sur le marque-page d'une offre dans votre tableau de bord pour la retrouver ici.
              </p>
            </div>
            <button
              onClick={() => navigate("/dashboard")}
              className="btn-accent ring-focus mt-2 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm"
            >
              <Bookmark className="h-4 w-4" /> Voir mes matchs
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-center text-sm text-muted py-12">Aucun résultat pour « {query} »</p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {filtered.map((job) => (
              <div key={job.id} className="relative group">
                {/* Saved date badge */}
                <div className="absolute top-4 right-4 z-10 flex items-center gap-1.5">
                  <span className="text-[10px] text-subtle bg-[rgb(var(--bg))] bd rounded-md px-2 py-0.5">
                    Sauvegardé · {formatSaved(job.savedAt)}
                  </span>
                  <button
                    onClick={() => handleUnsave(job.id)}
                    title="Retirer"
                    className="h-6 w-6 rounded-md flex items-center justify-center text-subtle hover:text-red-500 hover:bg-red-500/10 transition opacity-0 group-hover:opacity-100"
                  >
                    <BookmarkX className="h-3.5 w-3.5" />
                  </button>
                </div>
                <MatchCard match={job} onOpen={() => setSelected(job)} />
              </div>
            ))}
          </div>
        )}

        {selected && (
          <MatchDetailModal
            match={selected}
            analysisId={selected.analysisId}
            onClose={() => setSelected(null)}
            onApply={() => navigate(
              `/documents?analysisId=${selected.analysisId}&jobIndex=${selected.originalIndex}` +
              `&company=${encodeURIComponent(selected.company)}&title=${encodeURIComponent(selected.title)}`
            )}
            onSaveToggle={() => { handleUnsave(selected.id); setSelected(null) }}
          />
        )}
      </div>
    </Layout>
  )
}