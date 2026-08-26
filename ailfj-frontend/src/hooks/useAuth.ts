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
    } catch {
      setError('Email ou mot de passe incorrect')
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

  return { loading, error, loginUser, registerUser, logout }
}
