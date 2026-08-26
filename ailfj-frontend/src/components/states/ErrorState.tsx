import { CloudOff, RotateCw } from "lucide-react"

interface ErrorStateProps {
  message?: string
  detail?: string
  onRetry?: () => void
  onBack?: () => void
}

export default function ErrorState({
  message = "Le service de matching n'a pas répondu. Réessayez, aucun crédit n'a été débité.",
  detail,
  onRetry,
  onBack,
}: ErrorStateProps) {
  return (
    <div className="mx-auto max-w-md px-4 sm:px-6 py-16 sm:py-24 text-center animate-fade-up">
      <div className="relative mx-auto w-fit mb-6">
        <div className="absolute inset-0 blur-2xl rounded-full bg-rose-500/20" />
        <div className="relative grid place-items-center h-16 w-16 rounded-2xl card">
          <CloudOff className="h-8 w-8 text-rose-500" />
        </div>
      </div>
      <h2 className="text-xl font-semibold text-ink">L'analyse a échoué</h2>
      <p className="mt-2 text-sm text-muted text-balance">{message}</p>
      {detail && (
        <div className="mt-5 text-left card rounded-xl p-3 font-mono text-[11px] text-rose-500/80 bg-rose-500/[.04] border-rose-500/15">
          {detail}
        </div>
      )}
      <div className="mt-6 flex items-center justify-center gap-2.5">
        <button onClick={onRetry}
          className="btn-accent ring-focus text-sm font-medium text-white rounded-xl px-4 py-2.5 flex items-center gap-2 transition">
          <RotateCw className="h-4 w-4" /> Réessayer
        </button>
        <button onClick={onBack}
          className="text-sm font-medium text-muted rounded-xl px-4 py-2.5 border border-line/10 hover:bg-line/5 transition">
          Retour
        </button>
      </div>
    </div>
  )
}
