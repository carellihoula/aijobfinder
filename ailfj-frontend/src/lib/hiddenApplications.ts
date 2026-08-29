import { scopedKey } from "./storageKey"

// Application-sourced letters can't be deleted "just the letter" server-side -
// the content lives on the Application row itself, and deleting that belongs to
// "Mes candidatures". "Supprimer" in Documents for these is a local dismissal
// only: hidden here, but reappears the moment the user reopens it from "Mes
// candidatures" (unhideApplication), and is gone for good only once the
// application itself is deleted there.
const key = () => scopedKey("hidden_applications")

export function getHiddenApplicationIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(key()) || "[]")
  } catch {
    return []
  }
}

export function hideApplication(applicationId: string) {
  const ids = getHiddenApplicationIds()
  if (ids.includes(applicationId)) return
  localStorage.setItem(key(), JSON.stringify([...ids, applicationId]))
}

export function unhideApplication(applicationId: string) {
  const ids = getHiddenApplicationIds().filter((id) => id !== applicationId)
  localStorage.setItem(key(), JSON.stringify(ids))
}