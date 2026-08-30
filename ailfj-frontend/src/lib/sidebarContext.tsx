import { createContext, useContext, useState, type ReactNode } from "react"

interface SidebarCtx {
  collapsed: boolean
  toggle: () => void
  // Below lg (1024px) the sidebar is an off-canvas drawer instead of a fixed
  // rail - `collapsed` (persisted, desktop-only preference) doesn't apply to
  // it, this is purely "is the drawer open right now", reset on every mount.
  mobileOpen: boolean
  openMobile: () => void
  closeMobile: () => void
  toggleMobile: () => void
}

const Ctx = createContext<SidebarCtx>({
  collapsed: false, toggle: () => {},
  mobileOpen: false, openMobile: () => {}, closeMobile: () => {}, toggleMobile: () => {},
})

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("sb_col") === "1"
  )
  const [mobileOpen, setMobileOpen] = useState(false)

  const toggle = () =>
    setCollapsed((v) => {
      const next = !v
      localStorage.setItem("sb_col", next ? "1" : "0")
      return next
    })

  const openMobile = () => setMobileOpen(true)
  const closeMobile = () => setMobileOpen(false)
  const toggleMobile = () => setMobileOpen((v) => !v)

  return (
    <Ctx.Provider value={{ collapsed, toggle, mobileOpen, openMobile, closeMobile, toggleMobile }}>
      {children}
    </Ctx.Provider>
  )
}

export const useSidebar = () => useContext(Ctx)