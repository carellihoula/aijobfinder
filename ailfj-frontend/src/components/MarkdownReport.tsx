import { Fragment } from "react"
import type { ReactNode } from "react"

function inline(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g
  let last = 0
  let m: RegExpExecArray | null
  let key = 0
  while ((m = re.exec(text))) {
    if (m.index > last) nodes.push(text.slice(last, m.index))
    const tok = m[0]
    if (tok.startsWith("**")) {
      nodes.push(<strong key={key++} className="text-ink font-semibold">{tok.slice(2, -2)}</strong>)
    } else {
      nodes.push(<em key={key++} className="text-muted">{tok.slice(1, -1)}</em>)
    }
    last = m.index + tok.length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

export default function MarkdownReport({ markdown }: { markdown: string }) {
  const lines = markdown.split("\n")
  const blocks: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  let key = 0

  const flush = () => {
    if (!list) return
    const Tag = list.ordered ? "ol" : "ul"
    blocks.push(
      <Tag key={key++} className="space-y-1.5 my-1 ml-0.5">
        {list.items.map((it, i) => (
          <li key={i} className="flex gap-2.5 text-[13px]">
            {list!.ordered ? (
              <span className="font-mono text-[11px] shrink-0 mt-0.5 text-accent">{String(i + 1).padStart(2, "0")}</span>
            ) : (
              <span className="mt-1.5 h-1 w-1 rounded-full shrink-0 bg-accent" />
            )}
            <span>{inline(it)}</span>
          </li>
        ))}
      </Tag>
    )
    list = null
  }

  for (const raw of lines) {
    const ln = raw.trimEnd()
    if (/^##\s/.test(ln)) {
      flush()
      blocks.push(<h4 key={key++} className="text-xs font-semibold uppercase tracking-wider mt-5 first:mt-0 mb-2 text-accent">{inline(ln.slice(3))}</h4>)
    } else if (/^>\s/.test(ln)) {
      flush()
      blocks.push(
        <blockquote key={key++} className="mt-4 rounded-xl p-3.5 text-[13px] leading-relaxed"
          style={{ background: "rgb(var(--accent) / 0.08)", borderLeft: "2px solid rgb(var(--accent))" }}>
          {inline(ln.slice(2))}
        </blockquote>
      )
    } else if (/^-\s/.test(ln)) {
      if (!list || list.ordered) { flush(); list = { ordered: false, items: [] } }
      list.items.push(ln.slice(2))
    } else if (/^\d+\.\s/.test(ln)) {
      if (!list || !list.ordered) { flush(); list = { ordered: true, items: [] } }
      list.items.push(ln.slice(ln.indexOf(".") + 2))
    } else if (ln.trim() === "") {
      flush()
    } else {
      flush()
      blocks.push(<p key={key++} className="text-[13px] leading-relaxed my-1.5">{inline(ln)}</p>)
    }
  }
  flush()

  return <div className="text-sm leading-relaxed text-muted">{blocks.map((b, i) => <Fragment key={i}>{b}</Fragment>)}</div>
}
