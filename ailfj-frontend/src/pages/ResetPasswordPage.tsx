import { useState, type FormEvent } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { Lock, CheckCircle, Loader2, Eye, EyeOff, AlertTriangle } from 'lucide-react'
import { resetPassword } from '../api/auth'

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate  = useNavigate()
  const token     = params.get('token') ?? ''

  const [password, setPassword]   = useState('')
  const [confirm, setConfirm]     = useState('')
  const [showPwd, setShowPwd]     = useState(false)
  const [loading, setLoading]     = useState(false)
  const [done, setDone]           = useState(false)
  const [error, setError]         = useState<string | null>(null)

  const mismatch = confirm.length > 0 && password !== confirm
  const weak     = password.length > 0 && password.length < 8
  const ready    = token && password.length >= 8 && password === confirm

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!ready) return
    setLoading(true)
    setError(null)
    try {
      await resetPassword(token, password)
      setDone(true)
      setTimeout(() => navigate('/login'), 2500)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(detail ?? "Lien invalide ou expiré. Recommencez depuis la page mot de passe oublié.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[rgb(var(--bg))] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 mb-6">
            <span className="h-8 w-8 rounded-lg bg-accent flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 1L14 4.5V11.5L8 15L2 11.5V4.5L8 1Z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round"/>
                <circle cx="8" cy="8" r="2" fill="#fff"/>
              </svg>
            </span>
            <span className="font-semibold text-ink tracking-tight">AILFJ</span>
          </div>
          <h1 className="text-2xl font-semibold text-ink tracking-tight">Nouveau mot de passe</h1>
          <p className="mt-1 text-sm text-muted">Choisissez un nouveau mot de passe pour votre compte.</p>
        </div>

        {!token ? (
          <div className="card rounded-2xl p-6 text-center space-y-3">
            <AlertTriangle className="h-8 w-8 text-amber-500 mx-auto" />
            <p className="text-[13px] text-muted">Lien invalide. Vérifiez le lien dans votre e-mail.</p>
            <Link to="/forgot-password" className="text-accent text-[13px] hover:underline">
              Renvoyer un lien
            </Link>
          </div>
        ) : done ? (
          <div className="card rounded-2xl p-6 text-center space-y-3">
            <div className="flex justify-center">
              <div className="h-12 w-12 rounded-full bg-accent/10 flex items-center justify-center">
                <CheckCircle className="h-6 w-6 text-accent" />
              </div>
            </div>
            <p className="text-[14px] font-semibold text-ink">Mot de passe modifié</p>
            <p className="text-[13px] text-muted">Redirection vers la connexion…</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">Nouveau mot de passe</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-subtle" />
                <input
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className={`input-base ring-focus pl-9 pr-9 ${weak ? 'border-amber-400' : ''}`}
                  placeholder="Minimum 8 caractères"
                />
                <button type="button" onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-subtle hover:text-muted transition">
                  {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {weak && <p className="text-[11px] text-amber-500 mt-1">Minimum 8 caractères.</p>}
            </div>

            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">Confirmer le mot de passe</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-subtle" />
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  className={`input-base ring-focus pl-9 ${mismatch ? 'border-rose-400' : ''}`}
                  placeholder="••••••••"
                />
              </div>
              {mismatch && <p className="text-[11px] text-rose-500 mt-1">Les mots de passe ne correspondent pas.</p>}
            </div>

            {error && (
              <p className="text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={!ready || loading}
              className="btn-accent ring-focus w-full rounded-lg py-2.5 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Modification…</> : 'Modifier le mot de passe'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
