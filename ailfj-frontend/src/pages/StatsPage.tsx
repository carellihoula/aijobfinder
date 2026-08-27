import { useMemo } from "react"
import { TrendingUp, Target, Bookmark, Briefcase, Award, AlertCircle } from "lucide-react"
import Layout from "../components/Layout"
import type { JobMatch } from "../types"
import { useLatestAnalysis } from "../lib/queries"
import { getSavedJobs } from "../lib/savedJobs"
import { scoreTier } from "../lib/designTypes"

// ── Helpers ──────────────────────────────────────────────────────────────────

function avg(nums: number[]) {
  if (!nums.length) return 0
  return nums.reduce((a, b) => a + b, 0) / nums.length
}

function topN<T extends string>(arr: T[], n = 8): { value: T; count: number }[] {
  const map = new Map<T, number>()
  for (const v of arr) map.set(v, (map.get(v) ?? 0) + 1)
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([value, count]) => ({ value, count }))
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, sub, color = "text-accent" }: {
  icon: React.ElementType
  label: string
  value: string | number
  sub?: string
  color?: string
}) {
  return (
    <div className="card rounded-xl p-4">
      <div className={`h-8 w-8 rounded-lg bg-line/5 bd flex items-center justify-center mb-3 ${color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <p className="text-2xl font-semibold text-ink tabular-nums">{value}</p>
      <p className="text-xs font-medium text-ink mt-0.5">{label}</p>
      {sub && <p className="text-[11px] text-subtle mt-0.5">{sub}</p>}
    </div>
  )
}

function HBar({ label, count, max, color }: { label: string; count: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0
  return (
    <div className="flex items-center gap-3">
      <span className="text-[12px] text-muted w-32 shrink-0 truncate" title={label}>{label}</span>
      <div className="flex-1 h-1.5 bg-line/8 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-[11px] text-subtle w-4 text-right shrink-0">{count}</span>
    </div>
  )
}

function ScoreHistogram({ matches }: { matches: JobMatch[] }) {
  const ranges = [
    { label: "0–3",   min: 0,   max: 3,   rgb: "244 63 94" },
    { label: "3–5",   min: 3,   max: 5,   rgb: "234 179 8" },
    { label: "5–7",   min: 5,   max: 7,   rgb: "139 92 246" },
    { label: "7–8.5", min: 7,   max: 8.5, rgb: "16 185 129" },
    { label: "8.5+",  min: 8.5, max: 11,  rgb: "52 211 153" },
  ]

  const counts = ranges.map(({ min, max }) =>
    matches.filter((m) => m.score >= min && m.score < max).length
  )
  const peak = Math.max(...counts, 1)

  return (
    <div className="card rounded-xl p-5">
      <h3 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4">Distribution des scores</h3>
      <div className="flex items-end gap-2 h-24">
        {ranges.map(({ label, rgb }, i) => {
          const h = Math.max((counts[i] / peak) * 100, counts[i] > 0 ? 8 : 0)
          return (
            <div key={label} className="flex-1 flex flex-col items-center gap-1.5">
              <span className="text-[10px] text-subtle">{counts[i] || ""}</span>
              <div className="w-full rounded-t-sm transition-all duration-700"
                style={{ height: `${h}%`, background: `rgb(${rgb})`, minHeight: counts[i] > 0 ? 4 : 0 }} />
              <span className="text-[9px] text-subtle whitespace-nowrap">{label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function StatsPage() {
  const { data: analysis, isLoading: loading, isError: error } = useLatestAnalysis()
  const savedCount = useMemo(() => getSavedJobs().length, [])

  const matches = analysis?.matches ?? []
  const scores  = matches.map((m) => m.score)
  const avgScore = avg(scores)

  const matchedSkills = matches.flatMap((m) => m.matching_skills ?? [])
  const missingSkills = matches.flatMap((m) => m.missing_skills ?? [])
  const topMatched    = topN(matchedSkills)
  const topMissing    = topN(missingSkills)

  // contract_type is always a string (never null/undefined), just sometimes empty -
  // "||" (not "??") is required here to actually catch that case.
  const contractCounts = topN(
    matches.map((m) => m.job.contract_type || "Autres")
  )

  if (loading) {
    return (
      <Layout title="Statistiques">
        <div className="flex items-center justify-center py-24">
          <span className="h-5 w-5 border-2 border-line/20 border-t-accent rounded-full animate-spin" />
        </div>
      </Layout>
    )
  }

  if (error || !analysis) {
    return (
      <Layout title="Statistiques">
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <AlertCircle className="h-10 w-10 text-red-500" />
          <p className="text-sm text-muted">Aucune analyse disponible. Lancez d'abord une analyse.</p>
        </div>
      </Layout>
    )
  }

  const tier = scoreTier(avgScore)

  return (
    <Layout title="Statistiques" subtitle="Synthèse de votre dernière analyse">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-8 animate-fade-up">

        {/* KPI cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard icon={Briefcase}   label="Offres trouvées"  value={matches.length} sub="dernière analyse" />
          <StatCard
            icon={TrendingUp}
            label="Score moyen"
            value={avgScore.toFixed(1) + "/10"}
            sub={tier.label}
            color={`text-[rgb(${tier.rgb})]`}
          />
          <StatCard icon={Target}   label="Score max"         value={scores.length ? Math.max(...scores).toFixed(1) : "-"} sub="meilleure offre" color="text-violet-400" />
          <StatCard icon={Bookmark} label="Offres sauvegardées" value={savedCount} sub="sur votre liste" color="text-amber-400" />
        </div>

        {/* Score histogram */}
        {matches.length > 0 && <ScoreHistogram matches={matches} />}

        {/* Skills */}
        <div className="grid sm:grid-cols-2 gap-4">
          {/* Matched skills */}
          <div className="card rounded-xl p-5">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4 flex items-center gap-2">
              <Award className="h-3.5 w-3.5 text-accent" />
              Compétences en commun
            </h3>
            {topMatched.length === 0 ? (
              <p className="text-xs text-subtle">Aucune donnée</p>
            ) : (
              <div className="space-y-2.5">
                {topMatched.map(({ value, count }) => (
                  <HBar key={value} label={value} count={count} max={topMatched[0]?.count ?? 1} color="rgb(16 185 129)" />
                ))}
              </div>
            )}
          </div>

          {/* Missing skills */}
          <div className="card rounded-xl p-5">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4 flex items-center gap-2">
              <AlertCircle className="h-3.5 w-3.5 text-rose-400" />
              À renforcer
            </h3>
            {topMissing.length === 0 ? (
              <p className="text-xs text-subtle">Aucune donnée</p>
            ) : (
              <div className="space-y-2.5">
                {topMissing.map(({ value, count }) => (
                  <HBar key={value} label={value} count={count} max={topMissing[0]?.count ?? 1} color="rgb(244 63 94)" />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Contract type breakdown */}
        {contractCounts.length > 0 && (
          <div className="card rounded-xl p-5">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wide mb-4">
              Répartition par type de contrat
            </h3>
            <div className="space-y-2.5">
              {contractCounts.map(({ value, count }) => (
                <HBar key={value} label={value} count={count} max={contractCounts[0]?.count ?? 1} color="rgb(139 92 246)" />
              ))}
            </div>
          </div>
        )}

        {/* Keywords used */}
        {analysis.keywords && analysis.keywords.length > 0 && (
          <div className="card rounded-xl p-5">
            <h3 className="text-xs font-semibold text-muted uppercase tracking-wide mb-3">
              Mots-clés de recherche utilisés
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {analysis.keywords.map((k) => (
                <span key={k} className="text-xs font-mono px-2.5 py-1 rounded-md bg-line/5 bd text-muted">{k}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}