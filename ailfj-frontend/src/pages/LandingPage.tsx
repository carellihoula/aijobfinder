import { type ElementType } from "react"
import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import {
  ArrowRight, UploadCloud, Sparkles, Mail, Briefcase,
  Search, Wand2, SendHorizonal, CheckCircle2, Check, Link2, Files,
} from "lucide-react"
import ThemeToggle from "../components/ThemeToggle"

function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <span
      className="rounded-lg bg-accent flex items-center justify-center shrink-0"
      style={{ height: size, width: size }}
    >
      <svg width={size / 2} height={size / 2} viewBox="0 0 16 16" fill="none">
        <path d="M8 1L14 4.5V11.5L8 15L2 11.5V4.5L8 1Z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
        <circle cx="8" cy="8" r="2" fill="#fff" />
      </svg>
    </span>
  )
}

// ── Merged pipeline diagram ──────────────────────────────────────────────────
// Two entry points (CV upload / link-or-paste) converge through IA processing
// into a single output: the CV + a cover letter adapted to the offer.

const CANVAS_W = 720
const CANVAS_H = 250

interface DiagramNodeData {
  icon: ElementType
  label: string
  x: number
  y: number
  r: number
  tone: "default" | "accent" | "output"
}

const DIAGRAM_NODES: DiagramNodeData[] = [
  { icon: UploadCloud, label: "CV déposé",              x: 70,  y: 55,  r: 28, tone: "default" },
  { icon: Search,      label: "Matching & scoring IA",  x: 250, y: 55,  r: 28, tone: "default" },
  { icon: Link2,       label: "Lien ou texte collé",    x: 70,  y: 185, r: 28, tone: "default" },
  { icon: Wand2,       label: "Extraction IA",          x: 250, y: 185, r: 28, tone: "default" },
  { icon: Sparkles,    label: "Rédaction IA",            x: 450, y: 120, r: 30, tone: "accent" },
  { icon: Files,       label: "CV + lettre adaptée à l'offre", x: 630, y: 120, r: 34, tone: "output" },
]

const DIAGRAM_PATHS = [
  { id: "p-a1", d: "M98,55 H222",                          begin: 0,   dotR: 3 },
  { id: "p-b1", d: "M98,185 H222",                         begin: 0,   dotR: 3 },
  { id: "p-a2", d: "M278,55 C 350,55 350,120 420,120",     begin: 0.8, dotR: 3 },
  { id: "p-b2", d: "M278,185 C 350,185 350,120 420,120",   begin: 0.8, dotR: 3 },
  { id: "p-c",  d: "M480,120 H596",                        begin: 1.6, dotR: 3.5 },
]

function DiagramNode({ node, index }: { node: DiagramNodeData; index: number }) {
  const { icon: Icon, label, x, y, r, tone } = node
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.4, delay: index * 0.12, ease: "easeOut" }}
      className="absolute flex flex-col items-center gap-2 text-center"
      style={{ left: x, top: y - r, width: 128, marginLeft: -64 }}
    >
      <div
        className={`rounded-2xl flex items-center justify-center border ${
          tone === "output" ? "bg-accent border-accent" : tone === "accent" ? "bg-accent-soft border-accent/30" : "bg-accent-soft border-line/10"
        }`}
        style={{ height: r * 2, width: r * 2 }}
      >
        <Icon className={tone === "output" ? "h-6 w-6 text-white" : "h-5 w-5 text-accent"} />
      </div>
      <span className={`text-[11px] leading-tight ${tone === "output" ? "font-semibold text-ink" : "font-medium text-ink"}`}>
        {label}
      </span>
    </motion.div>
  )
}

function MergedPipelineDiagram() {
  return (
    <div className="overflow-x-auto no-scrollbar">
      <div className="relative mx-auto" style={{ width: CANVAS_W, height: CANVAS_H }}>
        <svg className="absolute inset-0 pointer-events-none" width={CANVAS_W} height={CANVAS_H} viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} fill="none">
          {DIAGRAM_PATHS.map((p) => (
            <path key={p.id} id={p.id} d={p.d} className="stroke-line/15" strokeWidth={1.5} />
          ))}
          {DIAGRAM_PATHS.map((p) => (
            <circle key={`dot-${p.id}`} r={p.dotR} className="fill-accent">
              <animateMotion dur="1.4s" repeatCount="indefinite" begin={`${p.begin}s`}>
                <mpath href={`#${p.id}`} />
              </animateMotion>
            </circle>
          ))}
        </svg>

        {DIAGRAM_NODES.map((node, i) => (
          <DiagramNode key={node.label} node={node} index={i} />
        ))}
      </div>
    </div>
  )
}

const FEATURES = [
  {
    icon: Sparkles,
    title: "Scoring expliqué",
    text: "Chaque offre reçoit un score de compatibilité avec le détail des compétences qui correspondent, et celles qui manquent.",
  },
  {
    icon: Mail,
    title: "Lettres sur-mesure",
    text: "Générées à partir de votre profil et de l'offre, avec un ton ajustable et des régénérations guidées par vos instructions.",
  },
  {
    icon: Link2,
    title: "Une offre trouvée ailleurs ?",
    text: "Collez son lien ou le texte de la page : l'IA rédige une lettre de motivation sur-mesure, prête en PDF pour postuler.",
  },
  {
    icon: Briefcase,
    title: "Suivi de candidatures",
    text: "Statut, entretiens, relances : gardez une vue d'ensemble sur toutes les offres auxquelles vous avez postulé.",
  },
]

const PLANS = [
  {
    name: "Gratuit",
    price: "0€",
    period: "",
    tagline: "Pour tester le matching IA sans engagement.",
    cta: "Commencer gratuitement",
    highlighted: false,
    features: [
      "1 CV actif",
      "Jusqu'à 10 offres matchées par analyse",
      "3 lettres de motivation générées / mois",
      "Suivi de candidatures basique",
    ],
  },
  {
    name: "Pro",
    price: "9,99€",
    period: "/mois",
    tagline: "Pour candidater sans compter.",
    cta: "Passer en Pro",
    highlighted: true,
    features: [
      "CV et analyses illimités",
      "Lettres de motivation illimitées, régénérées à volonté",
      "Ajout manuel d'offres illimité (lien ou texte collé)",
      "Suivi de candidatures complet avec étapes de recrutement",
      "Support prioritaire",
    ],
  },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[rgb(var(--bg))]">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 glass">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center gap-3">
          <div className="flex items-center gap-2.5">
            <BrandMark size={32} />
            <span className="font-semibold text-ink tracking-tight">AILFJ</span>
          </div>

          <nav className="hidden md:flex items-center gap-6 ml-8">
            <a href="#comment-ca-marche" className="text-sm text-muted hover:text-ink transition">Comment ça marche</a>
            <a href="#fonctionnalites" className="text-sm text-muted hover:text-ink transition">Fonctionnalités</a>
            <a href="#tarifs" className="text-sm text-muted hover:text-ink transition">Tarifs</a>
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Link to="/login" className="btn-ghost ring-focus rounded-lg px-3.5 py-2 text-sm hidden sm:inline-flex items-center">
              Se connecter
            </Link>
            <Link to="/register" className="btn-accent ring-focus rounded-lg px-3.5 py-2 text-sm font-medium inline-flex items-center gap-1.5">
              Créer un compte <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-16 md:pt-28 md:pb-24 text-center">
        <div className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 mb-6 bg-accent-soft border border-line/10">
          <Sparkles className="h-3 w-3 text-accent" />
          <span className="text-xs font-medium text-accent">Recherche d'emploi assistée par IA</span>
        </div>

        <h1 className="text-4xl md:text-6xl font-semibold tracking-tight text-ink leading-[1.1] max-w-3xl mx-auto">
          Trouvez votre prochain poste,{" "}
          <span className="text-accent">sans y passer vos soirées</span>
        </h1>

        <p className="mt-5 text-base md:text-lg text-muted max-w-xl mx-auto leading-relaxed">
          Déposez votre CV, laissez l'IA analyser des centaines d'offres et générer vos lettres
          de motivation. Vous choisissez, vous postulez.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link to="/register" className="btn-accent ring-focus rounded-lg px-6 py-3 text-sm font-medium inline-flex items-center gap-2 w-full sm:w-auto justify-center">
            Commencer gratuitement <ArrowRight className="h-4 w-4" />
          </Link>
          <Link to="/login" className="btn-ghost ring-focus rounded-lg px-6 py-3 text-sm w-full sm:w-auto text-center">
            J'ai déjà un compte
          </Link>
        </div>

        <div className="mt-10 flex items-center justify-center gap-x-6 gap-y-2 flex-wrap text-xs font-mono text-subtle">
          <span className="inline-flex items-center gap-1.5"><span className="h-1 w-1 rounded-full bg-accent" /> Analyse sémantique du CV</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-1 w-1 rounded-full bg-accent" /> Matching multi-sources</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-1 w-1 rounded-full bg-accent" /> Lien ou texte collé → lettre en PDF</span>
        </div>
      </section>

      {/* ── How it works ───────────────────────────────────────────────── */}
      <section id="comment-ca-marche" className="max-w-6xl mx-auto px-6 py-16 md:py-20">
        <div className="text-center mb-10">
          <h2 className="text-2xl md:text-3xl font-semibold text-ink tracking-tight">Comment ça marche</h2>
          <p className="mt-2 text-sm text-muted max-w-md mx-auto">
            CV déposé ou offre trouvée ailleurs, les deux chemins mènent à la même sortie :
            votre CV et une lettre de motivation adaptée à l'offre, prêts à télécharger.
          </p>
        </div>

        <MergedPipelineDiagram />
      </section>

      {/* ── Features ───────────────────────────────────────────────────── */}
      <section id="fonctionnalites" className="max-w-6xl mx-auto px-6 py-16 md:py-20">
        <div className="text-center mb-12">
          <h2 className="text-2xl md:text-3xl font-semibold text-ink tracking-tight">Tout ce qu'il faut pour candidater vite</h2>
          <p className="mt-2 text-sm text-muted">Pas seulement une liste d'offres : un copilote pour chaque candidature.</p>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          {FEATURES.map((f) => (
            <div key={f.title} className="card rounded-2xl p-6 flex gap-4">
              <div className="h-10 w-10 rounded-xl bg-accent-soft flex items-center justify-center shrink-0">
                <f.icon className="h-5 w-5 text-accent" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-ink mb-1">{f.title}</h3>
                <p className="text-sm text-muted leading-relaxed">{f.text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Pricing ────────────────────────────────────────────────────── */}
      <section id="tarifs" className="max-w-6xl mx-auto px-6 py-16 md:py-20">
        <div className="text-center mb-12">
          <h2 className="text-2xl md:text-3xl font-semibold text-ink tracking-tight">Tarifs</h2>
          <p className="mt-2 text-sm text-muted">Simple, sans engagement. Changez ou annulez à tout moment.</p>
        </div>

        <div className="grid sm:grid-cols-2 gap-5 max-w-3xl mx-auto">
          {PLANS.map((plan) => (
            <div
              key={plan.name}
              className={`rounded-2xl p-7 flex flex-col ${plan.highlighted ? "card relative ring-2 ring-accent" : "card"}`}
            >
              {plan.highlighted && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-accent text-white text-[11px] font-medium px-3 py-1 rounded-full">
                  Populaire
                </span>
              )}
              <h3 className="text-sm font-semibold text-ink">{plan.name}</h3>
              <p className="text-xs text-muted mt-1">{plan.tagline}</p>
              <div className="mt-5 flex items-baseline gap-1">
                <span className="text-3xl font-semibold text-ink tracking-tight">{plan.price}</span>
                {plan.period && <span className="text-sm text-muted">{plan.period}</span>}
              </div>

              <ul className="mt-6 space-y-2.5 flex-1">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-muted">
                    <Check className="h-4 w-4 text-accent shrink-0 mt-0.5" />
                    {f}
                  </li>
                ))}
              </ul>

              <Link
                to="/register"
                className={`ring-focus rounded-lg py-2.5 text-sm font-medium text-center mt-7 ${plan.highlighted ? "btn-accent" : "btn-ghost"}`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ────────────────────────────────────────────────────────── */}
      <section className="max-w-6xl mx-auto px-6 py-16 md:py-20">
        <div className="card rounded-2xl px-8 py-14 md:py-16 text-center relative overflow-hidden">
          <div
            className="absolute inset-0 opacity-60 pointer-events-none"
            style={{ background: "radial-gradient(600px circle at 50% 0%, rgb(var(--accent) / 0.10), transparent 60%)" }}
          />
          <div className="relative">
            <SendHorizonal className="h-8 w-8 text-accent mx-auto mb-4" />
            <h2 className="text-2xl md:text-3xl font-semibold text-ink tracking-tight">Prêt à passer à la vitesse supérieure ?</h2>
            <p className="mt-2 text-sm text-muted max-w-md mx-auto">
              Créez votre compte, déposez votre CV, et laissez l'IA préparer vos prochaines candidatures.
            </p>
            <Link to="/register" className="btn-accent ring-focus rounded-lg px-6 py-3 text-sm font-medium inline-flex items-center gap-2 mt-6">
              <CheckCircle2 className="h-4 w-4" /> Créer mon compte gratuitement
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className="border-t border-line/10">
        <div className="max-w-6xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <BrandMark size={24} />
            <span className="text-sm font-medium text-ink">AILFJ</span>
          </div>
          <p className="text-xs text-subtle">© {new Date().getFullYear()} AILFJ · Recherche d'emploi assistée par IA</p>
        </div>
      </footer>
    </div>
  )
}