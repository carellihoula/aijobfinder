import { Sun, Moon } from "lucide-react"
import { useTheme } from "../lib/useTheme"

export default function ThemeToggle() {
  const { theme, toggle } = useTheme()
  return (
    <button
      onClick={toggle}
      aria-label="Basculer le thème"
      className="grid place-items-center h-9 w-9 rounded-xl btn-ghost text-muted hover:text-ink transition"
    >
      {theme === "dark" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
    </button>
  )
}
