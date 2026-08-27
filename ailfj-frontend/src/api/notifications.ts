import { client } from "./client"

export type NotificationType =
  | "analysis_completed"
  | "analysis_failed"
  | "cover_letter_ready"
  | "cover_letter_failed"
  | "new_matches"

export interface Notification {
  id: string
  type: NotificationType
  title: string
  body: string
  link: string | null
  read: boolean
  created_at: string
}

export const listNotifications = () =>
  client.get<Notification[]>("/notifications")

export const getUnreadCount = () =>
  client.get<{ count: number }>("/notifications/unread-count")

export const markNotificationRead = (id: string) =>
  client.post(`/notifications/${id}/read`)

export const markAllNotificationsRead = () =>
  client.post<{ marked: number }>("/notifications/read-all")

export const deleteNotification = (id: string) =>
  client.delete(`/notifications/${id}`)