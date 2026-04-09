'use client'

import React, { useEffect, useRef, useState } from 'react'
import { ExternalLink, Loader2 } from 'lucide-react'
import { useTheme } from 'next-themes'
import { cn } from '@/lib/utils'

type Props = {
  fileUrl: string
  sourceUrl?: string | null
  highlightIds?: string[]
  className?: string
}

const EMPTY_IDS: string[] = []

function buildHighlightCss(ids: string[]): string {
  if (!ids.length) return ''

  const selectors = ids.map((id) => `#${CSS.escape(id)}`).join(',\n')

  return `
<style>
${selectors} {
  background-color: rgba(255, 235, 59, 0.55) !important;
  outline: 1.5px solid rgba(255, 180, 0, 0.7);
  border-radius: 2px;
}
</style>`
}

const DARK_STYLE = `
<style data-theme="dark">
  html, body {
    background-color: hsl(20 14% 4%) !important;
    color: hsl(40 10% 90%) !important;
    color-scheme: dark;
  }
  a { color: hsl(210 80% 65%); }
  table, th, td { border-color: hsl(20 10% 20%) !important; }
  th { background-color: hsl(20 12% 10%) !important; }
  blockquote { border-color: hsl(20 10% 25%) !important; background-color: hsl(20 12% 8%) !important; }
  pre, code { background-color: hsl(20 12% 8%) !important; color: hsl(40 10% 85%) !important; }
  img { opacity: 0.9; }
</style>`

export default function HtmlViewer({ fileUrl, sourceUrl, highlightIds = EMPTY_IDS, className }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rawHtml, setRawHtml] = useState<string | null>(null)
  const { theme } = useTheme()

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setRawHtml(null)

    fetch(fileUrl)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load: ${res.status}`)
        return res.text()
      })
      .then((html) => {
        if (!cancelled) setRawHtml(html)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [fileUrl, highlightIds])

  // Build srcdoc from raw HTML + highlight CSS + theme styles
  const srcdoc = React.useMemo(() => {
    if (!rawHtml) return ''
    const themeStyle = theme === 'dark' ? DARK_STYLE : ''
    return rawHtml + buildHighlightCss(highlightIds) + themeStyle
  }, [rawHtml, highlightIds, theme])

  const handleIframeLoad = () => {
    setLoading(false)
    if (highlightIds.length && iframeRef.current?.contentDocument) {
      const el = iframeRef.current.contentDocument.getElementById(highlightIds[0])
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <p className="text-sm text-muted-foreground">Failed to load document</p>
        {sourceUrl && (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <ExternalLink className="size-3.5" />
            Open original page
          </a>
        )}
      </div>
    )
  }

  return (
    <iframe
      ref={iframeRef}
      srcDoc={srcdoc}
      sandbox="allow-same-origin"
      className={cn('w-full h-full border-0', theme === 'dark' ? 'bg-[hsl(20,14%,4%)]' : 'bg-white', className)}
      title="Document viewer"
      onLoad={handleIframeLoad}
    />
  )
}
