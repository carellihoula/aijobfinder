import { client } from './client'

export interface UserPreferences {
  contract_types: string[]
  work_modes: string[]
  locations: string[]
  languages: { name: string; level?: string }[]
  gender?: "male" | "female" | ""
}

export const getPreferences = () =>
  client.get<UserPreferences>('/users/me/preferences')

export const updatePreferences = (data: Partial<UserPreferences>) =>
  client.patch<UserPreferences>('/users/me/preferences', data)

export const updateProfile = (data: { full_name?: string; email?: string }) =>
  client.patch('/users/me', data)

export const changePassword = (data: { current_password: string; new_password: string }) =>
  client.post('/users/me/change-password', data)

export const deleteAccount = () =>
  client.delete('/users/me')