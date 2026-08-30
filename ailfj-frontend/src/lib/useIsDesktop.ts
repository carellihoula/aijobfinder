import { useEffect, useState } from "react"

// Matches the `lg` breakpoint the sidebar switches on (see Sidebar.tsx /
// index.css) - keep this in sync with that value if it ever changes.
const DESKTOP_QUERY = "(min-width: 1024px)"

/** True at/above the `lg` breakpoint. Used to decide whether the sidebar
 * behaves as a fixed rail (desktop) or an off-canvas drawer (mobile/tablet). */
export function useIsDesktop(): boolean {
  const [isDesktop, setIsDesktop] = useState(
    () => window.matchMedia(DESKTOP_QUERY).matches
  )

  useEffect(() => {
    const mql = window.matchMedia(DESKTOP_QUERY)
    const onChange = () => setIsDesktop(mql.matches)
    mql.addEventListener("change", onChange)
    return () => mql.removeEventListener("change", onChange)
  }, [])

  return isDesktop
}
