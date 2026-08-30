// Mirrors MatchCard's real structure (logo + title/score, subtitle, tag pills,
// score bar, reason text, posted date) so the loading state doesn't visibly
// reflow into a different shape once real cards replace it.
export function MatchSkeleton() {
  return (
    <div className="card rounded-2xl p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="h-10 w-10 rounded-xl skel shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="h-3.5 w-2/3 skel rounded" />
            <div className="h-3.5 w-8 skel rounded shrink-0" />
          </div>
          <div className="h-3 w-1/2 skel rounded mt-2" />
        </div>
      </div>

      <div className="mt-2.5 flex gap-1.5">
        <div className="h-4 w-14 skel rounded-md" />
        <div className="h-4 w-14 skel rounded-md" />
        <div className="h-4 w-16 skel rounded-md" />
      </div>

      <div className="h-1.5 w-full skel rounded-full mt-2.5" />

      <div className="mt-2.5 space-y-1.5">
        <div className="h-2.5 w-full skel rounded" />
        <div className="h-2.5 w-4/5 skel rounded" />
      </div>

      <div className="h-2.5 w-20 skel rounded mt-2.5" />
    </div>
  )
}

// Same grid as the real matches (Dashboard: `grid sm:grid-cols-2 lg:grid-cols-3
// gap-3`) - a single-column stack here would reflow into columns the instant
// real data arrives, which reads as a layout jump rather than a smooth swap.
export function MatchSkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      <div className="h-3 w-28 skel rounded" />
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {Array.from({ length: count }).map((_, i) => (
          <MatchSkeleton key={i} />
        ))}
      </div>
    </div>
  )
}
