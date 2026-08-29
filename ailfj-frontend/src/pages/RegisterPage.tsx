import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { GoogleLogin } from '@react-oauth/google'
import { useAuth } from '../hooks/useAuth'
import { useUser } from '../lib/userContext'

export default function RegisterPage() {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const { registerUser, googleLogin, loading, error } = useAuth()
  const { refetchMe } = useUser()
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const ok = await registerUser(email, password, fullName)
    if (ok) {
      await refetchMe()
      navigate('/setup')
    }
  }

  const handleGoogleSuccess = async (credential?: string) => {
    if (!credential) return
    const result = await googleLogin(credential)
    if (result) {
      await refetchMe()
      // Someone with an existing account may still click Google here by mistake -
      // only a genuinely new signup needs onboarding.
      navigate(result.isNewUser ? '/setup' : '/dashboard')
    }
  }

  return (
    <div className="min-h-screen bg-[rgb(var(--bg))] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Brand */}
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
          <h1 className="text-2xl font-semibold text-ink tracking-tight">Créer un compte</h1>
          <p className="mt-1 text-sm text-muted">Configurez votre profil en quelques étapes</p>
        </div>

        <div className="mb-5 flex justify-center">
          <GoogleLogin
            onSuccess={(cred) => handleGoogleSuccess(cred.credential)}
            onError={() => {}}
          />
        </div>

        <div className="flex items-center gap-3 mb-5">
          <div className="flex-1 h-px bg-line/15" />
          <span className="text-xs text-subtle">ou</span>
          <div className="flex-1 h-px bg-line/15" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-muted mb-1.5">Nom complet</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="input-base ring-focus"
              placeholder="Jean Dupont"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-muted mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="input-base ring-focus"
              placeholder="vous@exemple.com"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-muted mb-1.5">Mot de passe</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="input-base ring-focus"
              placeholder="Minimum 6 caractères"
            />
          </div>

          {error && (
            <p className="text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-accent ring-focus w-full rounded-lg py-2.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <><span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Création…</>
            ) : 'Créer mon compte'}
          </button>
        </form>

        <p className="text-center text-sm text-muted mt-6">
          Déjà un compte ?{' '}
          <Link to="/login" className="text-accent hover:underline font-medium">
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  )
}