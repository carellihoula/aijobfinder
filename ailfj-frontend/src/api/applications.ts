import { client } from "./client"

export type ApplicationStatus = "applied" | "in_progress" | "rejected" | "accepted"
export type CoverLetterStatus = "pending" | "processing" | "completed" | "failed"

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

// ── Preview (scrape/paste, no persistence, no cover letter yet) ────────────

export interface JobPreview {
  title: string
  company: string
  location: string
  description: string
  url: string | null
}

export const previewJob = (payload: { url?: string; text?: string }, signal?: AbortSignal) =>
  client.post<JobPreview>("/applications/preview", payload, { signal })

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
    throw new Error(`HTTP ${res.status} - ${detail}`)
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

// ── Editor-first flow: content lives in SimpleEditor, PDF only exists on export ──

export interface CoverLetterJson {
  content: Record<string, unknown>
  body: string
}

/** Fetches the stored letter as JSON - no PDF rendering. Returns null on 404. */
export const getApplicationCoverLetterBody = async (
  applicationId: string,
): Promise<CoverLetterJson | null> => {
  try {
    const { data } = await client.get<CoverLetterJson>(`/applications/${applicationId}/cover-letter/body`)
    return data
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status
    if (status === 404) return null
    throw e
  }
}

/** Saves a manual edit of the letter body - the next export will use this text
 * instead of the AI-generated paragraphs. */
export const updateApplicationCoverLetterBody = (applicationId: string, text: string) =>
  client.patch(`/applications/${applicationId}/cover-letter/body`, { text })

/** Enqueues an AI refine (Celery), polls until it settles, then returns the fresh
 * letter as JSON - no PDF involved, straight into the editor. */
export const generateApplicationCoverLetterJson = async (
  applicationId: string,
  suggestion = "",
): Promise<CoverLetterJson> => {
  await refineCoverLetter(applicationId, suggestion)
  const result = await pollApplication(applicationId)
  if (result.cover_letter_status !== "completed") {
    throw new Error("La génération a échoué - réessayez.")
  }
  const body = await getApplicationCoverLetterBody(applicationId)
  if (!body) throw new Error("La lettre générée est introuvable.")
  return body
}

/** Saves the current editor text and renders it to PDF via WeasyPrint - the only
 * point in this flow where a PDF is ever produced. */
export const exportApplicationCoverLetterPdf = async (
  applicationId: string,
  text: string,
): Promise<Blob> => {
  const res = await fetch(`/api/applications/${applicationId}/cover-letter/export`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  })
  if (!res.ok) {
    const detail = await res.json().then((d) => d?.detail).catch(() => res.statusText)
    throw new Error(`HTTP ${res.status} - ${detail}`)
  }
  return res.blob()
}
