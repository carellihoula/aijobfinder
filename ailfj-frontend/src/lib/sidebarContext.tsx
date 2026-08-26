import { createContext, useContext, useState, type ReactNode } from "react"

interface SidebarCtx {
  collapsed: boolean
  toggle: () => void
}

const Ctx = createContext<SidebarCtx>({ collapsed: false, toggle: () => {} })

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("sb_col") === "1"
  )

  const toggle = () =>
    setCollapsed((v) => {
      const next = !v
      localStorage.setItem("sb_col", next ? "1" : "0")
      return next
    })

  return <Ctx.Provider value={{ collapsed, toggle }}>{children}</Ctx.Provider>
}

export const useSidebar = () => useContext(Ctx)