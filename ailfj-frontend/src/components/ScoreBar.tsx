import { useEffect, useState } from "react"
import { scoreTier } from "../lib/designTypes"

export default function ScoreBar({ score }: { score: number }) {
  const tier = scoreTier(score)
  const pct = Math.max(0, Math.min(100, (score / 10) * 100))
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true))
    return () => cancelAnimationFrame(id)
  }, [])

  return (
    <div className="mt-3 h-1.5 w-full rounded-full bg-white/[.06] overflow-hidden">
      <div
        className="h-full rounded-full transition-[width] duration-700 ease-out"
        style={{
          width: mounted ? `${pct}%` : 0,
          background: `linear-gradient(90deg, rgb(${tier.rgb} / .5), rgb(${tier.rgb}))`,
        }}
      />
    </div>
  )
}
