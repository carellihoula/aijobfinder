import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react"
import { getMe } from "../api/auth"
import type { MeResponse } from "../api/auth"
import { setStorageUid } from "./storageKey"

interface UserCtx {
  me: MeResponse | null
  isAdmin: boolean
  loading: boolean
  refetchMe: () => Promise<void>
}

const Ctx = createContext<UserCtx>({
  me: null, isAdmin: false, loading: true, refetchMe: async () => {},
})

export function UserProvider({ children }: { children: ReactNode }) {
  const [me, setMe]           = useState<MeResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchMe = useCallback(async () => {
    try {
      const r = await getMe()
      setMe(r.data)
      setStorageUid(r.data.id)
    } catch {
      setMe(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchMe() }, [fetchMe])

  return (
    <Ctx.Provider value={{ me, isAdmin: me?.is_admin ?? false, loading, refetchMe: fetchMe }}>
      {children}
    </Ctx.Provider>
  )
}

export const useUser = () => useContext(Ctx)
