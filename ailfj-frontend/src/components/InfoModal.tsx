import { X } from "lucide-react"
import type { ReactNode } from "react"

interface Props {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  icon?: ReactNode
}

export default function InfoModal({ open, onClose, title, children, icon }: Props) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className="relative w-full max-w-sm rounded-2xl p-6 animate-fade-up"
        style={{
          background: "rgb(var(--card))",
          border: "1px solid rgb(var(--line) / var(--line-a))",
          boxShadow: "var(--shadow)",
        }}
      >
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 h-7 w-7 rounded-lg flex items-center justify-center text-subtle hover:text-ink hover:bg-line/8 transition"
        >
          <X className="h-4 w-4" />
        </button>

        {icon && <div className="mb-4">{icon}</div>}

        <h2 className="text-[15px] font-semibold text-ink mb-2">{title}</h2>
        <div className="text-[13px] text-muted leading-relaxed">{children}</div>

        <button
          onClick={onClose}
          className="btn-accent ring-focus mt-5 w-full rounded-lg py-2 text-sm font-medium"
        >
          Compris
        </button>
      </div>
    </div>
  )
}
