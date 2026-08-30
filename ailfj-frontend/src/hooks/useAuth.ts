import { useState } from 'react'
import * as authApi from '../api/auth'

export function useAuth() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loginUser = async (email: string, password: string) => {
    setLoading(true)
    setError(null)
    try {
      await authApi.login(email, password)
      return true
    } catch (e: unknown) {
      // 429 = rate-limited (see backend/app/auth/rate_limit.py) - show the
      // real "try again in Xmin" message, not the generic wrong-password one,
      // otherwise a locked-out user with the *correct* password just thinks
      // they're mistyping it.
      const err = e as { response?: { status?: number; data?: { detail?: string } } }
      if (err.response?.status === 429 && err.response.data?.detail) {
        setError(err.response.data.detail)
      } else {
        setError('Email ou mot de passe incorrect')
      }
      return false
    } finally {
      setLoading(false)
    }
  }

  const googleLogin = async (idToken: string): Promise<{ isNewUser: boolean } | false> => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await authApi.googleAuth(idToken)
      return { isNewUser: data.is_new_user }
    } catch {
      setError('La connexion avec Google a échoué')
      return false
    } finally {
      setLoading(false)
    }
  }

  const registerUser = async (email: string, password: string, fullName: string) => {
    setLoading(true)
    setError(null)
    try {
      await authApi.register(email, password, fullName)
      return true
    } catch {
      setError('Cet email est déjà utilisé')
      return false
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    try { await authApi.logout() } catch { /* ignore */ }
    window.location.href = '/login'
  }

  return { loading, error, loginUser, googleLogin, registerUser, logout }
}
