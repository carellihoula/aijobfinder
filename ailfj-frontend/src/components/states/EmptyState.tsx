import { SearchX } from "lucide-react"

export default function EmptyState({
  title = "Aucune correspondance trouvée",
  message = "Aucune offre ne dépasse le seuil de pertinence pour ces critères. Essayez d'élargir vos postes recherchés ou de mettre votre CV à jour.",
  onAction,
  actionLabel = "Modifier les critères",
}: {
  title?: string
  message?: string
  onAction?: () => void
  actionLabel?: string
}) {
  return (
    <div className="card rounded-2xl px-6 py-12 text-center">
      <div className="mx-auto grid place-items-center h-14 w-14 rounded-2xl bg-line/5 border border-line/10">
        <SearchX className="h-7 w-7 text-muted" />
      </div>
      <h3 className="mt-4 text-sm font-semibold text-ink">{title}</h3>
      <p className="mt-1.5 text-xs text-muted max-w-sm mx-auto text-balance">{message}</p>
      {onAction && (
        <button onClick={onAction}
          className="mt-5 text-sm font-medium text-ink rounded-xl px-4 py-2 border border-line/10 hover:bg-line/5 transition">
          {actionLabel}
        </button>
      )}
    </div>
  )
}
