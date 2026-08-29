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
  body: string | null  // editable letter body (salutation..sign-off) from X-Cover-Letter-Body header
}

/** Base64 -> UTF-8 string (atob alone mangles accented characters). */
function base64ToUtf8(b64: string): string {
  return new TextDecoder().decode(Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)))
}

function parseCoverLetterHeaders(res: Response): { content: Record<string, unknown> | null; body: string | null } {
  let content: Record<string, unknown> | null = null
  const contentB64 = res.headers.get("X-Cover-Letter-Content")
  if (contentB64) {
    try { content = JSON.parse(atob(contentB64)) } catch { /* ignore */ }
  }

  let body: string | null = null
  const bodyB64 = res.headers.get("X-Cover-Letter-Body")
  if (bodyB64) {
    try { body = base64ToUtf8(bodyB64) } catch { /* ignore */ }
  }

  return { content, body }
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
  return { blob, ...parseCoverLetterHeaders(res) }
}

/** Fetches a previously generated cover letter without regenerating it. Returns
 * null on 404 (nothing generated yet for this offer) - the durable server-side
 * counterpart to the localStorage cache, so a cover letter survives a cleared
 * cache or a different device. */
export const fetchExistingCoverLetterPdfBlob = async (
  analysisId: string,
  jobIndex: number,
): Promise<CoverLetterResult | null> => {
  const params = new URLSearchParams({ job_index: String(jobIndex) })
  const res = await fetch(`/api/analysis/${analysisId}/cover-letter?${params}`, {
    credentials: "include",
  })
  if (res.status === 404) return null
  if (!res.ok) {
    const detail = await res.json().then((d) => d?.detail).catch(() => res.statusText)
    throw new Error(`HTTP ${res.status} - ${detail}`)
  }

  const blob = await res.blob()
  return { blob, ...parseCoverLetterHeaders(res) }
}

/** Saves a manual edit of the letter body - the next PDF render (download, or a
 * fresh GET) will use this text instead of the AI-generated paragraphs. */
export const updateCoverLetterBody = (analysisId: string, jobIndex: number, text: string) =>
  client.patch(`/analysis/${analysisId}/cover-letter/body?job_index=${jobIndex}`, { text })

// ── Editor-first flow: content lives in SimpleEditor, PDF only exists on export ──

export interface CoverLetterJson {
  content: Record<string, unknown>
  body: string
}

/** Fetches the stored letter as JSON - no PDF rendering. Returns null on 404. */
export const getCoverLetterBody = async (
  analysisId: string,
  jobIndex: number,
): Promise<CoverLetterJson | null> => {
  try {
    const { data } = await client.get<CoverLetterJson>(
      `/analysis/${analysisId}/cover-letter/body?job_index=${jobIndex}`,
    )
    return data
  } catch (e: unknown) {
    const status = (e as { response?: { status?: number } })?.response?.status
    if (status === 404) return null
    throw e
  }
}

export interface CoverLetterSummary {
  job_index: number
  company: string
  title: string
}

/** Lists every offer in this analysis that already has a generated cover letter -
 * used to rebuild the Documents page list across refreshes without regenerating. */
export const listCoverLetters = (analysisId: string): Promise<CoverLetterSummary[]> =>
  client.get<CoverLetterSummary[]>(`/analysis/${analysisId}/cover-letters`).then((r) => r.data)

/** Permanently deletes a generated cover letter for this offer. */
export const deleteCoverLetter = (analysisId: string, jobIndex: number) =>
  client.delete(`/analysis/${analysisId}/cover-letter?job_index=${jobIndex}`)

/** Generates (or AI-refines) the letter - returns JSON straight into the editor, no PDF. */
export const generateCoverLetterJson = (
  analysisId: string,
  jobIndex: number,
  suggestion = "",
  previousContent: Record<string, unknown> | null = null,
): Promise<CoverLetterJson> =>
  client
    .post<CoverLetterJson>(`/analysis/${analysisId}/cover-letter/generate?job_index=${jobIndex}`, {
      suggestion: suggestion.trim(),
      previous_content: previousContent,
    })
    .then((r) => r.data)

/** Saves the current editor text and renders it to PDF via WeasyPrint - the only
 * point in this flow where a PDF is ever produced. */
export const exportCoverLetterPdf = async (
  analysisId: string,
  jobIndex: number,
  text: string,
): Promise<Blob> => {
  const res = await fetch(`/api/analysis/${analysisId}/cover-letter/export?job_index=${jobIndex}`, {
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
