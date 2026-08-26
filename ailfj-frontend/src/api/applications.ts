import { client } from "./client"

export type ApplicationStatus = "applied" | "in_progress" | "rejected" | "accepted"
export type CoverLetterStatus = "pending" | "processing" | "completed" | "failed"

export interface ApplicationStep {
  id: string
  label: string
  status: ApplicationStatus
  date: string | null
  notes: string | null
  created_at: string
}

export interface Application {
  id: string
  title: string
  company: string
  url: string | null
  summary: string | null
  description: string | null
  status: ApplicationStatus
  cover_letter_status: CoverLetterStatus
  created_at: string
  updated_at: string | null
  steps: ApplicationStep[]
}

// ── List / detail / update / delete ─────────────────────────────────────────

export const listApplications = () =>
  client.get<Application[]>("/applications")

export const getApplication = (id: string) =>
  client.get<Application>(`/applications/${id}`)

export const updateApplication = (
  id: string,
  payload: { title?: string; company?: string; status?: ApplicationStatus },
) => client.patch<Application>(`/applications/${id}`, payload)

export const deleteApplication = (id: string) =>
  client.delete(`/applications/${id}`)

// ── Steps ────────────────────────────────────────────────────────────────────

export const addStep = (
  applicationId: string,
  payload: { label: string; status: ApplicationStatus; date?: string | null; notes?: string | null },
) => client.post<Application>(`/applications/${applicationId}/steps`, payload)

export const updateStep = (
  applicationId: string,
  stepId: string,
  payload: { label?: string; status?: ApplicationStatus; date?: string | null; notes?: string | null },
) => client.patch<Application>(`/applications/${applicationId}/steps/${stepId}`, payload)

export const deleteStep = (applicationId: string, stepId: string) =>
  client.delete(`/applications/${applicationId}/steps/${stepId}`)

// ── Preview (scrape/paste, no persistence, no cover letter yet) ────────────

export interface JobPreview {
  title: string
  company: string
  location: string
  description: string
  url: string | null
}

export const previewJob = (payload: { url?: string; text?: string }) =>
  client.post<JobPreview>("/applications/preview", payload)

// ── Create (persists + enqueues background cover letter generation) ────────

export const createApplication = (payload: {
  title: string
  company: string
  location?: string
  description: string
  url?: string | null
  suggestion?: string
}) => client.post<Application>("/applications", payload)

export const refineCoverLetter = (applicationId: string, suggestion: string) =>
  client.post<Application>(`/applications/${applicationId}/cover-letter/refine`, { suggestion })

// ── Cover letter PDF (only once cover_letter_status === "completed") ───────

export interface CoverLetterPdf {
  blob: Blob
  content: Record<string, unknown> | null
}

export const fetchApplicationCoverLetterPdf = async (applicationId: string): Promise<CoverLetterPdf> => {
  const res = await fetch(`/api/applications/${applicationId}/cover-letter`, {
    credentials: "include",
  })
  if (!res.ok) {
    const detail = await res.json().then((d) => d?.detail).catch(() => res.statusText)
    throw new Error(`HTTP ${res.status} — ${detail}`)
  }
  const blob = await res.blob()
  const contentB64 = res.headers.get("X-Cover-Letter-Content")
  return { blob, content: contentB64 ? JSON.parse(atob(contentB64)) : null }
}

// ── Poll an application until cover_letter_status settles ──────────────────

export const pollApplication = async (
  id: string,
  { intervalMs = 2000, timeoutMs = 90000 }: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<Application> => {
  const start = Date.now()
  while (true) {
    const { data } = await getApplication(id)
    if (data.cover_letter_status === "completed" || data.cover_letter_status === "failed") return data
    if (Date.now() - start > timeoutMs) return data
    await new Promise((r) => setTimeout(r, intervalMs))
  }
}

/** Documents page helper: fetches the already-generated PDF, or — when a suggestion is
 * given — refines it first (enqueues Celery, polls, then fetches the new PDF). */
export const fetchOrRefineApplicationCoverLetter = async (
  applicationId: string,
  suggestion = "",
): Promise<CoverLetterPdf> => {
  if (suggestion.trim()) {
    await refineCoverLetter(applicationId, suggestion)
    const result = await pollApplication(applicationId)
    if (result.cover_letter_status !== "completed") {
      throw new Error("La génération a échoué — réessayez.")
    }
  }
  return fetchApplicationCoverLetterPdf(applicationId)
}
