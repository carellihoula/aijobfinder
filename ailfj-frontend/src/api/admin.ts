import { client } from "./client"

export interface UserSummary {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  is_admin: boolean
}

export interface AnalysisSummary {
  id: string
  user_id: string
  status: string
  keywords: string[] | null
  error: string | null
}

export interface TaskResult {
  task_id: string
  status: string
  detail: string
}

// ── Users ────────────────────────────────────────────────────────────────────

export const listUsers = () =>
  client.get<UserSummary[]>("/admin/users")

export const promoteUser = (userId: string) =>
  client.patch<UserSummary>(`/admin/users/${userId}/promote`)

export const demoteUser = (userId: string) =>
  client.patch<UserSummary>(`/admin/users/${userId}/demote`)

// ── Analyses ─────────────────────────────────────────────────────────────────

export const listAllAnalyses = () =>
  client.get<AnalysisSummary[]>("/admin/analyses")

export const rerunAnalysis = (analysisId: string) =>
  client.post<TaskResult>(`/admin/analyses/${analysisId}/rerun`)

// ── Cortex / crons ────────────────────────────────────────────────────────────

export const triggerIngestion = (locations?: string[]) =>
  client.post<TaskResult>("/admin/cortex/ingest", { locations: locations ?? null })

export const triggerRefresh = () =>
  client.post<TaskResult>("/admin/cortex/refresh")

export const triggerCleanup = (days = 30) =>
  client.post<TaskResult>("/admin/cortex/cleanup", { days })