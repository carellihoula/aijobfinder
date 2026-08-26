import { useState, type ReactNode } from "react"
import { Mail, X } from "lucide-react"
import { useSidebar } from "../lib/sidebarContext"
import { useUser } from "../lib/userContext"
import { resendVerification } from "../api/auth"
import Sidebar from "./Sidebar"
import PageHeader from "./PageHeader"

interface Props {
  children: ReactNode
  title?: string
  subtitle?: string
  actions?: ReactNode
}

function VerificationBanner() {
  const [dismissed, setDismissed] = useState(false)
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  if (dismissed) return null

  const handleResend = async () => {
    setLoading(true)
    try {
      await resendVerification()
      setSent(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 bg-amber-500/10 border-b border-amber-500/20 text-[13px]">
      <Mail className="h-4 w-4 text-amber-500 shrink-0" />
      <span className="text-amber-700 dark:text-amber-300 flex-1">
        Votre adresse e-mail n'est pas encore vérifiée.{" "}
        {sent ? (
          <span className="font-medium">E-mail envoyé, vérifiez votre boîte.</span>
        ) : (
          <button
            onClick={handleResend}
            disabled={loading}
            className="font-medium underline underline-offset-2 hover:no-underline disabled:opacity-50"
          >
            {loading ? "Envoi…" : "Renvoyer l'e-mail"}
          </button>
        )}
      </span>
      <button onClick={() => setDismissed(true)} className="text-amber-500 hover:text-amber-400 transition">
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

export default function Layout({ children, title, subtitle, actions }: Props) {
  const { collapsed } = useSidebar()
  const { me } = useUser()
  const sidebarW = collapsed ? 56 : 220

  return (
    <div className="flex min-h-screen bg-[rgb(var(--bg))]">
      <Sidebar />
      <div
        className="flex-1 min-w-0 flex flex-col"
        style={{
          marginLeft: sidebarW,
          transition: "margin-left 0.22s cubic-bezier(0.4,0,0.2,1)",
        }}
      >
        {me && !me.is_verified && <VerificationBanner />}
        {title && <PageHeader title={title} subtitle={subtitle} actions={actions} />}
        <main className="flex-1">{children}</main>
      </div>
    </div>
  )
}