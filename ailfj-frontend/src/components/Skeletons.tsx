export function MatchSkeleton() {
  return (
    <div className="card rounded-2xl p-4">
      <div className="flex gap-3">
        <div className="h-11 w-11 skel rounded-xl" />
        <div className="flex-1 space-y-2">
          <div className="h-3.5 w-1/2 skel rounded" />
          <div className="h-3 w-1/3 skel rounded" />
          <div className="h-2 w-full skel rounded-full mt-3" />
        </div>
      </div>
    </div>
  )
}

export function MatchSkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      <div className="h-3 w-28 skel rounded" />
      <div className="space-y-3">
        {Array.from({ length: count }).map((_, i) => (
          <MatchSkeleton key={i} />
        ))}
      </div>
    </div>
  )
}
