import { SlidersHorizontal, X } from "lucide-react"
import type { MatchFilters, ContractType, WorkMode } from "../lib/designTypes"

const CONTRACTS: (ContractType | "all")[] = ["all", "CDI", "CDD", "Freelance", "Stage", "Alternance", "Autres"]
const MODES: (WorkMode | "all")[] = ["all", "Remote", "Hybride", "Sur site"]
const SCORES: { val: number; label: string }[] = [
  { val: 0,   label: "Tous" },
  { val: 5,   label: "≥ 5" },
  { val: 7,   label: "≥ 7" },
  { val: 8.5, label: "≥ 8.5" },
]

const pill = "text-[11px] px-2.5 py-1.5 rounded-lg bd text-muted transition whitespace-nowrap"

export default function FilterBar({ filters, onChange }: { filters: MatchFilters; onChange: (next: MatchFilters) => void }) {
  const set = (patch: Partial<MatchFilters>) => onChange({ ...filters, ...patch })
  const isActive = filters.contract !== "all" || filters.mode !== "all" || filters.minScore !== 0

  return (
    <div className="card rounded-2xl p-3 sm:p-3.5">
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
        <div className="flex items-center gap-1.5 shrink-0">
          <SlidersHorizontal className="h-3.5 w-3.5 text-subtle" />
          <span className="text-xs font-medium text-muted">Filtrer</span>
        </div>
        <div className="h-5 w-px bg-line/15 shrink-0" />
        <div className="flex items-center gap-1 shrink-0">
          {CONTRACTS.map((c) => (
            <button key={c} onClick={() => set({ contract: c })}
              className={`${pill} ${filters.contract === c ? "seg-on" : ""}`}>
              {c === "all" ? "Tous contrats" : c}
            </button>
          ))}
        </div>
        <div className="h-5 w-px bg-line/15 shrink-0" />
        <div className="flex items-center gap-1 shrink-0">
          {MODES.map((m) => (
            <button key={m} onClick={() => set({ mode: m })}
              className={`${pill} ${filters.mode === m ? "seg-on" : ""}`}>
              {m === "all" ? "Tous lieux" : m}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2 mt-2.5 pt-2.5 border-t border-line/10">
        <div className="flex items-center gap-1 shrink-0">
          <span className="text-[11px] text-subtle mr-1">Score min</span>
          {SCORES.map((s) => (
            <button key={s.val} onClick={() => set({ minScore: s.val })}
              className={`${pill} ${filters.minScore === s.val ? "seg-on" : ""}`}>
              {s.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2 shrink-0">
          {isActive && (
            <button onClick={() => set({ contract: "all", mode: "all", minScore: 0 })}
              className="text-[11px] text-subtle hover:text-ink transition flex items-center gap-1">
              <X className="h-3 w-3" /> Réinitialiser
            </button>
          )}
          <span className="text-[11px] text-subtle">Trier</span>
          <select value={filters.sort} onChange={(e) => set({ sort: e.target.value as MatchFilters["sort"] })}
            className="ring-focus text-[11px] bg-well bd rounded-lg pl-2.5 pr-6 py-1.5 text-muted cursor-pointer">
            <option value="score">Score</option>
            <option value="recent">Récence</option>
            <option value="salary">Salaire</option>
          </select>
        </div>
      </div>
    </div>
  )
}
