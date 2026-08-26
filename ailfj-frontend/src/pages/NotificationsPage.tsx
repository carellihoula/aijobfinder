import { useState, useEffect } from "react"
import { Bell, Sparkles, Zap, Info, BarChart2, AlertTriangle, CheckCheck } from "lucide-react"
import Layout from "../components/Layout"
import { MOCK_NOTIFS, getReadIds, markAllRead, type Notif } from "../lib/notifications"

const ICONS: Record<Notif["type"], React.ElementType> = {
  match:    Sparkles,
  cortex:   Zap,
  tip:      Info,
  analysis: BarChart2,
  alert:    AlertTriangle,
}

const COLORS: Record<Notif["type"], string> = {
  match:    "text-accent bg-accent/10",
  cortex:   "text-blue-400 bg-blue-400/10",
  tip:      "text-amber-400 bg-amber-400/10",
  analysis: "text-violet-400 bg-violet-400/10",
  alert:    "text-orange-400 bg-orange-400/10",
}

export default function NotificationsPage() {
  const [readIds, setReadIds] = useState<Set<number>>(getReadIds)

  useEffect(() => {
    markAllRead()
    setReadIds(new Set(MOCK_NOTIFS.map((n) => n.id)))
  }, [])

  const unreadCount = MOCK_NOTIFS.filter((n) => !readIds.has(n.id)).length

  return (
    <Layout
      title="Notifications"
      subtitle={unreadCount > 0 ? `${unreadCount} non lue${unreadCount > 1 ? "s" : ""}` : "Tout lu"}
      actions={
        unreadCount > 0 ? (
          <button
            onClick={() => { markAllRead(); setReadIds(new Set(MOCK_NOTIFS.map((n) => n.id))) }}
            className="btn-ghost ring-focus inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs"
          >
            <CheckCheck className="h-3.5 w-3.5" /> Tout marquer lu
          </button>
        ) : undefined
      }
    >
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
        {MOCK_NOTIFS.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-4">
            <div className="h-14 w-14 rounded-2xl bg-line/5 bd flex items-center justify-center">
              <Bell className="h-7 w-7 text-subtle" />
            </div>
            <p className="text-sm text-muted">Aucune notification</p>
          </div>
        ) : (
          <div className="space-y-2">
            {MOCK_NOTIFS.map((notif) => {
              const Icon = ICONS[notif.type]
              const color = COLORS[notif.type]
              const isRead = readIds.has(notif.id)

              return (
                <div
                  key={notif.id}
                  className={`card rounded-xl p-4 flex gap-3.5 transition ${!isRead ? "border-accent/20" : ""}`}
                >
                  <div className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <p className={`text-sm font-medium ${isRead ? "text-muted" : "text-ink"}`}>
                        {notif.title}
                      </p>
                      <span className="text-[10px] text-subtle shrink-0 mt-0.5">{notif.time}</span>
                    </div>
                    <p className="text-xs text-muted mt-0.5 leading-relaxed">{notif.body}</p>
                  </div>
                  {!isRead && (
                    <div className="h-2 w-2 rounded-full bg-accent shrink-0 mt-2" />
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Layout>
  )
}
