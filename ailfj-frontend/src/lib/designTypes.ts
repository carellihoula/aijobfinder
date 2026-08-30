export type AnalysisStatus = "idle" | "processing" | "completed" | "failed"
export type ContractType = "CDI" | "CDD" | "Freelance" | "Stage" | "Alternance" | "Autres"
export type WorkMode = "Remote" | "Hybride" | "Sur site"

export interface DesignJobMatch {
  id: string
  originalIndex: number
  title: string
  company: string
  logo: string
  location: string
  mode: WorkMode
  contract: ContractType | string
  seniority: string
  salary?: string
  score: number
  posted?: string
  postedDays?: number
  reason: string
  description: string
  missions: string[]
  matchedSkills: string[]
  missingSkills: string[]
  url?: string
}

export interface MatchFilters {
  contract: ContractType | "all"
  mode: WorkMode | "all"
  minScore: number
  sort: "score" | "recent" | "salary"
  search: string
}

export const DEFAULT_FILTERS: MatchFilters = {
  contract: "all",
  mode: "all",
  minScore: 0,
  sort: "score",
  search: "",
}

export function applyFilters(list: DesignJobMatch[], f: MatchFilters): DesignJobMatch[] {
  const query = f.search.trim().toLowerCase()
  const out = list.filter(
    (m) =>
      (f.contract === "all" || m.contract === f.contract) &&
      (f.mode === "all" || m.mode === f.mode) &&
      m.score >= f.minScore &&
      (query === "" || m.title.toLowerCase().includes(query) || m.company.toLowerCase().includes(query))
  )
  if (f.sort === "score")  out.sort((a, b) => b.score - a.score)
  if (f.sort === "recent") out.sort((a, b) => (a.postedDays ?? 0) - (b.postedDays ?? 0))
  if (f.sort === "salary") out.sort((a, b) => (b.salaryMin ?? 0) - (a.salaryMin ?? 0))
  return out
}

export function scoreTier(score: number): { rgb: string; label: string } {
  if (score >= 8.5) return { rgb: "16 185 129",  label: "Excellent" }
  if (score >= 7)   return { rgb: "139 92 246",   label: "Fort" }
  if (score >= 5)   return { rgb: "234 179 8",    label: "Moyen" }
  return              { rgb: "244 63 94",    label: "Faible" }
}

// Needed for salary sort – added as an extension on DesignJobMatch
declare module "./designTypes" {
  interface DesignJobMatch {
    salaryMin?: number
  }
}
