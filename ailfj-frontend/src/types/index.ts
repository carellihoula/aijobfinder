export interface User {
  id: string
  email: string
  full_name?: string
}

export interface JobMatch {
  job: {
    title: string
    company: string
    location: string
    desc: string
    url: string
    date: string
    contract_type: string
    remote: boolean
    _score?: number
  }
  score: number
  matching_skills: string[]
  missing_skills: string[]
  reason: string
}

export type ContractType = 'cdi' | 'cdd' | 'stage' | 'alternance' | 'freelance' | 'temps_partiel'
export type DatePosted = 'today' | '3days' | 'week' | 'month'
export type ExperienceLevel = 'junior' | 'mid' | 'senior'

export interface SearchFilters {
  locations: string[]
  contract_type: ContractType | ''
  remote: boolean
  date_posted: DatePosted | ''
  experience_level: ExperienceLevel | ''
}

export const DEFAULT_SEARCH_FILTERS: SearchFilters = {
  locations: [],
  contract_type: '',
  remote: false,
  date_posted: '',
  experience_level: '',
}

export interface Analysis {
  id: string
  user_id: string
  cv_id?: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  search_filters?: SearchFilters
  keywords?: string[]
  matches?: JobMatch[]
  final_report?: string
  error?: string
  created_at: string
  updated_at?: string
}