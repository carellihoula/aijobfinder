import { Bell, Settings, User, LogOut, Menu } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useUnreadNotificationsCount } from "../lib/queries"
import { useUser } from "../lib/userContext"
import { useAuth } from "../hooks/useAuth"
import { useSidebar } from "../lib/sidebarContext"
import UserAvatar from "./UserAvatar"

interface Props {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}

export default function PageHeader({ title, subtitle, actions }: Props) {
  const navigate = useNavigate()
  const { me } = useUser()
  const { logout } = useAuth()
  const { openMobile } = useSidebar()
  const [menuOpen, setMenuOpen] = useState(false)
  const { data: unread = 0 } = useUnreadNotificationsCount()

  return (
    <header
      className="sticky top-0 z-20 h-14 flex items-center gap-3 px-4 sm:px-6 shrink-0"
      style={{
        background: "rgb(var(--bg) / 0.88)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid rgb(var(--line) / var(--line-a))",
      }}
    >
      {/* Hamburger - only below lg, sidebar is fixed and always visible above that */}
      <button
        onClick={openMobile}
        className="lg:hidden h-8 w-8 -ml-1 rounded-lg flex items-center justify-center text-muted hover:bg-line/5 hover:text-ink transition shrink-0"
        title="Ouvrir le menu"
      >
        <Menu className="h-4.5 w-4.5" />
      </button>

      {/* Title */}
      <div className="flex-1 min-w-0">
        <h1 className="text-[13px] font-semibold text-ink leading-none truncate">{title}</h1>
        {subtitle && (
          <p className="text-[11px] text-muted mt-0.5 truncate">{subtitle}</p>
        )}
      </div>

      {/* Actions slot */}
      {actions && <div className="flex items-center gap-2">{actions}</div>}

      {/* Notifications */}
      <button
        onClick={() => navigate("/notifications")}
        className="relative h-8 w-8 rounded-lg flex items-center justify-center text-muted hover:bg-line/5 hover:text-ink transition"
        title="Notifications"
      >
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-accent" />
        )}
      </button>

      {/* Avatar + dropdown */}
      <div className="relative">
        <button
          onClick={() => setMenuOpen((v) => !v)}
          className="rounded-full hover:opacity-80 transition focus:outline-none focus:ring-2 focus:ring-accent/40"
        >
          <UserAvatar avatarKey={me?.avatar_key} avatarUrl={me?.avatar_url} name={me?.full_name || me?.email} size={8} />
        </button>

        {menuOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
            <div
              className="absolute right-0 top-10 z-20 w-48 rounded-xl py-1.5 overflow-hidden"
              style={{
                background: "rgb(var(--card))",
                border: "1px solid rgb(var(--line) / var(--line-a))",
                boxShadow: "var(--shadow)",
              }}
            >
              <button
                onClick={() => { setMenuOpen(false); navigate("/profile") }}
                className="w-full flex items-center gap-2.5 px-4 py-2 text-[13px] text-muted hover:bg-line/5 hover:text-ink transition text-left"
              >
                <User className="h-3.5 w-3.5 shrink-0" /> Mon profil
              </button>
              <button
                onClick={() => { setMenuOpen(false); navigate("/settings") }}
                className="w-full flex items-center gap-2.5 px-4 py-2 text-[13px] text-muted hover:bg-line/5 hover:text-ink transition text-left"
              >
                <Settings className="h-3.5 w-3.5 shrink-0" /> Paramètres
              </button>
              <div className="my-1.5 border-t border-line/10" />
              <button
                onClick={() => { setMenuOpen(false); logout() }}
                className="w-full flex items-center gap-2.5 px-4 py-2 text-[13px] text-red-500 hover:bg-red-500/5 transition text-left"
              >
                <LogOut className="h-3.5 w-3.5 shrink-0" /> Déconnexion
              </button>
            </div>
          </>
        )}
      </div>
    </header>
  )
}
