import { Children, cloneElement, isValidElement } from "react"
import type { ReactElement } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { Components } from "react-markdown"

// react-markdown v10 no longer passes `ordered`/`index` down to `li` overrides,
// so we thread them through manually via cloneElement from the parent ol/ul.
function withListMeta(children: React.ReactNode, ordered: boolean) {
  return Children.map(children, (child, i) =>
    isValidElement(child)
      ? cloneElement(child as ReactElement<any>, { "data-ordered": ordered, "data-index": i })
      : child
  )
}

const components: Components = {
  h1: ({ children }) => (
    <h4 className="text-xs font-semibold uppercase tracking-wider mt-5 first:mt-0 mb-2 text-accent">{children}</h4>
  ),
  h2: ({ children }) => (
    <h4 className="text-xs font-semibold uppercase tracking-wider mt-5 first:mt-0 mb-2 text-accent">{children}</h4>
  ),
  h3: ({ children }) => (
    <h4 className="text-xs font-semibold uppercase tracking-wider mt-5 first:mt-0 mb-2 text-accent">{children}</h4>
  ),
  blockquote: ({ children }) => (
    <blockquote
      className="mt-4 rounded-xl p-3.5 text-[13px] leading-relaxed"
      style={{ background: "rgb(var(--accent) / 0.08)", borderLeft: "2px solid rgb(var(--accent))" }}
    >
      {children}
    </blockquote>
  ),
  ul: ({ children }) => <ul className="space-y-1.5 my-1 ml-0.5">{withListMeta(children, false)}</ul>,
  ol: ({ children }) => <ol className="space-y-1.5 my-1 ml-0.5">{withListMeta(children, true)}</ol>,
  li: ({ children, ...props }) => {
    const ordered = (props as any)["data-ordered"] as boolean | undefined
    const index = (props as any)["data-index"] as number | undefined
    return (
      <li className="flex gap-2.5 text-[13px]">
        {ordered ? (
          <span className="font-mono text-[11px] shrink-0 mt-0.5 text-accent">
            {String((index ?? 0) + 1).padStart(2, "0")}
          </span>
        ) : (
          <span className="mt-1.5 h-1 w-1 rounded-full shrink-0 bg-accent" />
        )}
        <span>{children}</span>
      </li>
    )
  },
  p: ({ children }) => <p className="text-[13px] leading-relaxed my-1.5">{children}</p>,
  strong: ({ children }) => <strong className="text-ink font-semibold">{children}</strong>,
  em: ({ children }) => <em className="text-muted">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent underline underline-offset-2 hover:no-underline"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-line/10 px-1 py-0.5 font-mono text-[12px]">{children}</code>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="w-full text-[13px] border-collapse">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="text-left font-semibold text-ink px-2 py-1.5 border-b bd">{children}</th>,
  td: ({ children }) => <td className="px-2 py-1.5 border-b bd align-top">{children}</td>,
}

export default function MarkdownReport({ markdown }: { markdown: string }) {
  return (
    <div className="text-sm leading-relaxed text-muted">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  )
}