import { Link, useLocation } from "react-router-dom"
import {
  LayoutDashboard, Bookmark, BarChart2, Bell,
  Settings, LogOut, PanelLeftClose,
  Sparkles, Files, Shield, Briefcase,
} from "lucide-react"
import { useSidebar } from "../lib/sidebarContext"
import { useUser } from "../lib/userContext"
import { useAuth } from "../hooks/useAuth"
import { useUnreadNotificationsCount } from "../lib/queries"
import { getSavedJobs, SAVED_JOBS_EVENT } from "../lib/savedJobs"
import { useState, useEffect } from "react"
import UserAvatar from "./UserAvatar"

interface NavItem {
  to: string
  icon: React.ElementType
  label: string
  badge?: number
}

interface Section {
  label: string
  items: NavItem[]
}

function useBadges() {
  const { data: unread = 0 } = useUnreadNotificationsCount()
  const [saved, setSaved] = useState(0)
  useEffect(() => {
    setSaved(getSavedJobs().length)

    const onSavedChange = () => setSaved(getSavedJobs().length)
    window.addEventListener(SAVED_JOBS_EVENT, onSavedChange)
    return () => window.removeEventListener(SAVED_JOBS_EVENT, onSavedChange)
  }, [])
  return { unread, saved }
}

export default function Sidebar() {
  const { pathname } = useLocation()
  const { collapsed, toggle } = useSidebar()
  const { unread, saved } = useBadges()
  const { me, isAdmin } = useUser()
  const { logout } = useAuth()

  const SECTIONS: Section[] = [
    {
      label: "Analyse",
      items: [
        { to: "/dashboard",    icon: LayoutDashboard, label: "Tableau de bord" },
        { to: "/documents",    icon: Files,           label: "Documents" },
        { to: "/saved",        icon: Bookmark,        label: "Offres sauvegardées", badge: saved || undefined },
        { to: "/applications", icon: Briefcase,       label: "Mes candidatures" },
        { to: "/stats",        icon: BarChart2,       label: "Statistiques" },
      ],
    },
    {
      label: "Compte",
      items: [
        { to: "/notifications", icon: Bell,     label: "Notifications", badge: unread || undefined },
        { to: "/settings",      icon: Settings, label: "Paramètres" },
        ...(isAdmin ? [{ to: "/admin", icon: Shield, label: "Administration" }] : []),
      ],
    },
  ]

  const w = collapsed ? 56 : 220

  return (
    <aside
      className="fixed top-0 left-0 bottom-0 z-30 flex flex-col overflow-hidden"
      style={{
        width: w,
        transition: "width 0.22s cubic-bezier(0.4,0,0.2,1)",
        background: "rgb(var(--card))",
        borderRight: "1px solid rgb(var(--line) / var(--line-a))",
      }}
    >
      {/* Brand row */}
      <div
        className="h-14 flex items-center shrink-0"
        style={{
          padding: "0 12px",
          borderBottom: "1px solid rgb(var(--line) / var(--line-a))",
        }}
      >
        {collapsed ? (
          /* Collapsed: logo seul, cliquable pour ouvrir */
          <button
            onClick={toggle}
            title="Agrandir la sidebar"
            className="h-7 w-7 rounded-lg bg-accent flex items-center justify-center mx-auto hover:opacity-85 transition"
          >
            <Sparkles className="h-3.5 w-3.5 text-white" />
          </button>
        ) : (
          /* Expanded: logo + nom + bouton collapse */
          <>
            <span className="h-7 w-7 rounded-lg bg-accent flex items-center justify-center shrink-0">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </span>
            <span className="flex-1 font-semibold text-sm text-ink whitespace-nowrap ml-2.5">AILFJ</span>
            <button
              onClick={toggle}
              title="Réduire la sidebar"
              className="h-6 w-6 rounded-md flex items-center justify-center text-subtle hover:bg-line/8 hover:text-ink transition shrink-0"
            >
              <PanelLeftClose className="h-3.5 w-3.5" />
            </button>
          </>
        )}
      </div>

      {/* Nav sections */}
      <nav className="flex-1 overflow-y-auto no-scrollbar py-3 px-2 space-y-4">
        {SECTIONS.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <p className="px-2 mb-1 text-[10px] font-semibold text-subtle uppercase tracking-widest select-none">
                {section.label}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map(({ to, icon: Icon, label, badge }) => {
                const active = pathname === to
                return (
                  <Link
                    key={to}
                    to={to}
                    title={collapsed ? label : undefined}
                    onClick={() => { if (collapsed) toggle() }}
                    className={`relative flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-colors ${
                      active
                        ? "bg-accent/10 text-accent font-medium"
                        : "text-muted hover:bg-line/5 hover:text-ink"
                    }`}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full bg-accent" />
                    )}
                    <Icon className="h-4 w-4 shrink-0" />
                    {!collapsed && (
                      <span className="flex-1 whitespace-nowrap overflow-hidden">{label}</span>
                    )}
                    {badge !== undefined && badge > 0 && (
                      <span className={`flex items-center justify-center rounded-full text-[10px] font-semibold ${
                        collapsed
                          ? "absolute top-1 right-1 h-3.5 w-3.5 bg-accent text-white"
                          : "h-4 min-w-4 px-1 bg-accent/15 text-accent shrink-0"
                      }`}>
                        {badge}
                      </span>
                    )}
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom - profile + logout */}
      <div
        className="px-2 py-2 space-y-0.5 shrink-0"
        style={{ borderTop: "1px solid rgb(var(--line) / var(--line-a))" }}
      >
        <Link
          to="/profile"
          title={collapsed ? "Mon profil" : undefined}
          onClick={() => { if (collapsed) toggle() }}
          className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-colors ${
            pathname === "/profile"
              ? "bg-accent/10 text-accent font-medium"
              : "text-muted hover:bg-line/5 hover:text-ink"
          }`}
        >
          <UserAvatar
            avatarKey={me?.avatar_key}
            avatarUrl={me?.avatar_url}
            name={me?.full_name || me?.email}
            size={6}
          />
          {!collapsed && <span className="whitespace-nowrap">Mon profil</span>}
        </Link>
        <button
          onClick={logout}
          title={collapsed ? "Déconnexion" : undefined}
          className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] text-muted hover:bg-line/5 hover:text-ink transition-colors"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!collapsed && <span className="whitespace-nowrap">Déconnexion</span>}
        </button>
      </div>
    </aside>
  )
}