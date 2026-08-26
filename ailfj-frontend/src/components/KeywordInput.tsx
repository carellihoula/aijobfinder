import { useState } from "react"
import { Search, Plus, X, Sparkles } from "lucide-react"

interface KeywordInputProps {
  keywords: string[]
  onChange: (next: string[]) => void
  max?: number
}

export default function KeywordInput({ keywords, onChange, max = 10 }: KeywordInputProps) {
  const [value, setValue] = useState("")
  const [justAdded, setJustAdded] = useState<number | null>(null)

  const add = () => {
    const v = value.trim()
    if (!v || keywords.length >= max || keywords.includes(v)) return
    onChange([...keywords, v])
    setJustAdded(keywords.length)
    setValue("")
  }
  const remove = (i: number) => onChange(keywords.filter((_, idx) => idx !== i))

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2.5">
        <label className="text-sm font-medium text-muted">Postes recherchés</label>
        <span className="text-xs font-mono text-subtle">{keywords.length}<span className="text-subtle">/{max}</span></span>
      </div>
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-subtle" />
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add() } }}
          placeholder="Ex. Senior Frontend Engineer…"
          disabled={keywords.length >= max}
          className="ring-focus w-full bg-well border border-line/10 rounded-xl pl-10 pr-12 py-3 text-sm text-ink placeholder-subtle focus:border-line/20 transition disabled:opacity-50"
        />
        <button onClick={add} aria-label="Ajouter"
          className="btn-accent absolute right-2 top-1/2 -translate-y-1/2 grid place-items-center h-8 w-8 rounded-lg text-white transition">
          <Plus className="h-4 w-4" />
        </button>
      </div>
      {keywords.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3">
          {keywords.map((k, i) => (
            <span key={k}
              className={`group inline-flex items-center gap-1.5 text-xs font-medium pl-3 pr-1.5 py-1.5 rounded-lg border ${i === justAdded ? "animate-pop-in" : ""}`}
              style={{ background: "rgb(var(--accent) / 0.12)", borderColor: "rgb(var(--accent) / 0.25)", color: "#ddd6fe" }}>
              {k}
              <button onClick={() => remove(i)} aria-label={`Retirer ${k}`}
                className="grid place-items-center h-5 w-5 rounded-md hover:bg-line/10 text-accent-300/70 hover:text-white transition">
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          ))}
        </div>
      )}
      <p className="mt-3 flex items-center gap-1.5 text-xs text-subtle">
        <Sparkles className="h-3.5 w-3.5 text-accent" />
        Ajoutez-en quelques-uns — <span className="text-muted">l'IA complète le reste</span> à partir de votre CV.
      </p>
    </div>
  )
}
