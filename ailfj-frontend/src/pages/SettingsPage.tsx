import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { User, Mail, Lock, Trash2, Save, Loader2, Check, AlertTriangle, Eye, EyeOff } from "lucide-react"
import Layout from "../components/Layout"
import { useUser } from "../lib/userContext"
import { useAuth } from "../hooks/useAuth"
import { updateProfile, changePassword, deleteAccount } from "../api/users"

function SectionCard({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <div className="card rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-line/10">
        <p className="text-[14px] font-semibold text-ink">{title}</p>
        <p className="text-[12px] text-muted mt-0.5">{desc}</p>
      </div>
      <div className="px-5 py-5 space-y-4">{children}</div>
    </div>
  )
}

function Field({ label, icon: Icon, children }: { label: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-1.5 text-[12px] font-medium text-muted">
        <Icon className="h-3.5 w-3.5" /> {label}
      </label>
      {children}
    </div>
  )
}

const inputCls = "w-full rounded-lg px-3 py-2 text-[13px] text-ink border border-line/20 bg-transparent outline-none focus:border-accent focus:ring-1 focus:ring-accent/30 transition"

function Toast({ type, message }: { type: "success" | "error"; message: string }) {
  return (
    <div className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-medium ${
      type === "success" ? "bg-accent/10 text-accent border border-accent/20" : "bg-rose-500/10 text-rose-500 border border-rose-500/20"
    }`}>
      {type === "success" ? <Check className="h-3.5 w-3.5 shrink-0" /> : <AlertTriangle className="h-3.5 w-3.5 shrink-0" />}
      {message}
    </div>
  )
}

// ─── Personal info section ────────────────────────────────────────────────────
function PersonalInfoSection({ me, onRefresh }: { me: { full_name?: string | null; email?: string }; onRefresh: () => void }) {
  const [name, setName]   = useState(me.full_name ?? "")
  const [email, setEmail] = useState(me.email ?? "")
  const [saving, setSaving] = useState(false)
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; msg: string } | null>(null)

  const dirty = name !== (me.full_name ?? "") || email !== (me.email ?? "")

  const save = async () => {
    setSaving(true)
    setFeedback(null)
    try {
      await updateProfile({
        full_name: name || undefined,
        email: email !== me.email ? email : undefined,
      })
      await onRefresh()
      setFeedback({ type: "success", msg: "Informations mises à jour." })
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setFeedback({ type: "error", msg: detail ?? "Erreur lors de la mise à jour." })
    } finally {
      setSaving(false)
    }
  }

  return (
    <SectionCard title="Informations personnelles" desc="Votre nom et adresse e-mail affichés sur votre compte.">
      <Field label="Nom complet" icon={User}>
        <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Prénom Nom" />
      </Field>
      <Field label="Adresse e-mail" icon={Mail}>
        <input className={inputCls} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="vous@exemple.fr" />
        <p className="text-[11px] text-subtle">Changer l'e-mail vous déconnectera au prochain accès.</p>
      </Field>
      {feedback && <Toast type={feedback.type} message={feedback.msg} />}
      <button
        onClick={save}
        disabled={!dirty || saving}
        className="btn-accent inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-[13px] font-medium disabled:opacity-50"
      >
        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
        {saving ? "Enregistrement…" : "Enregistrer"}
      </button>
    </SectionCard>
  )
}

// ─── Password section ─────────────────────────────────────────────────────────
function PasswordSection() {
  const [current, setCurrent]   = useState("")
  const [next, setNext]         = useState("")
  const [confirm, setConfirm]   = useState("")
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNext, setShowNext]       = useState(false)
  const [saving, setSaving]     = useState(false)
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; msg: string } | null>(null)

  const mismatch = next.length > 0 && confirm.length > 0 && next !== confirm
  const weak     = next.length > 0 && next.length < 8
  const ready    = current && next && confirm && next === confirm && next.length >= 8

  const save = async () => {
    setSaving(true)
    setFeedback(null)
    try {
      await changePassword({ current_password: current, new_password: next })
      setCurrent(""); setNext(""); setConfirm("")
      setFeedback({ type: "success", msg: "Mot de passe modifié avec succès." })
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setFeedback({ type: "error", msg: detail ?? "Erreur lors du changement." })
    } finally {
      setSaving(false)
    }
  }

  return (
    <SectionCard title="Sécurité" desc="Changez votre mot de passe. Minimum 8 caractères.">
      <Field label="Mot de passe actuel" icon={Lock}>
        <div className="relative">
          <input
            className={inputCls}
            type={showCurrent ? "text" : "password"}
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            placeholder="••••••••"
          />
          <button
            type="button"
            onClick={() => setShowCurrent((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle hover:text-muted transition"
          >
            {showCurrent ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        </div>
      </Field>
      <Field label="Nouveau mot de passe" icon={Lock}>
        <div className="relative">
          <input
            className={`${inputCls} ${weak ? "border-amber-400 focus:border-amber-400 focus:ring-amber-400/30" : ""}`}
            type={showNext ? "text" : "password"}
            value={next}
            onChange={(e) => setNext(e.target.value)}
            placeholder="••••••••"
          />
          <button
            type="button"
            onClick={() => setShowNext((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle hover:text-muted transition"
          >
            {showNext ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        </div>
        {weak && <p className="text-[11px] text-amber-500">Minimum 8 caractères.</p>}
      </Field>
      <Field label="Confirmer le nouveau mot de passe" icon={Lock}>
        <input
          className={`${inputCls} ${mismatch ? "border-rose-400 focus:border-rose-400 focus:ring-rose-400/30" : ""}`}
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="••••••••"
        />
        {mismatch && <p className="text-[11px] text-rose-500">Les mots de passe ne correspondent pas.</p>}
      </Field>
      {feedback && <Toast type={feedback.type} message={feedback.msg} />}
      <button
        onClick={save}
        disabled={!ready || saving}
        className="btn-accent inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-[13px] font-medium disabled:opacity-50"
      >
        {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Lock className="h-3.5 w-3.5" />}
        {saving ? "Modification…" : "Modifier le mot de passe"}
      </button>
    </SectionCard>
  )
}

// ─── Danger zone ──────────────────────────────────────────────────────────────
function DangerZone() {
  const [confirming, setConfirming] = useState(false)
  const [input, setInput]           = useState("")
  const [deleting, setDeleting]     = useState(false)
  const { logout } = useAuth()

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await deleteAccount()
      await logout()
    } catch {
      setDeleting(false)
    }
  }

  return (
    <div className="card rounded-2xl overflow-hidden border border-rose-500/20">
      <div className="px-5 py-4 border-b border-rose-500/10" style={{ background: "rgb(239 68 68 / 0.03)" }}>
        <p className="text-[14px] font-semibold text-rose-500">Zone de danger</p>
        <p className="text-[12px] text-muted mt-0.5">Actions irréversibles sur votre compte.</p>
      </div>
      <div className="px-5 py-5">
        {!confirming ? (
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-[13px] font-medium text-ink">Supprimer le compte</p>
              <p className="text-[12px] text-muted mt-0.5">Désactive définitivement votre compte et toutes vos données.</p>
            </div>
            <button
              onClick={() => setConfirming(true)}
              className="shrink-0 inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[12px] font-medium text-rose-500 border border-rose-500/30 hover:bg-rose-500/10 transition"
            >
              <Trash2 className="h-3.5 w-3.5" /> Supprimer
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-start gap-2 rounded-lg bg-rose-500/8 border border-rose-500/20 px-3 py-2.5">
              <AlertTriangle className="h-4 w-4 text-rose-500 shrink-0 mt-0.5" />
              <p className="text-[12px] text-rose-600 dark:text-rose-400">
                Cette action est <strong>irréversible</strong>. Tapez <strong>SUPPRIMER</strong> pour confirmer.
              </p>
            </div>
            <input
              className={inputCls}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="SUPPRIMER"
            />
            <div className="flex gap-2">
              <button
                onClick={handleDelete}
                disabled={input !== "SUPPRIMER" || deleting}
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[12px] font-medium bg-rose-500 text-white hover:bg-rose-600 transition disabled:opacity-50"
              >
                {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                {deleting ? "Suppression…" : "Confirmer la suppression"}
              </button>
              <button
                onClick={() => { setConfirming(false); setInput("") }}
                className="btn-ghost inline-flex items-center rounded-lg px-3 py-2 text-[12px] text-muted"
              >
                Annuler
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function SettingsPage() {
  const { me, refetchMe } = useUser()
  const navigate = useNavigate()

  if (!me) {
    navigate("/login", { replace: true })
    return null
  }

  return (
    <Layout title="Paramètres">
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <div className="mb-2">
          <h1 className="text-xl font-semibold text-ink">Paramètres du compte</h1>
          <p className="text-[13px] text-muted mt-0.5">Gérez vos informations personnelles et la sécurité de votre compte.</p>
        </div>

        <PersonalInfoSection me={me} onRefresh={refetchMe} />
        <PasswordSection />
        <DangerZone />
      </div>
    </Layout>
  )
}
