import { client } from './client'
import type { Analysis } from '../types'

// Mirrors backend's _PIPELINE_COOLDOWN (analysis/router.py) - shared by every
// page that shows a "launch search" button (Dashboard, Profile) so they can't
// drift apart the way the old per-page localStorage hacks did.
export const SEARCH_COOLDOWN_MS = 14_400_000 // 4h

export interface CvInitResult {
  cv_id: string
  status: 'processing' | 'ready'
}

/** Upload a PDF to initialise the profile (extraction only, no job search). */
export const uploadCV = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return client.post<CvInitResult>('/analysis/upload', form)
}

/** Launch a job-search run from the current profile. Rate-limited 24 h. */
export const launchSearch = () =>
  client.post<Analysis>('/analysis/search')

export const getAnalysis = (id: string) =>
  client.get<Analysis>(`/analysis/${id}`)

export const getLatestAnalysis = () =>
  client.get<Analysis>('/analysis/latest')

export interface CvExperience {
  title?: string
  company?: string
  start_date?: string
  end_date?: string
  description?: string
}

export interface CvEducation {
  degree?: string
  school?: string
  start_date?: string
  end_date?: string
}

export interface CvLanguage {
  name: string
  level?: string
}

export interface CvData {
  full_name?: string
  email?: string
  phone?: string
  location?: string
  summary?: string
  skills: string[]
  roles: string[]
  experience_years: number
  level: string
  experiences: CvExperience[]
  education: CvEducation[]
  languages: CvLanguage[]
  hobbies: { name: string }[]
}

export const getCvData = () =>
  client.get<CvData>('/analysis/cv-data')

export const updateCvData = (data: Partial<CvData>) =>
  client.patch<CvData>('/analysis/cv-data', data)