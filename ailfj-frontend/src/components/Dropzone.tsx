import { useRef, useState, useCallback } from "react"
import { UploadCloud, FileText, Check, X } from "lucide-react"

interface DropzoneProps {
  file: File | null
  onFile: (file: File | null) => void
  accept?: string
  maxSizeMB?: number
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`
  return `${(bytes / 1024 / 1024).toFixed(1)} Mo`
}

export default function Dropzone({ file, onFile, accept = "application/pdf", maxSizeMB = 10 }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handle = useCallback((f: File | undefined) => {
    if (!f) return
    if (accept && !f.type.includes("pdf")) return setError("PDF uniquement.")
    if (f.size > maxSizeMB * 1024 * 1024) return setError(`${maxSizeMB} Mo max.`)
    setError(null)
    onFile(f)
  }, [accept, maxSizeMB, onFile])

  return (
    <div>
      <input ref={inputRef} type="file" accept={accept} className="sr-only"
        onChange={(e) => handle(e.target.files?.[0])} />
      <div
        role="button" tabIndex={0}
        onClick={() => !file && inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && !file && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); handle(e.dataTransfer.files?.[0]) }}
        className={[
          "group relative card rounded-2xl border-dashed p-8 sm:p-10 text-center overflow-hidden transition-all duration-200",
          file ? "border-line/10" : "cursor-pointer border-white/15",
          over ? "scale-[1.005] border-accent bg-accent/[.06]" : "",
        ].join(" ")}
        style={over ? { borderColor: "rgb(var(--accent))" } : undefined}
      >
        {!file ? (
          <>
            <div className={`mx-auto grid place-items-center h-14 w-14 rounded-2xl bg-well border border-line/10 transition-transform ${over ? "-translate-y-1 scale-105" : ""}`}>
              <UploadCloud className="h-7 w-7 text-accent" />
            </div>
            <p className="mt-4 text-sm text-ink">
              <span className="font-semibold text-accent">Cliquez pour parcourir</span> ou glissez-déposez
            </p>
            <p className="mt-1 text-xs text-subtle">PDF uniquement · {maxSizeMB} Mo max</p>
          </>
        ) : (
          <div className="flex items-center gap-3 text-left bg-well border border-line/10 rounded-xl p-3 animate-pop-in">
            <span className="grid place-items-center h-11 w-11 rounded-lg bg-rose-500/10 border border-rose-500/20 shrink-0">
              <FileText className="h-5 w-5 text-rose-500" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink truncate">{file.name}</p>
              <p className="text-xs text-subtle">{formatSize(file.size)} · prêt à analyser</p>
            </div>
            <span className="grid place-items-center h-6 w-6 rounded-full bg-emerald-500/15 border border-emerald-500/30 shrink-0">
              <Check className="h-3.5 w-3.5 text-emerald-500" />
            </span>
            <button onClick={(e) => { e.stopPropagation(); onFile(null) }}
              aria-label="Retirer le fichier"
              className="grid place-items-center h-8 w-8 rounded-lg hover:bg-line/5 text-subtle hover:text-ink transition shrink-0">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
      {error && <p className="mt-2 text-xs text-rose-500">{error}</p>}
    </div>
  )
}
