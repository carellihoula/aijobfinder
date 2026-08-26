import { useEffect, useState } from "react"
import { User } from "lucide-react"

interface Props {
  avatarKey: string | null | undefined
  name?: string | null
  size?: number   // tailwind size number, default 8 (= 2rem)
  className?: string
}

// Module-level blob URL cache — survives re-mounts and page navigation
// Key: avatarKey (changes when user uploads a new avatar)
export const blobCache = new Map<string, string>()

/** Clear one entry (or all) after an upload/delete so the new image is fetched. */
export function clearAvatarCache(key?: string) {
  if (key) {
    const url = blobCache.get(key)
    if (url) URL.revokeObjectURL(url)
    blobCache.delete(key)
  } else {
    blobCache.forEach((url) => URL.revokeObjectURL(url))
    blobCache.clear()
  }
}

export default function UserAvatar({ avatarKey, name, size = 8, className = "" }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(
    avatarKey ? (blobCache.get(avatarKey) ?? null) : null
  )

  useEffect(() => {
    if (!avatarKey) { setBlobUrl(null); return }

    // Cache hit — no fetch needed
    if (blobCache.has(avatarKey)) {
      setBlobUrl(blobCache.get(avatarKey)!)
      return
    }

    let active = true

    fetch(`/api/users/me/avatar`, { credentials: "include" })
      .then((res) => (res.ok ? res.blob() : Promise.reject()))
      .then((blob) => {
        if (!active) return
        const url = URL.createObjectURL(blob)
        blobCache.set(avatarKey, url)
        setBlobUrl(url)
      })
      .catch(() => { if (active) setBlobUrl(null) })

    return () => { active = false }
    // Don't revoke on cleanup — blob stays in module cache for the session
  }, [avatarKey])

  const initial = name ? name[0].toUpperCase() : null
  const sz = `h-${size} w-${size}`

  if (blobUrl) {
    return (
      <img
        src={blobUrl}
        alt="Avatar"
        className={`${sz} rounded-full object-cover shrink-0 ${className}`}
      />
    )
  }

  return (
    <div className={`${sz} rounded-full bg-accent/15 flex items-center justify-center shrink-0 ${className}`}>
      {initial
        ? <span className="text-accent font-semibold" style={{ fontSize: `${size * 0.45}px` }}>{initial}</span>
        : <User className="h-1/2 w-1/2 text-accent" />}
    </div>
  )
}
