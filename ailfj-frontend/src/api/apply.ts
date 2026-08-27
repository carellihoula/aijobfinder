import { client } from './client'

export interface ApplyResponse {
  job: {
    title: string
    company: string
    location: string
    url: string | null
  }
  cover_letter: {
    subject: string
    tone: string
    highlighted_skills: string[]
    key_selling_point: string
    paragraphs: { purpose: string; text: string }[]
  }
  documents: {
    cv: { available: boolean; download_url: string | null }
    cover_letter: { available: boolean; download_url: string }
  }
}

export const applyToJob = (analysisId: string, jobIndex: number) =>
  client.post<ApplyResponse>(`/analysis/${analysisId}/apply?job_index=${jobIndex}`)

export interface CoverLetterResult {
  blob: Blob
  content: Record<string, unknown> | null  // CoverLetterContent dict from X-Cover-Letter-Content header
}

/** Returns the raw Blob + the structured content JSON (for refinement caching). */
export const fetchCoverLetterPdfBlob = async (
  analysisId: string,
  jobIndex: number,
  suggestion = "",
  previousContent: Record<string, unknown> | null = null,
): Promise<CoverLetterResult> => {
  const params = new URLSearchParams({ job_index: String(jobIndex) })

  const res = await fetch(`/api/analysis/${analysisId}/cover-letter?${params}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ suggestion: suggestion.trim(), previous_content: previousContent }),
  })
  if (!res.ok) {
    const detail = await res.json().then((d) => d?.detail).catch(() => res.statusText)
    throw new Error(`HTTP ${res.status} - ${detail}`)
  }

  const blob = await res.blob()

  // Backend returns CoverLetterContent as base64 JSON in this header
  let content: Record<string, unknown> | null = null
  const contentB64 = res.headers.get("X-Cover-Letter-Content")
  if (contentB64) {
    try { content = JSON.parse(atob(contentB64)) } catch { /* ignore */ }
  }

  return { blob, content }
}

/** Returns a blob URL - use with an <iframe> or <a download> */
export const fetchCoverLetterPdf = async (
  analysisId: string,
  jobIndex: number,
  suggestion = "",
): Promise<string> => {
  const { blob } = await fetchCoverLetterPdfBlob(analysisId, jobIndex, suggestion)
  return URL.createObjectURL(blob)
}

/** Returns a blob URL - streamed through the backend (no S3 CORS issues) */
export const fetchCvPdf = async (analysisId: string): Promise<string> => {
  const res = await fetch(`/api/analysis/${analysisId}/cv`, {
    credentials: "include",
  })
  if (!res.ok) {
    const detail = await res.json().then((d) => d?.detail).catch(() => res.statusText)
    throw new Error(`HTTP ${res.status} - ${detail}`)
  }
  const blob = await res.blob()
  if (!blob.size) throw new Error("Received empty PDF")
  return URL.createObjectURL(blob)
}
