import { useEffect, useRef, useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import {
  User, Mail, Shield, Calendar, ExternalLink, LogOut,
  Globe, Link, GitBranch, Upload, Briefcase, GraduationCap,
  Code2, SlidersHorizontal, Check, MapPin, Clock, Loader2,
  Star, Plus, Trash2, Pencil, X, Save, ChevronLeft, ChevronRight,
  Search, Camera, AlertTriangle,
} from "lucide-react"
import Layout from "../components/Layout"
import { clearAvatarCache, blobCache } from "../components/UserAvatar"
import { useUser } from "../lib/userContext"
import { useAuth } from "../hooks/useAuth"
import { updateCvData, launchSearch, uploadCV } from "../api/analysis"
import { updatePreferences } from "../api/users"
import { useQueryClient } from "@tanstack/react-query"
import { QK, useCvData, usePreferences } from "../lib/queries"
import { uploadAvatar, deleteAvatar } from "../api/auth"
import type { CvData, CvExperience, CvEducation, CvLanguage } from "../api/analysis"
import type { UserPreferences } from "../api/users"

type Tab = "overview" | "preferences" | "stack" | "experience" | "education"

const TABS: { key: Tab; label: string; icon: React.ElementType }[] = [
  { key: "overview",    label: "Vue d'ensemble",  icon: User },
  { key: "preferences", label: "Préférences",      icon: SlidersHorizontal },
  { key: "stack",       label: "Stack technique",  icon: Code2 },
  { key: "experience",  label: "Expérience",       icon: Briefcase },
  { key: "education",   label: "Formation",        icon: GraduationCap },
]

const LEVEL_LABELS: Record<string, string> = {
  junior:    "Junior (0–3 ans)",
  mid:       "Intermédiaire (3–7 ans)",
  senior:    "Senior (7+ ans)",
  lead:      "Lead / Tech Lead",
  principal: "Principal / Architect",
}

const CONTRACT_OPTIONS: { value: string; label: string }[] = [
  { value: "cdi",          label: "CDI" },
  { value: "cdd",          label: "CDD" },
  { value: "stage",        label: "Stage" },
  { value: "alternance",   label: "Alternance" },
  { value: "freelance",    label: "Freelance" },
  { value: "temps_partiel", label: "Temps partiel" },
]

const WORK_MODE_OPTIONS: { value: string; label: string }[] = [
  { value: "on_site", label: "Sur site" },
  { value: "hybrid",  label: "Hybride" },
  { value: "remote",  label: "Télétravail" },
]

const LANG_LEVEL_OPTIONS: { value: string; label: string }[] = [
  { value: "A1",     label: "Débutant (A1)" },
  { value: "A2",     label: "Élémentaire (A2)" },
  { value: "B1",     label: "Intermédiaire (B1)" },
  { value: "B2",     label: "Avancé (B2)" },
  { value: "C1",     label: "Courant (C1)" },
  { value: "C2",     label: "Maîtrise (C2)" },
  { value: "native", label: "Langue maternelle" },
]

function sessionExpiry(): string {
  return "Session active"
}

// ─── Primitives ───────────────────────────────────────────────────────────────
function SettingRow({ label, desc, children }: { label: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-3 sm:gap-8 py-5 border-b border-line/10 last:border-0">
      <div className="sm:w-52 shrink-0">
        <p className="text-[13px] font-medium text-ink">{label}</p>
        {desc && <p className="text-[12px] text-muted mt-0.5 leading-relaxed">{desc}</p>}
      </div>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  )
}

function ReadonlyField({ value, mono = false }: { value: string; mono?: boolean }) {
  return (
    <div className="w-full rounded-lg px-3 py-2 text-sm border border-line/20" style={{ background: "rgb(var(--line) / 0.03)" }}>
      <span className={mono ? "font-mono text-xs text-muted" : "text-ink"}>{value}</span>
    </div>
  )
}

function FieldInput({ value, onChange, placeholder, multiline = false }: {
  value: string; onChange: (v: string) => void; placeholder?: string; multiline?: boolean
}) {
  const cls = "w-full rounded-lg px-3 py-2 text-[13px] text-ink border border-accent/40 bg-accent/5 outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition"
  return multiline
    ? <textarea rows={3} className={`${cls} resize-none`} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    : <input className={cls} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
}

function Chip({ label, accent = false, onRemove }: { label: string; accent?: boolean; onRemove?: () => void }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[12px] font-medium px-2.5 py-1 rounded-md border ${
      accent ? "bg-accent/10 text-accent border-accent/20" : "bg-line/5 text-muted border-line/15"
    }`}>
      {label}
      {onRemove && (
        <button onClick={onRemove} className="ml-0.5 opacity-60 hover:opacity-100 transition">
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  )
}

function ToggleChip({ label, selected, onToggle }: { label: string; selected: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={`inline-flex items-center gap-1.5 text-[12px] font-medium px-3 py-1.5 rounded-lg border transition ${
        selected
          ? "bg-accent/10 text-accent border-accent/30"
          : "bg-transparent text-muted border-line/20 hover:border-line/40 hover:text-ink"
      }`}>
      {selected && <Check className="h-3 w-3 shrink-0" />}
      {label}
    </button>
  )
}

function SectionHeader({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="pt-5 pb-1">
      <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
      <p className="text-[13px] text-muted mt-0.5">{desc}</p>
    </div>
  )
}

function NoDataState({ icon: Icon, label }: { icon: React.ElementType; label: string }) {
  return (
    <div className="py-14 flex flex-col items-center gap-3 text-center">
      <div className="h-10 w-10 rounded-xl bg-line/5 bd flex items-center justify-center">
        <Icon className="h-5 w-5 text-subtle" />
      </div>
      <p className="text-[13px] text-muted">{label}</p>
      <p className="text-[11px] text-subtle">Uploadez un CV pour extraire automatiquement vos données.</p>
    </div>
  )
}

function SaveBar({ saving, onSave, onCancel }: { saving: boolean; onSave: () => void; onCancel: () => void }) {
  return (
    <div className="flex items-center gap-2 mt-4">
      <button onClick={onSave} disabled={saving}
        className="btn-accent inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium disabled:opacity-60">
        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
        Sauvegarder
      </button>
      <button onClick={onCancel} className="btn-ghost inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] text-muted">
        <X className="h-3.5 w-3.5" /> Annuler
      </button>
    </div>
  )
}

// ─── City autocomplete (api-adresse.data.gouv.fr) ────────────────────────────
const FRANCE_KEYWORDS = ["fr", "fra", "fran", "franc", "france", "tout", "part", "natio"]

function CityAutocomplete({ selected, onAdd, onRemove, onClearAll }: {
  selected: string[]
  onAdd: (city: string) => void
  onRemove: (city: string) => void
  onClearAll: () => void
}) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<string[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const wrapperRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const showFranceOption = selected.length === 0 ||
    FRANCE_KEYWORDS.some((kw) => query.toLowerCase().startsWith(kw))

  const search = (q: string) => {
    clearTimeout(timerRef.current)
    if (q.length < 2) {
      setResults([])
      // Still open to show France option if relevant
      setOpen(showFranceOption || selected.length === 0)
      return
    }
    timerRef.current = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await fetch(
          `https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(q)}&type=municipality&limit=8&autocomplete=1`
        )
        const data = await res.json()
        const cities: string[] = Array.from(
          new Set(
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (data.features as any[]).map((f) => f.properties.city as string)
          )
        ).filter((c) => !selected.includes(c))
        setResults(cities)
        setOpen(true)
      } catch {
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
  }

  const handleFocus = () => {
    if (results.length > 0 || selected.length === 0) setOpen(true)
  }

  const selectFrance = () => {
    onClearAll()
    setQuery("")
    setResults([])
    setOpen(false)
  }

  const isFranceActive = selected.length === 0

  return (
    <div className="space-y-2">
      {/* Selected cities chips */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 items-center">
          {selected.map((c) => (
            <span key={c} className="inline-flex items-center gap-1 text-[12px] font-medium px-2.5 py-1 rounded-md bg-accent/10 text-accent border border-accent/20">
              <MapPin className="h-3 w-3 shrink-0" /> {c}
              <button onClick={() => onRemove(c)} className="ml-0.5 opacity-60 hover:opacity-100 transition"><X className="h-3 w-3" /></button>
            </span>
          ))}
          <button onClick={selectFrance}
            className="text-[11px] text-subtle hover:text-muted transition underline underline-offset-2">
            Réinitialiser (France entière)
          </button>
        </div>
      )}

      {/* France entière passive chip when nothing selected */}
      {isFranceActive && (
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-[12px] font-medium px-2.5 py-1 rounded-md bg-line/5 text-muted border border-line/15">
            🇫🇷 France entière
          </span>
          <span className="text-[11px] text-subtle">- recherchez une ville pour restreindre</span>
        </div>
      )}

      {/* Input + dropdown */}
      <div className="relative max-w-xs" ref={wrapperRef}>
        <MapPin className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-subtle" />
        {loading && <Loader2 className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-subtle animate-spin" />}
        <input
          className="w-full rounded-lg pl-9 pr-8 py-2 text-[13px] border border-line/20 bg-transparent text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition"
          placeholder="Rechercher une ville…"
          value={query}
          onChange={(e) => { setQuery(e.target.value); search(e.target.value) }}
          onFocus={handleFocus}
          onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        />
        {open && (
          <div className="absolute z-20 top-full left-0 right-0 mt-1 card rounded-lg py-1 shadow-lg border border-line/20 overflow-hidden">
            {/* France entière option - always first when query matches or list is empty */}
            {(results.length === 0 || FRANCE_KEYWORDS.some((kw) => query.toLowerCase().startsWith(kw))) && (
              <button
                className="w-full text-left px-3 py-2 text-[13px] text-muted hover:bg-accent/5 transition border-b border-line/10 last:border-0"
                onMouseDown={(e) => e.preventDefault()}
                onClick={selectFrance}>
                🇫🇷 <span className="font-medium text-ink">France entière</span>
                <span className="ml-1.5 text-[11px] text-subtle">- aucun filtre géographique</span>
              </button>
            )}
            {results.map((city) => (
              <button key={city}
                className="w-full text-left px-3 py-2 text-[13px] text-ink hover:bg-accent/5 transition"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => { onAdd(city); setQuery(""); setResults([]); setOpen(false) }}>
                <MapPin className="inline h-3 w-3 mr-1.5 text-subtle" />{city}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Month/Year picker input ──────────────────────────────────────────────────
const MONTHS_FR = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]

function MonthYearInput({ value, onChange, placeholder }: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const [pickerYear, setPickerYear] = useState(() => {
    const y = parseInt((value ?? "").split("/")[1] ?? "")
    return isNaN(y) ? new Date().getFullYear() : y
  })
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setPickerOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const prev = value ?? ""
    let v = e.target.value.replace(/[^0-9/]/g, "")
    // Auto-insert "/" after 2-digit month (only when user is adding, not deleting)
    if (v.length === 2 && !v.includes("/") && prev.length < 2) v = v + "/"
    if (v.length > 7) v = v.slice(0, 7)
    onChange(v)
  }

  const selectMonth = (idx: number) => {
    const mm = String(idx + 1).padStart(2, "0")
    onChange(`${mm}/${pickerYear}`)
    setPickerOpen(false)
  }

  const parsedMonth = parseInt((value ?? "").split("/")[0]) - 1
  const parsedYear  = parseInt((value ?? "").split("/")[1])

  return (
    <div className="relative" ref={wrapRef}>
      <div className="flex gap-1.5">
        <input
          type="text"
          inputMode="numeric"
          value={value ?? ""}
          onChange={handleTextChange}
          placeholder={placeholder ?? "MM/YYYY"}
          maxLength={7}
          className="flex-1 rounded-lg px-3 py-2 text-[13px] text-ink border border-accent/40 bg-accent/5 outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition"
        />
        <button
          type="button"
          onClick={() => {
            const y = parseInt((value ?? "").split("/")[1] ?? "")
            if (!isNaN(y)) setPickerYear(y)
            setPickerOpen((o) => !o)
          }}
          className="btn-ghost rounded-lg px-2.5 text-subtle hover:text-ink transition">
          <Calendar className="h-3.5 w-3.5" />
        </button>
      </div>

      {pickerOpen && (
        <div className="absolute z-30 top-full left-0 mt-1 card rounded-xl border border-line/20 shadow-lg p-3 w-52">
          {/* Year navigation */}
          <div className="flex items-center justify-between mb-3">
            <button
              type="button"
              onClick={() => setPickerYear((y) => y - 1)}
              className="btn-ghost rounded-lg p-1 text-subtle hover:text-ink">
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span className="text-[13px] font-semibold text-ink select-none">{pickerYear}</span>
            <button
              type="button"
              onClick={() => setPickerYear((y) => y + 1)}
              className="btn-ghost rounded-lg p-1 text-subtle hover:text-ink">
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
          {/* Month grid */}
          <div className="grid grid-cols-3 gap-1">
            {MONTHS_FR.map((m, i) => {
              const selected = i === parsedMonth && pickerYear === parsedYear
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => selectMonth(i)}
                  className={`text-[12px] rounded-lg py-1.5 transition ${
                    selected
                      ? "bg-accent text-white font-semibold"
                      : "text-muted hover:bg-accent/10 hover:text-ink"
                  }`}>
                  {m}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Language editor ──────────────────────────────────────────────────────────
function LanguageEditor({ languages, onChange }: {
  languages: CvLanguage[]
  onChange: (langs: CvLanguage[]) => void
}) {
  const [newName, setNewName] = useState("")
  const [newLevel, setNewLevel] = useState("")

  const add = () => {
    const n = newName.trim()
    if (!n || languages.some((l) => l.name.toLowerCase() === n.toLowerCase())) return
    onChange([...languages, { name: n, level: newLevel || undefined }])
    setNewName("")
    setNewLevel("")
  }

  const remove = (name: string) => onChange(languages.filter((l) => l.name !== name))

  const updateLevel = (name: string, level: string) =>
    onChange(languages.map((l) => l.name === name ? { ...l, level: level || undefined } : l))

  return (
    <div className="space-y-2">
      {languages.map((lang) => (
        <div key={lang.name} className="flex items-center gap-2">
          <span className="text-[13px] text-ink font-medium w-28 shrink-0 truncate">{lang.name}</span>
          <select
            className="flex-1 max-w-44 rounded-lg px-2 py-1.5 text-[12px] border border-line/20 bg-transparent text-muted outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition"
            value={lang.level ?? ""}
            onChange={(e) => updateLevel(lang.name, e.target.value)}>
            <option value="">Niveau…</option>
            {LANG_LEVEL_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <button onClick={() => remove(lang.name)}
            className="h-7 w-7 rounded-md flex items-center justify-center text-subtle hover:text-rose-500 hover:bg-rose-500/10 transition shrink-0">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <div className="flex items-center gap-2 pt-1 flex-wrap">
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="ex. Anglais"
          className="w-32 rounded-lg px-3 py-1.5 text-[13px] border border-line/20 bg-transparent text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition"
        />
        <select
          value={newLevel}
          onChange={(e) => setNewLevel(e.target.value)}
          className="max-w-44 rounded-lg px-2 py-1.5 text-[12px] border border-line/20 bg-transparent text-muted outline-none focus:border-accent">
          <option value="">Niveau…</option>
          {LANG_LEVEL_OPTIONS.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <button onClick={add} className="btn-ghost inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px]">
          <Plus className="h-3.5 w-3.5" /> Ajouter
        </button>
      </div>
    </div>
  )
}

// ─── Authenticated avatar image ───────────────────────────────────────────────
// <img> doesn't send the Authorization header - fetch manually and use a blob URL.
function AuthAvatar({ avatarKey, avatarUrl, className }: {
  avatarKey: string | null | undefined
  avatarUrl?: string | null
  className?: string
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(
    avatarKey ? (blobCache.get(avatarKey) ?? null) : null
  )

  useEffect(() => {
    if (!avatarKey) { setBlobUrl(null); return }
    if (blobCache.has(avatarKey)) { setBlobUrl(blobCache.get(avatarKey)!); return }

    let active = true
    fetch(`/api/users/me/avatar`, { credentials: "include" })
      .then((res) => (res.ok ? res.blob() : Promise.reject()))
      .then((blob) => {
        if (!active) return
        const url = URL.createObjectURL(blob)
        blobCache.set(avatarKey, url)
        setBlobUrl(url)
      })
      .catch(() => { if (active) setBlobUrl(null) })

    return () => { active = false }
  }, [avatarKey])

  if (blobUrl) return <img src={blobUrl} alt="Avatar" className={className} />
  // No self-hosted upload - fall back to the Google-provided picture, if any.
  if (!avatarKey && avatarUrl) {
    return <img src={avatarUrl} alt="Avatar" referrerPolicy="no-referrer" className={className} />
  }
  return null
}

// ─── CV re-upload modal ───────────────────────────────────────────────────────
type CvUploadPhase = "confirm" | "uploading" | "extracting" | "error"

function CvUpdateModal({ onConfirm, onCancel, phase }: {
  onConfirm: () => void
  onCancel: () => void
  phase: CvUploadPhase
}) {
  const busy = phase === "uploading" || phase === "extracting"

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgb(0 0 0 / 0.5)" }}>
      <div className="card rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-4">
        <div className="flex items-start gap-3">
          <div className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 ${phase === "error" ? "bg-rose-500/10" : "bg-amber-500/10"}`}>
            <AlertTriangle className={`h-5 w-5 ${phase === "error" ? "text-rose-500" : "text-amber-500"}`} />
          </div>
          <div>
            <p className="text-[15px] font-semibold text-ink">Mettre à jour votre CV</p>
            <p className="text-[13px] text-muted mt-0.5">Cette action va ré-extraire vos données depuis le nouveau fichier.</p>
          </div>
        </div>

        {phase === "extracting" && (
          <div className="rounded-xl border border-line/15 p-4 flex items-center gap-3">
            <Loader2 className="h-5 w-5 text-accent animate-spin shrink-0" />
            <div>
              <p className="text-[13px] font-medium text-ink">Extraction en cours…</p>
              <p className="text-[12px] text-muted">Lecture du PDF et mise à jour du profil. Cela peut prendre 1 à 2 minutes.</p>
            </div>
          </div>
        )}

        {phase === "error" && (
          <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4 text-[12.5px] text-rose-600 dark:text-rose-400">
            L'extraction a échoué ou a pris trop de temps. Vérifiez que le worker Celery est actif, puis réessayez.
          </div>
        )}

        {(phase === "confirm" || phase === "uploading") && (
          <div className="rounded-xl border border-line/15 divide-y divide-line/10 text-[12.5px]">
            <div className="px-4 py-3">
              <p className="font-medium text-ink mb-1">Sera conservé</p>
              <p className="text-muted">Postes ciblés, compétences et centres d'intérêt ajoutés manuellement.</p>
            </div>
            <div className="px-4 py-3">
              <p className="font-medium text-ink mb-1">Sera mis à jour</p>
              <p className="text-muted">Expériences professionnelles, formations, résumé et coordonnées.</p>
            </div>
          </div>
        )}

        <div className="flex gap-2 pt-1">
          {phase !== "error" && (
            <button
              onClick={onConfirm}
              disabled={busy}
              className="btn-accent flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2.5 text-[13px] font-medium disabled:opacity-60"
            >
              {phase === "uploading" ? (
                <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Envoi…</>
              ) : phase === "extracting" ? (
                <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Extraction…</>
              ) : (
                <><Upload className="h-3.5 w-3.5" /> Confirmer la mise à jour</>
              )}
            </button>
          )}
          <button
            onClick={onCancel}
            disabled={busy}
            className={`btn-ghost rounded-lg px-4 py-2.5 text-[13px] text-muted ${phase === "error" ? "w-full" : ""}`}
          >
            {phase === "error" ? "Fermer" : "Annuler"}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Overview tab ─────────────────────────────────────────────────────────────
function OverviewPane({
  me, isAdmin, hasAvatar, avatarUploading, onAvatarChange, onAvatarDelete, onCvUpdate,
}: {
  me: ReturnType<typeof useUser>["me"]
  isAdmin: boolean
  hasAvatar: boolean
  avatarUploading: boolean
  onAvatarChange: (e: React.ChangeEvent<HTMLInputElement>) => void
  onAvatarDelete: () => void
  onCvUpdate: (file: File) => void
}) {
  const displayName = me?.full_name || me?.email || "-"
  const email = me?.email ?? "-"
  const userId = me?.id ?? "-"
  const initials = displayName !== "-" ? displayName.slice(0, 2).toUpperCase() : "?"
  const fileInputRef = useRef<HTMLInputElement>(null)

  return (
    <div>
      <SectionHeader title="Vue d'ensemble" desc="Informations de votre compte." />

      <SettingRow label="Photo de profil" desc="Cliquez sur la photo pour la modifier.">
        <div className="flex items-center gap-4">
          {/* Clickable avatar */}
          <div className="relative group shrink-0">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="hidden"
              onChange={onAvatarChange}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="relative h-16 w-16 rounded-2xl overflow-hidden focus:outline-none focus:ring-2 focus:ring-accent/40"
              title="Changer la photo"
            >
              {hasAvatar ? (
                <AuthAvatar avatarKey={me?.avatar_key} avatarUrl={me?.avatar_url} className="h-full w-full object-cover" />
              ) : (
                <div className="h-full w-full bg-accent/15 flex items-center justify-center text-accent text-xl font-bold select-none">
                  {initials}
                </div>
              )}
              <div className="pointer-events-none absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                {avatarUploading
                  ? <Loader2 className="h-5 w-5 text-white animate-spin" />
                  : <Camera className="h-5 w-5 text-white" />}
              </div>
            </button>
          </div>

          {/* Upload / delete actions */}
          <div className="flex flex-col gap-2">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={avatarUploading}
              className="btn-ghost inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] disabled:opacity-50"
            >
              {avatarUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
              {avatarUploading ? "Envoi…" : "Téléverser une photo"}
            </button>
            {/* Only a self-hosted upload can actually be deleted server-side - a
                Google-provided picture with no upload has nothing to remove. */}
            {!!me?.avatar_key && (
              <button
                onClick={onAvatarDelete}
                disabled={avatarUploading}
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] text-rose-500 hover:bg-rose-500/10 transition disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" /> Supprimer la photo
              </button>
            )}
            <p className="text-[11px] text-subtle">JPEG, PNG, WebP · Max 5 Mo</p>
          </div>
        </div>
      </SettingRow>

      <SettingRow label="Nom complet" desc="Affiché sur votre profil.">
        <ReadonlyField value={me?.full_name ?? "Non renseigné"} />
      </SettingRow>

      <SettingRow label="Adresse e-mail" desc="Utilisée pour la connexion.">
        <div className="flex items-center gap-2">
          <ReadonlyField value={email} />
          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-md bg-accent/10 text-accent whitespace-nowrap shrink-0">
            <Check className="h-3 w-3" /> Vérifié
          </span>
        </div>
      </SettingRow>

      <SettingRow label="Identifiant" desc="Référence unique de votre compte.">
        <ReadonlyField value={userId} mono />
      </SettingRow>

      <SettingRow label="Session" desc="Expiration du jeton actuel.">
        <div className="flex items-center gap-2">
          <Calendar className="h-3.5 w-3.5 text-subtle shrink-0" />
          <span className="text-[13px] text-muted">{sessionExpiry()}</span>
        </div>
      </SettingRow>

      <SettingRow label="Rôle">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-md bg-accent/10 text-accent">
            <Shield className="h-3 w-3" /> Compte actif
          </span>
          {isAdmin && (
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <Shield className="h-3 w-3" /> Administrateur
            </span>
          )}
        </div>
      </SettingRow>

      <SettingRow label="CV" desc="Mettez à jour votre profil à partir d'un nouveau CV.">
        <div>
          <input
            type="file"
            accept=".pdf"
            className="hidden"
            id="cv-reupload-input"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) { onCvUpdate(f); e.target.value = "" } }}
          />
          <label
            htmlFor="cv-reupload-input"
            className="btn-ghost inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] cursor-pointer"
          >
            <Upload className="h-3.5 w-3.5" /> Mettre à jour mon CV
          </label>
          <p className="text-[11px] text-subtle mt-1">PDF uniquement · Max {10} Mo</p>
        </div>
      </SettingRow>

      <SettingRow label="Liens sociaux" desc="Vos profils publics (à venir).">
        <div className="space-y-2.5 opacity-50 cursor-not-allowed select-none">
          {[
            { icon: Globe, placeholder: "https://votre-site.fr" },
            { icon: GitBranch, placeholder: "https://github.com/username" },
            { icon: Link, placeholder: "https://linkedin.com/in/username" },
          ].map(({ icon: Icon, placeholder }) => (
            <div key={placeholder} className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-subtle"><Icon className="h-3.5 w-3.5" /></span>
              <div className="w-full rounded-lg pl-9 pr-3 py-2 text-[13px] border border-line/20" style={{ background: "rgb(var(--line) / 0.03)" }}>
                <span className="text-subtle">{placeholder}</span>
              </div>
            </div>
          ))}
        </div>
      </SettingRow>
    </div>
  )
}

// ─── Plan card ────────────────────────────────────────────────────────────────
function PlanPane() {
  const features = [
    { label: "1 analyse par 24 h", ok: true },
    { label: "Cortex partagé - offres indexées chaque nuit", ok: true },
    { label: "Lettre de motivation IA (avec affinage)", ok: true },
    { label: "Accès à tous les filtres de recherche", ok: true },
    { label: "Analyses illimitées", ok: false },
    { label: "Alertes personnalisées temps réel", ok: false },
    { label: "Export PDF multi-offres", ok: false },
  ]
  return (
    <div className="card rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-line/10">
        <div>
          <p className="text-[13px] font-semibold text-ink">Plan actuel</p>
          <p className="text-[12px] text-muted mt-0.5">Gratuit - sans engagement</p>
        </div>
        <span className="text-[11px] font-semibold px-3 py-1 rounded-full bg-line/5 bd text-muted tracking-wide uppercase">Free</span>
      </div>
      <div className="px-5 py-4 space-y-2.5">
        {features.map(({ label, ok }) => (
          <div key={label} className="flex items-center gap-2.5 text-[12.5px]">
            <span className={`h-4 w-4 rounded-full flex items-center justify-center shrink-0 text-[9px] font-bold ${ok ? "bg-accent/15 text-accent" : "bg-line/5 text-subtle"}`}>
              {ok ? "✓" : "-"}
            </span>
            <span className={ok ? "text-ink" : "text-subtle"}>{label}</span>
          </div>
        ))}
      </div>
      <div className="px-5 py-3.5 border-t border-line/10" style={{ background: "rgb(var(--line) / 0.02)" }}>
        <p className="text-[11px] text-subtle text-center">Les plans avancés seront disponibles prochainement.</p>
      </div>
    </div>
  )
}

// ─── Preferences tab ──────────────────────────────────────────────────────────
const MAX_ROLES = 10

function PreferencesPane({ cv, prefs, onUpdateCv, onUpdatePrefs }: {
  cv: CvData | null
  prefs: UserPreferences
  onUpdateCv: (updated: CvData) => void
  onUpdatePrefs: (updated: UserPreferences) => void
}) {
  // - Postes ciblés (saved in cv.roles) -
  const [roles, setRoles] = useState<string[]>(cv?.roles ?? [])
  const [newRole, setNewRole] = useState("")
  const [rolesDirty, setRolesDirty] = useState(false)
  const [savingRoles, setSavingRoles] = useState(false)
  const roleInputRef = useRef<HTMLInputElement>(null)

  // - Contrats (multi-select, saved in prefs) -
  const [contractTypes, setContractTypes] = useState<string[]>(prefs.contract_types ?? [])
  const [contractDirty, setContractDirty] = useState(false)
  const [savingContract, setSavingContract] = useState(false)

  // - Modes de travail (multi-select, saved in prefs) -
  const [workModes, setWorkModes] = useState<string[]>(prefs.work_modes ?? [])
  const [workModeDirty, setWorkModeDirty] = useState(false)
  const [savingWorkMode, setSavingWorkMode] = useState(false)

  // - Localisations (city autocomplete, saved in prefs) -
  const [locations, setLocations] = useState<string[]>(prefs.locations ?? [])
  const [locationDirty, setLocationDirty] = useState(false)
  const [savingLocation, setSavingLocation] = useState(false)

  // - Langues (editable list, saved in prefs) -
  const [languages, setLanguages] = useState<CvLanguage[]>(
    prefs.languages?.length ? prefs.languages : (cv?.languages ?? [])
  )
  const [langDirty, setLangDirty] = useState(false)
  const [savingLang, setSavingLang] = useState(false)

  // - Genre -
  const [gender, setGender] = useState<"male" | "female" | "">(prefs.gender ?? "")
  const [genderDirty, setGenderDirty] = useState(false)
  const [savingGender, setSavingGender] = useState(false)

  useEffect(() => { setRoles(cv?.roles ?? []) }, [cv])
  useEffect(() => {
    setContractTypes(prefs.contract_types ?? [])
    setWorkModes(prefs.work_modes ?? [])
    setLocations(prefs.locations ?? [])
    setLanguages(prefs.languages?.length ? prefs.languages : (cv?.languages ?? []))
    setGender(prefs.gender ?? "")
  }, [prefs, cv])

  // Roles helpers
  const addRole = () => {
    const r = newRole.trim()
    if (!r || roles.includes(r) || roles.length >= MAX_ROLES) return
    setRoles((prev) => [...prev, r]); setNewRole(""); setRolesDirty(true)
    roleInputRef.current?.focus()
  }
  const removeRole = (r: string) => { setRoles((prev) => prev.filter((x) => x !== r)); setRolesDirty(true) }
  const saveRoles = async () => {
    setSavingRoles(true)
    try { const res = await updateCvData({ roles }); onUpdateCv(res.data); setRolesDirty(false) }
    finally { setSavingRoles(false) }
  }

  // Contract helpers
  const toggleContract = (v: string) => {
    setContractTypes((prev) => prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v])
    setContractDirty(true)
  }
  const saveContract = async () => {
    setSavingContract(true)
    try { const res = await updatePreferences({ contract_types: contractTypes }); onUpdatePrefs(res.data); setContractDirty(false) }
    finally { setSavingContract(false) }
  }

  // Work mode helpers
  const toggleWorkMode = (v: string) => {
    setWorkModes((prev) => prev.includes(v) ? prev.filter((x) => x !== v) : [...prev, v])
    setWorkModeDirty(true)
  }
  const saveWorkMode = async () => {
    setSavingWorkMode(true)
    try { const res = await updatePreferences({ work_modes: workModes }); onUpdatePrefs(res.data); setWorkModeDirty(false) }
    finally { setSavingWorkMode(false) }
  }

  // Location helpers
  const addLocation = (city: string) => { setLocations((prev) => [...prev, city]); setLocationDirty(true) }
  const removeLocation = (city: string) => { setLocations((prev) => prev.filter((c) => c !== city)); setLocationDirty(true) }
  const saveLocations = async () => {
    setSavingLocation(true)
    try { const res = await updatePreferences({ locations }); onUpdatePrefs(res.data); setLocationDirty(false) }
    finally { setSavingLocation(false) }
  }

  // Language helpers
  const saveLangs = async () => {
    setSavingLang(true)
    try { const res = await updatePreferences({ languages }); onUpdatePrefs(res.data); setLangDirty(false) }
    finally { setSavingLang(false) }
  }

  // Gender helpers
  const saveGender = async () => {
    setSavingGender(true)
    try { const res = await updatePreferences({ gender }); onUpdatePrefs(res.data); setGenderDirty(false) }
    finally { setSavingGender(false) }
  }

  if (!cv && !prefs) return <NoDataState icon={SlidersHorizontal} label="Aucune analyse trouvée" />

  return (
    <div>
      <SectionHeader title="Préférences" desc="Vos critères de recherche d'emploi. Ces données sont utilisées pour affiner vos résultats." />

      {/* Postes ciblés */}
      <SettingRow label="Postes ciblés" desc={`Rôles que vous ciblez. Max ${MAX_ROLES}.`}>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {roles.map((r) => <Chip key={r} label={r} accent onRemove={() => removeRole(r)} />)}
            {roles.length === 0 && <p className="text-[13px] text-subtle italic">Aucun poste - ajoutez-en ci-dessous.</p>}
          </div>
          {roles.length < MAX_ROLES && (
            <div className="flex gap-2 max-w-sm">
              <input
                ref={roleInputRef}
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addRole()}
                placeholder="ex. Data Engineer…"
                className="flex-1 rounded-lg px-3 py-2 text-[13px] border border-line/20 bg-transparent text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition"
              />
              <button onClick={addRole} className="btn-ghost rounded-lg px-3 py-2 inline-flex items-center gap-1.5 text-[13px]">
                <Plus className="h-3.5 w-3.5" /> Ajouter
              </button>
            </div>
          )}
          {roles.length >= MAX_ROLES && <p className="text-[11px] text-subtle">Maximum {MAX_ROLES} postes atteint.</p>}
          {rolesDirty && <SaveBar saving={savingRoles} onSave={saveRoles} onCancel={() => { setRoles(cv?.roles ?? []); setRolesDirty(false) }} />}
        </div>
      </SettingRow>

      {/* Niveau (readonly) */}
      {cv?.level && (
        <SettingRow label="Niveau" desc="Séniorité détectée par l'IA.">
          <div className="flex items-center gap-2">
            <Star className="h-3.5 w-3.5 text-accent shrink-0" />
            <span className="text-[13px] text-ink">{LEVEL_LABELS[cv.level] ?? cv.level}</span>
            {(cv.experience_years ?? 0) > 0 && (
              <span className="text-[12px] text-muted">· {cv.experience_years} an{cv.experience_years > 1 ? "s" : ""}</span>
            )}
          </div>
        </SettingRow>
      )}

      {/* Type de contrat */}
      <SettingRow label="Type de contrat" desc="Sélectionnez un ou plusieurs types.">
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {CONTRACT_OPTIONS.map(({ value, label }) => (
              <ToggleChip key={value} label={label} selected={contractTypes.includes(value)} onToggle={() => toggleContract(value)} />
            ))}
          </div>
          {contractTypes.length === 0 && <p className="text-[11px] text-subtle">Aucun type sélectionné - tous les contrats seront considérés.</p>}
          {contractDirty && <SaveBar saving={savingContract} onSave={saveContract} onCancel={() => { setContractTypes(prefs.contract_types ?? []); setContractDirty(false) }} />}
        </div>
      </SettingRow>

      {/* Mode de travail */}
      <SettingRow label="Mode de travail" desc="Sélectionnez vos préférences.">
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {WORK_MODE_OPTIONS.map(({ value, label }) => (
              <ToggleChip key={value} label={label} selected={workModes.includes(value)} onToggle={() => toggleWorkMode(value)} />
            ))}
          </div>
          {workModes.length === 0 && <p className="text-[11px] text-subtle">Aucun mode sélectionné - tous les modes seront considérés.</p>}
          {workModeDirty && <SaveBar saving={savingWorkMode} onSave={saveWorkMode} onCancel={() => { setWorkModes(prefs.work_modes ?? []); setWorkModeDirty(false) }} />}
        </div>
      </SettingRow>

      {/* Localisations */}
      <SettingRow label="Localisations" desc="Villes où vous souhaitez travailler (max 5).">
        <div className="space-y-3">
          <CityAutocomplete
            selected={locations}
            onAdd={(city) => { if (locations.length < 5) addLocation(city) }}
            onRemove={removeLocation}
            onClearAll={() => { setLocations([]); setLocationDirty(true) }}
          />
          {locations.length >= 5 && <p className="text-[11px] text-subtle">Maximum 5 villes atteint.</p>}
          {locationDirty && <SaveBar saving={savingLocation} onSave={saveLocations} onCancel={() => { setLocations(prefs.locations ?? []); setLocationDirty(false) }} />}
        </div>
      </SettingRow>

      {/* Genre */}
      <SettingRow label="Genre" desc="Utilisé pour accorder correctement vos lettres de motivation.">
        <div className="space-y-3">
          <div className="flex gap-2">
            {([["male", "Homme"], ["female", "Femme"], ["", "Non précisé"]] as const).map(([value, label]) => (
              <ToggleChip
                key={label}
                label={label}
                selected={gender === value}
                onToggle={() => { setGender(value); setGenderDirty(true) }}
              />
            ))}
          </div>
          {genderDirty && <SaveBar saving={savingGender} onSave={saveGender} onCancel={() => { setGender(prefs.gender ?? ""); setGenderDirty(false) }} />}
        </div>
      </SettingRow>

      {/* Langues */}
      <SettingRow label="Langues" desc="Langues parlées et niveaux.">
        <div className="space-y-3">
          <LanguageEditor languages={languages} onChange={(langs) => { setLanguages(langs); setLangDirty(true) }} />
          {langDirty && <SaveBar saving={savingLang} onSave={saveLangs} onCancel={() => { setLanguages(prefs.languages?.length ? prefs.languages : (cv?.languages ?? [])); setLangDirty(false) }} />}
        </div>
      </SettingRow>
    </div>
  )
}

// ─── Stack tab ────────────────────────────────────────────────────────────────
function StackPane({ cv, onUpdate }: { cv: CvData | null; onUpdate: (updated: CvData) => void }) {
  const [skills, setSkills] = useState<string[]>(cv?.skills ?? [])
  const [newSkill, setNewSkill] = useState("")
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setSkills(cv?.skills ?? []) }, [cv])

  const addSkill = () => {
    const s = newSkill.trim()
    if (!s || skills.includes(s)) return
    setSkills((prev) => [...prev, s]); setNewSkill(""); setDirty(true)
    inputRef.current?.focus()
  }

  const removeSkill = (s: string) => { setSkills((prev) => prev.filter((x) => x !== s)); setDirty(true) }

  const save = async () => {
    setSaving(true)
    try { const res = await updateCvData({ skills }); onUpdate(res.data); setDirty(false) }
    finally { setSaving(false) }
  }

  if (!cv) return <NoDataState icon={Code2} label="Aucun CV analysé" />

  return (
    <div>
      <SectionHeader title="Stack technique" desc="Les compétences extraites de votre CV. Modifiez-les librement." />
      <div className="py-5">
        <div className="flex flex-wrap gap-2 mb-4">
          {skills.map((s) => <Chip key={s} label={s} onRemove={() => removeSkill(s)} />)}
          {skills.length === 0 && <p className="text-[13px] text-subtle italic">Aucune compétence - ajoutez-en ci-dessous.</p>}
        </div>

        <div className="flex gap-2 max-w-sm">
          <input
            ref={inputRef}
            value={newSkill}
            onChange={(e) => setNewSkill(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addSkill()}
            placeholder="Ajouter une compétence…"
            className="flex-1 rounded-lg px-3 py-2 text-[13px] border border-line/20 bg-transparent text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition"
          />
          <button onClick={addSkill} className="btn-ghost rounded-lg px-3 py-2 inline-flex items-center gap-1.5 text-[13px]">
            <Plus className="h-3.5 w-3.5" /> Ajouter
          </button>
        </div>

        {cv.hobbies && cv.hobbies.length > 0 && (
          <div className="mt-6 pt-5 border-t border-line/10">
            <p className="text-[11px] font-medium uppercase tracking-wide text-subtle mb-3">Centres d'intérêt</p>
            <div className="flex flex-wrap gap-2">
              {cv.hobbies.map((h) => (
                <span key={h.name} className="text-[12px] px-2.5 py-1 rounded-md bg-line/5 text-muted border border-line/15">{h.name}</span>
              ))}
            </div>
          </div>
        )}

        {dirty && <SaveBar saving={saving} onSave={save} onCancel={() => { setSkills(cv?.skills ?? []); setDirty(false) }} />}
      </div>
    </div>
  )
}

// ─── Experience tab ───────────────────────────────────────────────────────────
const EMPTY_EXP: CvExperience = { title: "", company: "", start_date: "", end_date: "", description: "" }

function ExpCard({
  exp, index, onSave, onDelete,
}: { exp: CvExperience; index: number; onSave: (i: number, e: CvExperience) => Promise<void>; onDelete: (i: number) => Promise<void> }) {
  const [editing, setEditing] = useState(exp.title === "" && exp.company === "")
  const [draft, setDraft] = useState<CvExperience>({ ...exp })
  const [saving, setSaving] = useState(false)
  const [isCurrent, setIsCurrent] = useState(!exp.end_date || exp.end_date === "présent")

  const field = (k: keyof CvExperience) => (v: string) => setDraft((d) => ({ ...d, [k]: v }))

  const save = async () => {
    setSaving(true)
    const toSave = { ...draft, end_date: isCurrent ? "" : draft.end_date }
    try { await onSave(index, toSave); setEditing(false) }
    finally { setSaving(false) }
  }

  const cancel = () => { setDraft({ ...exp }); setIsCurrent(!exp.end_date || exp.end_date === "présent"); setEditing(false) }

  if (editing) {
    return (
      <div className="card rounded-xl p-4 space-y-3">
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-medium text-subtle uppercase tracking-wide mb-1 block">Poste</label>
            <FieldInput value={draft.title ?? ""} onChange={field("title")} placeholder="ex. Développeur Full Stack" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-subtle uppercase tracking-wide mb-1 block">Entreprise</label>
            <FieldInput value={draft.company ?? ""} onChange={field("company")} placeholder="ex. Acme Corp" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-subtle uppercase tracking-wide mb-1 block">Début</label>
            <MonthYearInput value={draft.start_date ?? ""} onChange={field("start_date")} />
          </div>
          <div>
            <label className="text-[11px] font-medium text-subtle uppercase tracking-wide mb-1 block">Fin</label>
            {isCurrent ? (
              <div className="rounded-lg px-3 py-2 text-[13px] border border-line/20 text-muted bg-transparent select-none">
                En poste actuellement
              </div>
            ) : (
              <MonthYearInput value={draft.end_date ?? ""} onChange={field("end_date")} />
            )}
          </div>
        </div>
        {/* En poste actuellement toggle */}
        <label className="inline-flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={isCurrent}
            onChange={(e) => {
              setIsCurrent(e.target.checked)
              if (e.target.checked) setDraft((d) => ({ ...d, end_date: "" }))
            }}
            className="rounded accent-[rgb(var(--accent))] h-3.5 w-3.5"
          />
          <span className="text-[12px] text-muted">En poste actuellement</span>
        </label>
        <div>
          <label className="text-[11px] font-medium text-subtle uppercase tracking-wide mb-1 block">Description</label>
          <FieldInput value={draft.description ?? ""} onChange={field("description")} placeholder="Décrivez vos missions…" multiline />
        </div>
        <SaveBar saving={saving} onSave={save} onCancel={cancel} />
      </div>
    )
  }

  return (
    <div className="card rounded-xl p-4 group">
      <div className="flex items-start gap-3">
        <div className="h-9 w-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0 mt-0.5">
          <Briefcase className="h-4 w-4 text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-ink">{exp.title || "Poste non précisé"}</p>
              {exp.company && <p className="text-[13px] text-accent font-medium mt-0.5">{exp.company}</p>}
              {(exp.start_date || exp.end_date) && (
                <p className="inline-flex items-center gap-1.5 text-[12px] text-subtle mt-1">
                  <Clock className="h-3 w-3" />
                  {[exp.start_date, exp.end_date || "présent"].filter(Boolean).join(" - ")}
                </p>
              )}
              {exp.description && <p className="text-[13px] text-muted mt-2 leading-relaxed">{exp.description}</p>}
            </div>
            <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition">
              <button onClick={() => setEditing(true)}
                className="btn-ghost inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12px] text-muted">
                <Pencil className="h-3 w-3" /> Modifier
              </button>
              <button onClick={() => onDelete(index)}
                className="h-7 w-7 rounded-lg flex items-center justify-center text-subtle hover:text-rose-500 hover:bg-rose-500/10 transition">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ExperiencePane({ cv, onUpdate }: { cv: CvData | null; onUpdate: (updated: CvData) => void }) {
  const [experiences, setExperiences] = useState<CvExperience[]>(cv?.experiences ?? [])

  useEffect(() => { setExperiences(cv?.experiences ?? []) }, [cv])

  const persist = async (next: CvExperience[]) => {
    const res = await updateCvData({ experiences: next })
    setExperiences(res.data.experiences ?? [])
    onUpdate(res.data)
  }

  const handleSave = async (i: number, updated: CvExperience) => {
    const next = [...experiences]; next[i] = updated; await persist(next)
  }

  const handleDelete = async (i: number) => { await persist(experiences.filter((_, idx) => idx !== i)) }
  const handleAdd = () => { setExperiences((prev) => [EMPTY_EXP, ...prev]) }

  if (!cv) return <NoDataState icon={Briefcase} label="Aucun CV analysé" />

  return (
    <div>
      <div className="flex items-center justify-between pt-5 pb-1">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">Expérience professionnelle</h2>
          <p className="text-[13px] text-muted mt-0.5">Extraite de votre CV. Modifiez ou ajoutez des entrées.</p>
        </div>
        <button onClick={handleAdd} className="btn-ghost inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px]">
          <Plus className="h-3.5 w-3.5" /> Ajouter
        </button>
      </div>
      {experiences.length === 0 ? (
        <NoDataState icon={Briefcase} label="Aucune expérience" />
      ) : (
        <div className="py-4 space-y-3">
          {experiences.map((exp, i) => (
            <ExpCard key={i} exp={exp} index={i} onSave={handleSave} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Education tab ────────────────────────────────────────────────────────────
const EMPTY_EDU: CvEducation = { degree: "", school: "", start_date: "", end_date: "" }

function EduCard({
  edu, index, onSave, onDelete,
}: { edu: CvEducation; index: number; onSave: (i: number, e: CvEducation) => Promise<void>; onDelete: (i: number) => Promise<void> }) {
  const [editing, setEditing] = useState(edu.degree === "" && edu.school === "")
  const [draft, setDraft] = useState<CvEducation>({ ...edu })
  const [saving, setSaving] = useState(false)

  const field = (k: keyof CvEducation) => (v: string) => setDraft((d) => ({ ...d, [k]: v }))

  const save = async () => {
    setSaving(true)
    try { await onSave(index, draft); setEditing(false) }
    finally { setSaving(false) }
  }

  const cancel = () => { setDraft({ ...edu }); setEditing(false) }

  if (editing) {
    return (
      <div className="card rounded-xl p-4 space-y-3">
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="text-[11px] font-medium text-subtle uppercase tracking-wide mb-1 block">Diplôme</label>
            <FieldInput value={draft.degree ?? ""} onChange={field("degree")} placeholder="ex. Master Informatique" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-subtle uppercase tracking-wide mb-1 block">École / Université</label>
            <FieldInput value={draft.school ?? ""} onChange={field("school")} placeholder="ex. Université Paris-Saclay" />
          </div>
          <div>
            <label className="text-[11px] font-medium text-subtle uppercase tracking-wide mb-1 block">Début</label>
            <MonthYearInput value={draft.start_date ?? ""} onChange={field("start_date")} />
          </div>
          <div>
            <label className="text-[11px] font-medium text-subtle uppercase tracking-wide mb-1 block">Fin</label>
            <MonthYearInput value={draft.end_date ?? ""} onChange={field("end_date")} placeholder="MM/YYYY ou vide" />
          </div>
        </div>
        <SaveBar saving={saving} onSave={save} onCancel={cancel} />
      </div>
    )
  }

  return (
    <div className="card rounded-xl p-4 group">
      <div className="flex items-start gap-3">
        <div className="h-9 w-9 rounded-lg bg-line/5 bd flex items-center justify-center shrink-0 mt-0.5">
          <GraduationCap className="h-4 w-4 text-subtle" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-ink">{edu.degree || "Diplôme non précisé"}</p>
              {edu.school && <p className="text-[13px] text-muted font-medium mt-0.5">{edu.school}</p>}
              {(edu.start_date || edu.end_date) && (
                <p className="inline-flex items-center gap-1.5 text-[12px] text-subtle mt-1">
                  <Clock className="h-3 w-3" />
                  {[edu.start_date, edu.end_date].filter(Boolean).join(" - ")}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition">
              <button onClick={() => setEditing(true)}
                className="btn-ghost inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[12px] text-muted">
                <Pencil className="h-3 w-3" /> Modifier
              </button>
              <button onClick={() => onDelete(index)}
                className="h-7 w-7 rounded-lg flex items-center justify-center text-subtle hover:text-rose-500 hover:bg-rose-500/10 transition">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function EducationPane({ cv, onUpdate }: { cv: CvData | null; onUpdate: (updated: CvData) => void }) {
  const [education, setEducation] = useState<CvEducation[]>(cv?.education ?? [])

  useEffect(() => { setEducation(cv?.education ?? []) }, [cv])

  const persist = async (next: CvEducation[]) => {
    const res = await updateCvData({ education: next })
    setEducation(res.data.education ?? [])
    onUpdate(res.data)
  }

  const handleSave = async (i: number, updated: CvEducation) => {
    const next = [...education]; next[i] = updated; await persist(next)
  }

  const handleDelete = async (i: number) => { await persist(education.filter((_, idx) => idx !== i)) }
  const handleAdd = () => { setEducation((prev) => [EMPTY_EDU, ...prev]) }

  if (!cv) return <NoDataState icon={GraduationCap} label="Aucun CV analysé" />

  return (
    <div>
      <div className="flex items-center justify-between pt-5 pb-1">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">Formation</h2>
          <p className="text-[13px] text-muted mt-0.5">Extraite de votre CV. Modifiez ou ajoutez des entrées.</p>
        </div>
        <button onClick={handleAdd} className="btn-ghost inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px]">
          <Plus className="h-3.5 w-3.5" /> Ajouter
        </button>
      </div>
      {education.length === 0 ? (
        <NoDataState icon={GraduationCap} label="Aucune formation" />
      ) : (
        <div className="py-4 space-y-3">
          {education.map((edu, i) => (
            <EduCard key={i} edu={edu} index={i} onSave={handleSave} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
const DEFAULT_PREFS: UserPreferences = { contract_types: [], work_modes: [], locations: [], languages: [] }

export default function ProfilePage() {
  const { me, isAdmin, refetchMe } = useUser()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>("overview")
  const queryClient = useQueryClient()
  const { data: cvData, isLoading: cvLoading } = useCvData()
  const { data: prefsData, isLoading: prefsLoading } = usePreferences()
  const loading = cvLoading || prefsLoading

  const [cv, setCv] = useState<CvData | null>(null)
  const [prefs, setPrefs] = useState<UserPreferences>(DEFAULT_PREFS)
  const initialized = useRef(false)
  const [cvPendingFile, setCvPendingFile] = useState<File | null>(null)
  const [cvPhase, setCvPhase] = useState<"confirm" | "uploading" | "extracting" | "error">("confirm")
  const [launching, setLaunching] = useState(false)
  const [rateLimited, setRateLimited] = useState(() => {
    const ts = localStorage.getItem("ailfj_search_rl_at")
    return ts ? Date.now() - Number(ts) < 24 * 3_600_000 : false
  })
  const [inProgress, setInProgress] = useState(false)

  // Avatar state
  const avatarInputRef = useRef<HTMLInputElement>(null)
  const [avatarUploading, setAvatarUploading] = useState(false)
  const hasAvatar = !!me?.avatar_key || !!me?.avatar_url

  const displayName = me?.full_name || me?.email || "-"

  // Initialize local form state once from query cache (no re-init on background refetch)
  useEffect(() => {
    if (cvLoading || prefsLoading || initialized.current) return
    initialized.current = true
    if (cvData)    setCv(cvData)
    if (prefsData) setPrefs({ ...DEFAULT_PREFS, ...prefsData })
  }, [cvLoading, prefsLoading, cvData, prefsData])

  // Wrappers that update both local state and query cache after each save
  const handleUpdateCv = useCallback((data: CvData) => {
    setCv(data)
    queryClient.setQueryData(QK.cvData, data)
  }, [queryClient])

  const handleUpdatePrefs = useCallback((data: UserPreferences) => {
    setPrefs(data)
    queryClient.setQueryData(QK.preferences, data)
  }, [queryClient])

  const { logout } = useAuth()

  const handleCvUpdate = (file: File) => {
    setCvPhase("confirm")
    setCvPendingFile(file)
  }

  const handleCvConfirm = async () => {
    if (!cvPendingFile) return
    setCvPhase("uploading")
    try {
      const res = await uploadCV(cvPendingFile)
      const { cv_id, status } = res.data
      if (status === "ready") {
        // Same as current latest CV - nothing to update
        setCvPendingFile(null)
        setCvPhase("confirm")
        return
      }
      // New PDF - wait for extraction via SSE (3 min timeout)
      setCvPhase("extracting")
      const extracted = await new Promise<boolean>((resolve) => {
        const ctrl = new AbortController()
        const timer = setTimeout(() => { ctrl.abort(); resolve(false) }, 3 * 60 * 1000)
        const run = async () => {
          try {
            const r = await fetch(`/api/analysis/init-stream/${cv_id}`, {
              credentials: "include",
              signal: ctrl.signal,
            })
            if (!r.ok || !r.body) { clearTimeout(timer); resolve(false); return }
            const reader  = r.body.getReader()
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
                  if (event.done) { clearTimeout(timer); resolve(true); return }
                } catch { /* ignore */ }
              }
            }
          } catch { /* aborted or network error */ }
          clearTimeout(timer)
          resolve(false)
        }
        run()
      })
      if (extracted) {
        await queryClient.refetchQueries({ queryKey: QK.cvData })
        const fresh = queryClient.getQueryData<CvData>(QK.cvData)
        if (fresh) setCv(fresh)
        setCvPendingFile(null)
        setCvPhase("confirm")
      } else {
        setCvPhase("error")
      }
    } catch {
      setCvPhase("error")
    }
  }

  const handleLaunchSearch = async () => {
    setLaunching(true)
    try {
      await launchSearch()
      navigate("/dashboard")
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status
      if (status === 429) {
        localStorage.setItem("ailfj_search_rl_at", String(Date.now()))
        setRateLimited(true)
      } else if (status === 409) {
        setInProgress(true)
      }
      setLaunching(false)
    }
  }

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setAvatarUploading(true)
    try {
      await uploadAvatar(file)
      clearAvatarCache()     // force re-fetch in Sidebar, PageHeader, and here
      await refetchMe()      // me.avatar_key updates → AuthAvatar re-fetches automatically
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(detail ?? "Erreur lors de l'upload.")
    } finally {
      setAvatarUploading(false)
      if (avatarInputRef.current) avatarInputRef.current.value = ""
    }
  }

  const handleAvatarDelete = async () => {
    if (!confirm("Supprimer la photo de profil ?")) return
    setAvatarUploading(true)
    try {
      await deleteAvatar()
      clearAvatarCache()
      await refetchMe()
    } finally {
      setAvatarUploading(false)
    }
  }

  return (
    <Layout title="Profil">
      {cvPendingFile && (
        <CvUpdateModal
          onConfirm={handleCvConfirm}
          onCancel={() => { setCvPendingFile(null); setCvPhase("confirm") }}
          phase={cvPhase}
        />
      )}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">

        {/* Header */}
        <div className="flex items-start justify-between mb-6 gap-4">
          <div>
            <h1 className="text-xl font-semibold text-ink">Votre profil</h1>
            <p className="text-[13px] text-muted mt-0.5">Gérez vos informations et préférences de recherche.</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {cv && (() => {
              const blocked = rateLimited || inProgress
              const rlTs = localStorage.getItem("ailfj_search_rl_at")
              const hours = rlTs ? Math.max(1, Math.ceil((24 * 3_600_000 - (Date.now() - Number(rlTs))) / 3_600_000)) : 24
              const tooltip = rateLimited
                ? `Limite atteinte - réessayez dans ${hours}h`
                : inProgress ? "Une recherche est déjà en cours" : null
              return (
                <div className="relative group">
                  <button
                    onClick={handleLaunchSearch}
                    disabled={launching || blocked}
                    className="btn-accent ring-focus inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {launching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                    {launching ? "Lancement…" : "Lancer une recherche"}
                  </button>
                  {tooltip && (
                    <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 flex flex-col items-center opacity-0 group-hover:opacity-100 transition-opacity duration-150 z-20">
                      <div
                        className="rounded-lg px-3 py-1.5 text-[11px] font-medium text-white whitespace-nowrap flex items-center gap-1.5"
                        style={{ background: "rgb(var(--ink))" }}
                      >
                        <Clock className="h-3 w-3 shrink-0" />
                        {tooltip}
                      </div>
                      <div className="w-0 h-0" style={{ borderLeft: "5px solid transparent", borderRight: "5px solid transparent", borderTop: "5px solid rgb(var(--ink))" }} />
                    </div>
                  )}
                </div>
              )
            })()}
            <a href="mailto:support@ailfj.fr" className="btn-ghost inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[13px]">
              <ExternalLink className="h-3.5 w-3.5" /> Support
            </a>
          </div>
        </div>

        {/* Identity card */}
        <div className="card rounded-2xl p-4 mb-6 flex items-center gap-4">
          {/* Avatar */}
          <div className="relative shrink-0 group">
            <input
              ref={avatarInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="hidden"
              onChange={handleAvatarChange}
            />
            <button
              onClick={() => avatarInputRef.current?.click()}
              className="relative h-14 w-14 rounded-2xl overflow-hidden focus:outline-none focus:ring-2 focus:ring-accent/40"
              title="Changer la photo"
            >
              {hasAvatar ? (
                <AuthAvatar avatarKey={me?.avatar_key} avatarUrl={me?.avatar_url} className="h-full w-full object-cover" />
              ) : (
                <div className="h-full w-full bg-accent/15 flex items-center justify-center text-accent text-xl font-bold select-none">
                  {displayName !== "-" ? displayName[0].toUpperCase() : <User className="h-6 w-6" />}
                </div>
              )}
              {/* Overlay - pointer-events-none so it never blocks the button click */}
              <div className="pointer-events-none absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                {avatarUploading
                  ? <Loader2 className="h-5 w-5 text-white animate-spin" />
                  : <Camera className="h-5 w-5 text-white" />}
              </div>
            </button>
            {/* Delete button - only for a self-hosted upload; nothing to remove
                for a Google-provided picture with no upload of its own */}
            {!!me?.avatar_key && !avatarUploading && (
              <button
                onClick={handleAvatarDelete}
                title="Supprimer la photo"
                className="absolute -top-1.5 -right-1.5 h-5 w-5 rounded-full bg-rose-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition shadow"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>

          <div className="flex-1 min-w-0">
            <p className="text-[15px] font-semibold text-ink truncate">{displayName}</p>
            <p className="text-[12px] text-muted truncate">{me?.email ?? "-"}</p>
            {cv && (
              <p className="text-[11px] text-subtle mt-0.5">
                {LEVEL_LABELS[cv.level] ?? cv.level}{cv.location ? ` · ${cv.location}` : ""}
              </p>
            )}
          </div>
          <button onClick={logout} className="btn-ghost inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[13px] text-muted shrink-0">
            <LogOut className="h-3.5 w-3.5" /> Déconnexion
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex gap-0.5 border-b mb-6" style={{ borderColor: "rgb(var(--line) / var(--line-a))" }}>
          {TABS.map(({ key, label, icon: Icon }) => {
            const active = tab === key
            return (
              <button key={key} onClick={() => setTab(key)}
                className={`inline-flex items-center gap-1.5 px-3 py-2.5 text-[13px] font-medium transition-colors relative whitespace-nowrap ${active ? "text-ink" : "text-muted hover:text-ink"}`}>
                <Icon className="h-3.5 w-3.5 shrink-0" />
                <span className="hidden sm:inline">{label}</span>
                {active && <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-accent" />}
              </button>
            )
          })}
        </div>

        {/* Content */}
        {loading && tab !== "overview" ? (
          <div className="card rounded-xl px-5 py-16 flex items-center justify-center">
            <Loader2 className="h-5 w-5 text-subtle animate-spin" />
          </div>
        ) : (
          <>
            {tab === "overview" && (
              <div className="space-y-6">
                <div className="card rounded-xl px-5">
                  <OverviewPane
                    me={me}
                    isAdmin={isAdmin}
                    hasAvatar={hasAvatar}
                    avatarUploading={avatarUploading}
                    onAvatarChange={handleAvatarChange}
                    onAvatarDelete={handleAvatarDelete}
                    onCvUpdate={handleCvUpdate}
                  />
                </div>
                <PlanPane />
              </div>
            )}
            {tab === "preferences" && (
              <div className="card rounded-xl px-5">
                <PreferencesPane cv={cv} prefs={prefs} onUpdateCv={handleUpdateCv} onUpdatePrefs={handleUpdatePrefs} />
              </div>
            )}
            {tab === "stack" && (
              <div className="card rounded-xl px-5">
                <StackPane cv={cv} onUpdate={handleUpdateCv} />
              </div>
            )}
            {tab === "experience" && (
              <div className="card rounded-xl px-5">
                <ExperiencePane cv={cv} onUpdate={handleUpdateCv} />
              </div>
            )}
            {tab === "education" && (
              <div className="card rounded-xl px-5">
                <EducationPane cv={cv} onUpdate={handleUpdateCv} />
              </div>
            )}
          </>
        )}

        {/* Footer */}
        <div className="mt-6 flex items-center justify-between text-[12px] text-subtle">
          <a href="mailto:support@ailfj.fr" className="hover:text-muted transition-colors inline-flex items-center gap-1">
            <Mail className="h-3 w-3" /> Contacter le support
          </a>
          <span>AILFJ · v1.0</span>
        </div>
      </div>

    </Layout>
  )
}