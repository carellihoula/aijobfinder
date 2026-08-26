import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { CheckCircle, AlertTriangle, Loader2 } from 'lucide-react'
import { verifyEmail } from '../api/auth'
import { useUser } from '../lib/userContext'

export default function VerifyEmailPage() {
  const [params]  = useSearchParams()
  const token     = params.get('token') ?? ''
  const { refetchMe } = useUser()

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')

  useEffect(() => {
    if (!token) { setStatus('error'); return }
    verifyEmail(token)
      .then(async () => {
        await refetchMe()
        setStatus('success')
      })
      .catch(() => setStatus('error'))
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

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
        </div>

        <div className="card rounded-2xl p-8 text-center space-y-4">
          {status === 'loading' && (
            <>
              <Loader2 className="h-10 w-10 text-accent animate-spin mx-auto" />
              <p className="text-[14px] text-muted">Vérification en cours…</p>
            </>
          )}
          {status === 'success' && (
            <>
              <div className="h-14 w-14 rounded-full bg-accent/10 flex items-center justify-center mx-auto">
                <CheckCircle className="h-8 w-8 text-accent" />
              </div>
              <p className="text-[16px] font-semibold text-ink">Compte vérifié !</p>
              <p className="text-[13px] text-muted">Votre adresse e-mail a été confirmée avec succès.</p>
              <Link to="/dashboard" className="btn-accent inline-flex items-center rounded-lg px-4 py-2 text-[13px] font-medium">
                Accéder à mon espace
              </Link>
            </>
          )}
          {status === 'error' && (
            <>
              <div className="h-14 w-14 rounded-full bg-rose-500/10 flex items-center justify-center mx-auto">
                <AlertTriangle className="h-8 w-8 text-rose-500" />
              </div>
              <p className="text-[16px] font-semibold text-ink">Lien invalide ou expiré</p>
              <p className="text-[13px] text-muted">Le lien de vérification est invalide ou a expiré (24h).</p>
              <Link to="/" className="text-accent text-[13px] hover:underline">
                Retour à l'accueil
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  )
}