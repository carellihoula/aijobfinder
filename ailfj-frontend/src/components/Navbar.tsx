import { Link, useLocation } from "react-router-dom"
import { Settings, LogOut } from "lucide-react"
import { useAuth } from "../hooks/useAuth"

export default function Navbar() {
  const { pathname } = useLocation()
  const { logout } = useAuth()

  const navLink = (to: string, label: string) => (
    <Link
      to={to}
      className={`text-sm px-3 py-1.5 rounded-md transition ${
        pathname === to
          ? "text-ink font-medium"
          : "text-muted hover:text-ink"
      }`}
    >
      {label}
    </Link>
  )

  return (
    <header className="sticky top-0 z-40 glass">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 h-14 flex items-center gap-4">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-2 mr-4">
          <span className="h-7 w-7 rounded-lg bg-accent flex items-center justify-center shrink-0">
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
              <path d="M8 1L14 4.5V11.5L8 15L2 11.5V4.5L8 1Z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round"/>
              <circle cx="8" cy="8" r="2" fill="#fff"/>
            </svg>
          </span>
          <span className="font-semibold text-sm text-ink tracking-tight hidden sm:block">AILFJ</span>
        </Link>

        {/* Nav links */}
        <nav className="flex items-center gap-1">
          {navLink("/", "Tableau de bord")}
          {navLink("/settings", "Paramètres")}
        </nav>

        {/* Actions */}
        <div className="ml-auto flex items-center gap-1">
          <Link
            to="/settings"
            aria-label="Paramètres"
            className="h-8 w-8 flex items-center justify-center rounded-md text-subtle hover:text-ink hover:bg-line/5 transition sm:hidden"
          >
            <Settings className="h-4 w-4" />
          </Link>
          <button
            onClick={logout}
            aria-label="Déconnexion"
            className="h-8 w-8 flex items-center justify-center rounded-md text-subtle hover:text-ink hover:bg-line/5 transition"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  )
}