import { useState, useCallback } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { QK, useAdminUsers, useAdminAnalyses } from "../lib/queries"
import {
  RefreshCw, Play, Trash2, Users, BarChart2,
  CheckCircle, AlertCircle, Loader2, ChevronDown, ChevronUp, Shield,
} from "lucide-react"
import Layout from "../components/Layout"
import {
  rerunAnalysis,
  triggerIngestion, triggerRefresh, triggerCleanup,
} from "../api/admin"
import type { AnalysisSummary, TaskResult } from "../api/admin"

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "completed" ? "bg-emerald-500/10 text-emerald-500" :
    status === "processing" || status === "pending" ? "bg-accent/10 text-accent" :
    status === "failed" ? "bg-red-500/10 text-red-400" :
    "bg-line/10 text-muted"
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${cls}`}>
      {status}
    </span>
  )
}

// ── Toast-style feedback ──────────────────────────────────────────────────────

interface Feedback { kind: "ok" | "err"; text: string }

function FeedbackBanner({ fb }: { fb: Feedback }) {
  const Icon = fb.kind === "ok" ? CheckCircle : AlertCircle
  return (
    <div className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm mb-4 ${
      fb.kind === "ok" ? "bg-emerald-500/10 text-emerald-600" : "bg-red-500/10 text-red-500"
    }`}>
      <Icon className="h-4 w-4 shrink-0" />
      {fb.text}
    </div>
  )
}

// ── Action button ─────────────────────────────────────────────────────────────

function ActionBtn({
  label, icon: Icon, onClick, loading, variant = "ghost",
}: {
  label: string
  icon: React.ElementType
  onClick: () => void
  loading?: boolean
  variant?: "ghost" | "accent" | "danger"
}) {
  const cls =
    variant === "accent" ? "btn-accent" :
    variant === "danger" ? "bg-red-500/10 text-red-500 hover:bg-red-500/20 rounded-lg px-3 h-8 text-xs font-medium transition" :
    "btn-ghost"
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`${cls} ring-focus flex items-center gap-1.5 rounded-lg px-3 h-8 text-xs disabled:opacity-50`}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
      {label}
    </button>
  )
}

// ── Section card ──────────────────────────────────────────────────────────────

function SectionCard({ title, icon: Icon, children, defaultOpen = true }: {
  title: string
  icon: React.ElementType
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="card rounded-xl overflow-hidden mb-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 px-5 py-3.5 text-left hover:bg-line/4 transition"
        style={{ borderBottom: open ? "1px solid rgb(var(--line) / var(--line-a))" : "none" }}
      >
        <Icon className="h-4 w-4 text-accent" />
        <h3 className="text-sm font-semibold text-ink flex-1">{title}</h3>
        {open ? <ChevronUp className="h-4 w-4 text-subtle" /> : <ChevronDown className="h-4 w-4 text-subtle" />}
      </button>
      {open && <div className="px-5 py-4">{children}</div>}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const [feedback, setFeedback]       = useState<Feedback | null>(null)
  const queryClient = useQueryClient()
  const { data: users = [], isLoading: loadingUsers } = useAdminUsers()
  const { data: analyses = [], isLoading: loadingAnalyses } = useAdminAnalyses()
  const [busyTask, setBusyTask]       = useState<string | null>(null)  // which button is loading
  const [rerunningId, setRerunningId] = useState<string | null>(null)

  const notify = useCallback((result: TaskResult | null, err?: unknown) => {
    if (err) {
      setFeedback({ kind: "err", text: String(err) })
    } else if (result) {
      setFeedback({ kind: "ok", text: result.detail })
    }
    setTimeout(() => setFeedback(null), 5000)
  }, [])


  // ── Cron actions ─────────────────────────────────────────────────────────

  async function handleIngest() {
    setBusyTask("ingest")
    try { notify((await triggerIngestion()).data) }
    catch (e) { notify(null, e) }
    finally { setBusyTask(null) }
  }

  async function handleRefresh() {
    setBusyTask("refresh")
    try { notify((await triggerRefresh()).data) }
    catch (e) { notify(null, e) }
    finally { setBusyTask(null) }
  }

  async function handleCleanup() {
    setBusyTask("cleanup")
    try { notify((await triggerCleanup(30)).data) }
    catch (e) { notify(null, e) }
    finally { setBusyTask(null) }
  }

  // ── Rerun pipeline ────────────────────────────────────────────────────────

  async function handleRerun(id: string) {
    setRerunningId(id)
    try {
      const res = await rerunAnalysis(id)
      notify(res.data)
      queryClient.setQueryData(QK.adminAnalyses, (prev: AnalysisSummary[] | undefined) =>
        prev?.map((a) => (a.id === id ? { ...a, status: "pending" } : a)) ?? []
      )
    } catch (e) { notify(null, e) }
    finally { setRerunningId(null) }
  }

  const userMap = Object.fromEntries(users.map((u) => [u.id, u.email]))

  return (
    <Layout
      title="Administration"
      subtitle="Contrôles réservés aux administrateurs"
      actions={
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-accent/10 bd">
          <Shield className="h-3.5 w-3.5 text-accent" />
          <span className="text-[11px] font-semibold text-accent">Admin</span>
        </div>
      }
    >
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">

        {feedback && <FeedbackBanner fb={feedback} />}

        {/* ── Cron / pipeline controls ── */}
        <SectionCard title="Contrôles pipeline & Cortex" icon={Play}>
          <p className="text-xs text-muted mb-4">
            Déclenche manuellement les tâches planifiées sans attendre les crons nocturnes.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">

            <div className="card rounded-xl p-4 flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-accent/10 flex items-center justify-center">
                  <RefreshCw className="h-4 w-4 text-accent" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink">Ingestion Cortex</p>
                  <p className="text-[10px] text-muted">Rafraîchit les offres d'emploi</p>
                </div>
              </div>
              <p className="text-[10px] text-subtle leading-relaxed">
                Normalement lancé chaque nuit à 2h. Récupère les nouvelles offres depuis Adzuna
                et les stocke dans le Cortex (pgvector).
              </p>
              <ActionBtn
                label="Lancer l'ingestion"
                icon={Play}
                variant="accent"
                loading={busyTask === "ingest"}
                onClick={handleIngest}
              />
            </div>

            <div className="card rounded-xl p-4 flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <BarChart2 className="h-4 w-4 text-purple-400" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink">Refresh analyses</p>
                  <p className="text-[10px] text-muted">Re-matche les CVs existants</p>
                </div>
              </div>
              <p className="text-[10px] text-subtle leading-relaxed">
                Normalement à 3h (après ingestion). Compare les analyses existantes avec le
                Cortex mis à jour, rafraîchit si de nouveaux jobs correspondent.
              </p>
              <ActionBtn
                label="Lancer le refresh"
                icon={RefreshCw}
                loading={busyTask === "refresh"}
                onClick={handleRefresh}
              />
            </div>

            <div className="card rounded-xl p-4 flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-red-500/10 flex items-center justify-center">
                  <Trash2 className="h-4 w-4 text-red-400" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-ink">Nettoyage Cortex</p>
                  <p className="text-[10px] text-muted">Purge les vieux jobs (+30j)</p>
                </div>
              </div>
              <p className="text-[10px] text-subtle leading-relaxed">
                Normalement le dimanche à 3h. Désactive les offres non vues depuis 30 jours
                et purge celles inactives depuis 90 jours.
              </p>
              <ActionBtn
                label="Nettoyer"
                icon={Trash2}
                variant="danger"
                loading={busyTask === "cleanup"}
                onClick={handleCleanup}
              />
            </div>
          </div>
        </SectionCard>

        {/* ── Analyses list ── */}
        <SectionCard title={`Analyses (${analyses.length})`} icon={BarChart2} defaultOpen={true}>
          {loadingAnalyses ? (
            <div className="flex items-center gap-2 py-6 justify-center">
              <Loader2 className="h-4 w-4 animate-spin text-accent" />
              <span className="text-xs text-muted">Chargement…</span>
            </div>
          ) : analyses.length === 0 ? (
            <p className="text-xs text-muted text-center py-6">Aucune analyse.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left border-b border-line/10">
                    <th className="pb-2 font-semibold text-muted pr-4">Utilisateur</th>
                    <th className="pb-2 font-semibold text-muted pr-4">ID analyse</th>
                    <th className="pb-2 font-semibold text-muted pr-4">Statut</th>
                    <th className="pb-2 font-semibold text-muted pr-4">Mots-clés</th>
                    <th className="pb-2 font-semibold text-muted text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/6">
                  {analyses.map((a) => (
                    <tr key={a.id} className="hover:bg-line/4 transition">
                      <td className="py-2.5 pr-4 text-ink font-medium truncate max-w-[160px]">
                        {userMap[a.user_id] ?? a.user_id.slice(0, 8) + "…"}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-subtle">
                        {a.id.slice(0, 8)}…
                      </td>
                      <td className="py-2.5 pr-4">
                        <StatusBadge status={a.status} />
                        {a.error && (
                          <p className="text-[10px] text-red-400 mt-0.5 max-w-[200px] truncate" title={a.error}>
                            {a.error}
                          </p>
                        )}
                      </td>
                      <td className="py-2.5 pr-4 text-muted max-w-[180px] truncate">
                        {a.keywords?.slice(0, 3).join(", ") ?? "—"}
                      </td>
                      <td className="py-2.5 text-right">
                        <ActionBtn
                          label={rerunningId === a.id ? "En cours…" : "Re-lancer"}
                          icon={Play}
                          loading={rerunningId === a.id}
                          onClick={() => handleRerun(a.id)}
                          variant="ghost"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

        {/* ── Users list ── */}
        <SectionCard title={`Utilisateurs (${users.length})`} icon={Users} defaultOpen={false}>
          {loadingUsers ? (
            <div className="flex items-center gap-2 py-6 justify-center">
              <Loader2 className="h-4 w-4 animate-spin text-accent" />
              <span className="text-xs text-muted">Chargement…</span>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left border-b border-line/10">
                    <th className="pb-2 font-semibold text-muted pr-4">Email</th>
                    <th className="pb-2 font-semibold text-muted pr-4">Nom</th>
                    <th className="pb-2 font-semibold text-muted pr-4">Statut</th>
                    <th className="pb-2 font-semibold text-muted">Admin</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/6">
                  {users.map((u) => (
                    <tr key={u.id} className="hover:bg-line/4 transition">
                      <td className="py-2.5 pr-4 text-ink font-medium">{u.email}</td>
                      <td className="py-2.5 pr-4 text-muted">{u.full_name ?? "—"}</td>
                      <td className="py-2.5 pr-4">
                        <span className={`inline-flex rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                          u.is_active ? "bg-emerald-500/10 text-emerald-500" : "bg-line/10 text-muted"
                        }`}>
                          {u.is_active ? "actif" : "inactif"}
                        </span>
                      </td>
                      <td className="py-2.5">
                        {u.is_admin && (
                          <span className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-semibold bg-accent/10 text-accent">
                            <Shield className="h-2.5 w-2.5" /> admin
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>

      </div>
    </Layout>
  )
}
