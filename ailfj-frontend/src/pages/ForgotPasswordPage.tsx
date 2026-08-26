import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Mail, ArrowLeft, CheckCircle, Loader2 } from 'lucide-react'
import { forgotPassword } from '../api/auth'

export default function ForgotPasswordPage() {
  const [email, setEmail]   = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent]     = useState(false)
  const [error, setError]   = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await forgotPassword(email)
      setSent(true)
    } catch {
      setError("Une erreur est survenue. Réessayez.")
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
          <h1 className="text-2xl font-semibold text-ink tracking-tight">Mot de passe oublié</h1>
          <p className="mt-1 text-sm text-muted">Entrez votre e-mail pour recevoir un lien de réinitialisation.</p>
        </div>

        {sent ? (
          <div className="card rounded-2xl p-6 text-center space-y-3">
            <div className="flex justify-center">
              <div className="h-12 w-12 rounded-full bg-accent/10 flex items-center justify-center">
                <CheckCircle className="h-6 w-6 text-accent" />
              </div>
            </div>
            <p className="text-[14px] font-semibold text-ink">E-mail envoyé</p>
            <p className="text-[13px] text-muted">
              Si un compte existe pour <strong>{email}</strong>, vous recevrez un lien dans quelques minutes.
            </p>
            <p className="text-[12px] text-subtle">Vérifiez aussi vos spams.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">Adresse e-mail</label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-subtle" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="input-base ring-focus pl-9"
                  placeholder="vous@exemple.com"
                />
              </div>
            </div>

            {error && (
              <p className="text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-accent ring-focus w-full rounded-lg py-2.5 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? <><Loader2 className="h-4 w-4 animate-spin" /> Envoi…</> : 'Envoyer le lien'}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-muted">
          <Link to="/login" className="inline-flex items-center gap-1 hover:text-ink transition">
            <ArrowLeft className="h-3.5 w-3.5" /> Retour à la connexion
          </Link>
        </p>
      </div>
    </div>
  )
}