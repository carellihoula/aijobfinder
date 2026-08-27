import { useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { Bookmark, Search, Inbox, X } from "lucide-react"
import Layout from "../components/Layout"
import MatchCard, { MatchDetailModal } from "../components/MatchCard"
import { getSavedJobs, unsaveJob } from "../lib/savedJobs"
import type { SavedJob } from "../lib/savedJobs"

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
      <div className="max-w-400 mx-auto px-4 sm:px-6 py-8">

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
                <button
                  onClick={() => handleUnsave(job.id)}
                  title="Retirer"
                  className="absolute -top-2 -right-2 z-10 h-6 w-6 rounded-full flex items-center justify-center text-subtle bg-canvas bd shadow-md hover:text-red-500 hover:bg-red-500/10 transition"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
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