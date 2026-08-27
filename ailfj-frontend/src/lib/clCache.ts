import { scopedKey } from "./storageKey"

const PDF_PREFIX     = "cl_pdf_"
const CONTENT_PREFIX = "cl_content_"
const MAX_ENTRIES    = 20

function key(prefix: string, analysisId: string, jobIndex: number) {
  return scopedKey(`${prefix}${analysisId}_${jobIndex}`)
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

function dataUrlToBlob(dataUrl: string): Blob {
  const [header, b64] = dataUrl.split(",")
  const mime = header.match(/:(.*?);/)?.[1] ?? "application/pdf"
  const bytes = atob(b64)
  const ab = new ArrayBuffer(bytes.length)
  const ia = new Uint8Array(ab)
  for (let i = 0; i < bytes.length; i++) ia[i] = bytes.charCodeAt(i)
  return new Blob([ab], { type: mime })
}

/** Persist a cover letter blob to localStorage. Silently ignores quota errors. */
export async function cacheCL(analysisId: string, jobIndex: number, blob: Blob) {
  try {
    const dataUrl = await blobToDataUrl(blob)
    // Evict oldest entry for THIS user only (scoped prefix)
    const userPdfPrefix = scopedKey(PDF_PREFIX)  // e.g. "abc12345:cl_pdf_"
    const existing = Object.keys(localStorage).filter((k) => k.startsWith(userPdfPrefix))
    if (existing.length >= MAX_ENTRIES) localStorage.removeItem(existing[0])
    localStorage.setItem(key(PDF_PREFIX, analysisId, jobIndex), dataUrl)
  } catch { /* quota or encoding error - skip silently */ }
}

/** Returns a fresh blob URL from the cache, or null on miss. */
export function getCachedCLUrl(analysisId: string, jobIndex: number): string | null {
  const dataUrl = localStorage.getItem(key(PDF_PREFIX, analysisId, jobIndex))
  if (!dataUrl) return null
  try {
    return URL.createObjectURL(dataUrlToBlob(dataUrl))
  } catch { return null }
}

/** Persist the structured CoverLetterContent JSON for future refinements. */
export function cacheCLContent(analysisId: string, jobIndex: number, content: object) {
  try {
    localStorage.setItem(key(CONTENT_PREFIX, analysisId, jobIndex), JSON.stringify(content))
  } catch { /* quota - skip */ }
}

/** Returns the cached CoverLetterContent dict, or null on miss. */
export function getCachedCLContent(analysisId: string, jobIndex: number): Record<string, unknown> | null {
  const raw = localStorage.getItem(key(CONTENT_PREFIX, analysisId, jobIndex))
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

/** Remove both the PDF blob and the content JSON for this entry. */
export function clearCachedCL(analysisId: string, jobIndex: number) {
  localStorage.removeItem(key(PDF_PREFIX, analysisId, jobIndex))
  localStorage.removeItem(key(CONTENT_PREFIX, analysisId, jobIndex))
}

/** True if a cover letter PDF is cached for this analysisId + jobIndex. */
export function hasCachedCL(analysisId: string, jobIndex: number): boolean {
  return localStorage.getItem(key(PDF_PREFIX, analysisId, jobIndex)) !== null
}
