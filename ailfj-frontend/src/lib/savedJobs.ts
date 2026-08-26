import type { DesignJobMatch } from "./designTypes"
import { scopedKey } from "./storageKey"

export interface SavedJob extends DesignJobMatch {
  analysisId: string
  savedAt: string
}

const key = () => scopedKey("saved_jobs")

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
}

export function unsaveJob(jobId: string) {
  const jobs = getSavedJobs().filter((j) => j.id !== jobId)
  localStorage.setItem(key(), JSON.stringify(jobs))
}

export function toggleSaveJob(job: DesignJobMatch, analysisId: string): boolean {
  if (isJobSaved(job.id)) {
    unsaveJob(job.id)
    return false
  }
  saveJob(job, analysisId)
  return true
}