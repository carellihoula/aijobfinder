import type { DesignJobMatch } from "./designTypes"
import { scopedKey } from "./storageKey"

export interface SavedJob extends DesignJobMatch {
  analysisId: string
  savedAt: string
}

const key = () => scopedKey("saved_jobs")

// Fired whenever the saved-jobs list changes, so any mounted component (e.g. the
// sidebar badge count) can react instantly without polling or reloading —
// localStorage's own "storage" event only fires in *other* tabs, not this one.
export const SAVED_JOBS_EVENT = "savedjobs:change"

function notify() {
  window.dispatchEvent(new Event(SAVED_JOBS_EVENT))
}

export function getSavedJobs(): SavedJob[] {
  try {
    return JSON.parse(localStorage.getItem(key()) || "[]")
  } catch {
    return []
  }
}

export function isJobSaved(id: string): boolean {
  return getSavedJobs().some((j) => j.id === id)
}

export function saveJob(job: DesignJobMatch, analysisId: string) {
  const jobs = getSavedJobs().filter((j) => j.id !== job.id)
  jobs.unshift({ ...job, analysisId, savedAt: new Date().toISOString() })
  localStorage.setItem(key(), JSON.stringify(jobs.slice(0, 50)))
  notify()
}

export function unsaveJob(jobId: string) {
  const jobs = getSavedJobs().filter((j) => j.id !== jobId)
  localStorage.setItem(key(), JSON.stringify(jobs))
  notify()
}

export function toggleSaveJob(job: DesignJobMatch, analysisId: string): boolean {
  if (isJobSaved(job.id)) {
    unsaveJob(job.id)
    return false
  }
  saveJob(job, analysisId)
  return true
}