'use client'

import { Globe } from 'lucide-react'

interface SourceIngestionActions {
  onConfluenceImport: () => void
}

/** Inline button for the homepage empty state */
export function SourceIngestionButtons({ onConfluenceImport }: SourceIngestionActions) {
  return (
    <div className="flex items-center gap-3 mt-2">
      <button
        onClick={onConfluenceImport}
        className="inline-flex items-center gap-2 rounded-full bg-foreground text-background px-5 py-2 text-sm font-medium hover:opacity-90 transition-opacity cursor-pointer"
      >
        <Globe className="size-3.5 opacity-60" />
        Import from Confluence
      </button>
    </div>
  )
}
