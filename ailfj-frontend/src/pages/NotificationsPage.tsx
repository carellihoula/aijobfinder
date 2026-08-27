import { useNavigate } from "react-router-dom"
import { useQueryClient } from "@tanstack/react-query"
import { Bell, Sparkles, Zap, BarChart2, AlertTriangle, FileX, CheckCheck, X } from "lucide-react"
import Layout from "../components/Layout"
import { QK, useNotifications } from "../lib/queries"
import { markAllNotificationsRead, markNotificationRead, deleteNotification } from "../api/notifications"
import type { Notification, NotificationType } from "../api/notifications"

const ICONS: Record<NotificationType, React.ElementType> = {
  analysis_completed:  BarChart2,
  analysis_failed:     AlertTriangle,
  cover_letter_ready:  Sparkles,
  cover_letter_failed: FileX,
  new_matches:         Zap,
}

const COLORS: Record<NotificationType, string> = {
  analysis_completed:  "text-violet-400 bg-violet-400/10",
  analysis_failed:     "text-orange-400 bg-orange-400/10",
  cover_letter_ready:  "text-accent bg-accent/10",
  cover_letter_failed: "text-red-400 bg-red-400/10",
  new_matches:         "text-blue-400 bg-blue-400/10",
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 1) return "À l'instant"
  if (minutes < 60) return `Il y a ${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `Il y a ${hours} h`
  const days = Math.floor(hours / 24)
  if (days === 1) return "Hier"
  if (days < 7) return `Il y a ${days} j`
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })
}

export default function NotificationsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: notifs = [], isLoading } = useNotifications()

  const unreadCount = notifs.filter((n) => !n.read).length

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: QK.notifications })
    queryClient.invalidateQueries({ queryKey: QK.notificationsUnread })
  }

  const handleClick = (notif: Notification) => {
    if (!notif.read) markNotificationRead(notif.id).then(invalidate)
    if (notif.link) navigate(notif.link)
  }

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    deleteNotification(id).then(invalidate)
  }

  return (
    <Layout
      title="Notifications"
      subtitle={unreadCount > 0 ? `${unreadCount} non lue${unreadCount > 1 ? "s" : ""}` : "Tout lu"}
      actions={
        unreadCount > 0 ? (
          <button
            onClick={() => markAllNotificationsRead().then(invalidate)}
            className="btn-ghost ring-focus inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs"
          >
            <CheckCheck className="h-3.5 w-3.5" /> Tout marquer lu
          </button>
        ) : undefined
      }
    >
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <span className="h-5 w-5 border-2 border-line/20 border-t-accent rounded-full animate-spin" />
          </div>
        ) : notifs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="h-14 w-14 rounded-2xl bg-line/5 bd flex items-center justify-center">
              <Bell className="h-7 w-7 text-subtle" />
            </div>
            <p className="text-sm text-muted">Aucune notification</p>
          </div>
        ) : (
          <div className="space-y-2">
            {notifs.map((notif) => {
              const Icon = ICONS[notif.type]
              const color = COLORS[notif.type]

              return (
                <div
                  key={notif.id}
                  onClick={() => handleClick(notif)}
                  className={`group w-full text-left card rounded-xl p-4 flex gap-3.5 transition cursor-pointer hover:border-line/20 ${!notif.read ? "border-accent/20" : ""}`}
                >
                  <div className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p className={`text-sm font-medium ${notif.read ? "text-muted" : "text-ink"}`}>
                        {notif.title}
                      </p>
                      <span className="text-[10px] text-subtle shrink-0 mt-0.5">{timeAgo(notif.created_at)}</span>
                    </div>
                    <p className="text-xs text-muted mt-0.5 leading-relaxed">{notif.body}</p>
                  </div>
                  {!notif.read && (
                    <div className="h-2 w-2 rounded-full bg-accent shrink-0 mt-2" />
                  )}
                  <button
                    onClick={(e) => handleDelete(e, notif.id)}
                    title="Supprimer"
                    className="h-6 w-6 rounded-md flex items-center justify-center text-subtle hover:text-red-500 hover:bg-red-500/10 transition shrink-0 opacity-0 group-hover:opacity-100"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Layout>
  )
}
