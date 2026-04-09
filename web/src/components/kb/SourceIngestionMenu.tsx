'use client'

import { Upload, Globe } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

interface SourceIngestionActions {
  onUpload: () => void
  onConfluenceImport: () => void
}

/** Inline buttons for the homepage empty state */
export function SourceIngestionButtons({ onUpload, onConfluenceImport }: SourceIngestionActions) {
  return (
    <div className="flex items-center gap-3 mt-2">
      <button
        onClick={onUpload}
        className="inline-flex items-center gap-2 rounded-full bg-foreground text-background px-5 py-2 text-sm font-medium hover:opacity-90 transition-opacity cursor-pointer"
      >
        <Upload className="size-3.5 opacity-60" />
        Upload Sources
      </button>
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

/** Dropdown variant for the sidebar upload button */
export function SourceIngestionDropdown({
  onUpload, onConfluenceImport, children,
}: SourceIngestionActions & { children: React.ReactNode }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {children}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" side="bottom">
        <DropdownMenuItem onClick={onUpload}>
          <Upload className="size-3.5 mr-2" />
          Upload Files
        </DropdownMenuItem>
        <DropdownMenuItem onClick={onConfluenceImport}>
          <Globe className="size-3.5 mr-2" />
          Import from Confluence
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
