import { useQuery } from "@tanstack/react-query"
import { getLatestAnalysis, getCvData } from "../api/analysis"
import { getPreferences } from "../api/users"
import { listUsers, listAllAnalyses } from "../api/admin"
import { listApplications } from "../api/applications"
import { listNotifications, getUnreadCount as fetchUnreadCount } from "../api/notifications"

// ─── Query keys (single source of truth for invalidation) ────────────────────
export const QK = {
  latestAnalysis: ["latestAnalysis"] as const,
  cvData:         ["cvData"]         as const,
  preferences:    ["preferences"]    as const,
  adminUsers:     ["admin", "users"] as const,
  adminAnalyses:  ["admin", "analyses"] as const,
  applications:   ["applications"]   as const,
  notifications:      ["notifications"]        as const,
  notificationsUnread:["notifications", "unread"] as const,
} as const

// ─── Hooks ───────────────────────────────────────────────────────────────────

export function useLatestAnalysis() {
  return useQuery({
    queryKey: QK.latestAnalysis,
    queryFn:  () => getLatestAnalysis().then(r => r.data),
    // don't retry 404s - they are expected (no analysis yet)
    retry: (_, err: any) => err?.response?.status !== 404,
  })
}

export function useCvData() {
  return useQuery({
    queryKey:  QK.cvData,
    queryFn:   () => getCvData().then(r => r.data),
    staleTime: 5 * 60 * 1000,
    retry:     (_, err: any) => err?.response?.status !== 404,
  })
}

export function usePreferences() {
  return useQuery({
    queryKey:  QK.preferences,
    queryFn:   () => getPreferences().then(r => r.data),
    staleTime: 5 * 60 * 1000,
  })
}

export function useAdminUsers() {
  return useQuery({
    queryKey:  QK.adminUsers,
    queryFn:   () => listUsers().then(r => r.data),
    staleTime: 60 * 1000,
  })
}

export function useAdminAnalyses() {
  return useQuery({
    queryKey:  QK.adminAnalyses,
    queryFn:   () => listAllAnalyses().then(r => r.data),
    staleTime: 60 * 1000,
  })
}

export function useApplications() {
  return useQuery({
    queryKey:  QK.applications,
    queryFn:   () => listApplications().then(r => r.data),
    staleTime: 30 * 1000,
  })
}

export function useNotifications() {
  return useQuery({
    queryKey: QK.notifications,
    queryFn:  () => listNotifications().then(r => r.data),
  })
}

export function useUnreadNotificationsCount() {
  return useQuery({
    queryKey:       QK.notificationsUnread,
    queryFn:        () => fetchUnreadCount().then(r => r.data.count),
    refetchInterval: 60 * 1000,
  })
}
