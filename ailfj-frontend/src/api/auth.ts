import { client } from './client'

export const register = (email: string, password: string, full_name?: string) =>
  client.post<{ ok: boolean }>('/auth/register', { email, password, full_name })

export const login = (email: string, password: string) =>
  client.post<{ ok: boolean }>('/auth/login', { email, password })

export const googleAuth = (idToken: string) =>
  client.post<{ ok: boolean; is_new_user: boolean }>('/auth/google', { id_token: idToken })

export const logout = () => client.post('/auth/logout')

export const forgotPassword = (email: string) =>
  client.post<{ ok: boolean }>('/auth/forgot-password', { email })

export const resetPassword = (token: string, new_password: string) =>
  client.post<{ ok: boolean }>('/auth/reset-password', { token, new_password })

export const verifyEmail = (token: string) =>
  client.get<{ ok: boolean }>(`/auth/verify-email?token=${token}`)

export const resendVerification = () =>
  client.post<{ ok: boolean }>('/auth/resend-verification')

export interface MeResponse {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_admin: boolean
  is_verified: boolean
  created_at: string
  avatar_key: string | null
  avatar_url: string | null
  has_password: boolean
}

export const getMe = () => client.get<MeResponse>('/users/me')

export const uploadAvatar = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return client.post<{ avatar_url: string }>('/users/me/avatar', form)
}

export const deleteAvatar = () => client.delete('/users/me/avatar')
