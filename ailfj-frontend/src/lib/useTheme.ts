import { useEffect, useState } from "react"

type Theme = "light" | "dark"

function getInitial(): Theme {
  if (typeof window === "undefined") return "dark"
  const saved = localStorage.getItem("ajf_theme") as Theme | null
  if (saved) return saved
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitial)

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark")
    localStorage.setItem("ajf_theme", theme)
  }, [theme])

  return {
    theme,
    toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    setTheme,
  }
}
