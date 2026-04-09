'use client'

import * as React from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { apiFetch } from '@/lib/api'
import { useUserStore } from '@/stores'
import { toast } from 'sonner'
import { Loader2 } from 'lucide-react'

interface ConfluenceImportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  kbId: string
  initialUrl?: string
  initialIncludeChildren?: boolean
}

export function ConfluenceImportDialog({ open, onOpenChange, kbId, initialUrl, initialIncludeChildren }: ConfluenceImportDialogProps) {
  const [url, setUrl] = React.useState('')
  const [includeChildren, setIncludeChildren] = React.useState(false)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')
  const token = useUserStore((s) => s.accessToken)

  // Sync initial values when dialog opens
  React.useEffect(() => {
    if (open) {
      setUrl(initialUrl ?? '')
      setIncludeChildren(initialIncludeChildren ?? false)
      setError('')
    }
  }, [open, initialUrl, initialIncludeChildren])

  async function handleImport(e: React.FormEvent) {
    e.preventDefault()
    if (!url.trim() || !token) return

    setLoading(true)
    setError('')

    try {
      await apiFetch(`/v1/knowledge-bases/${kbId}/import/confluence`, token, {
        method: 'POST',
        body: JSON.stringify({ url: url.trim(), include_children: includeChildren }),
      })

      if (includeChildren) {
        const result = await apiFetch<{ queued: number; skipped: number }>(
          `/v1/knowledge-bases/${kbId}/import/confluence/children`, token, {
            method: 'POST',
            body: JSON.stringify({ url: url.trim() }),
          },
        )
        toast.success(`Importing page + ${result.queued} child page${result.queued !== 1 ? 's' : ''}...`)
      } else {
        toast.success('Importing from Confluence...')
      }

      setUrl('')
      setIncludeChildren(false)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initialUrl ? 'Re-import from Confluence' : 'Import from Confluence'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleImport} className="space-y-4">
          <div>
            <label htmlFor="confluence-url" className="block text-sm font-medium mb-1.5">
              Confluence page URL
            </label>
            <input
              id="confluence-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://mycompany.atlassian.net/wiki/spaces/TEAM/pages/12345/..."
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
              required
            />
            <p className="text-xs text-muted-foreground mt-1.5">
              Paste the full URL of a Confluence page. Images and diagrams will be included.
            </p>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={includeChildren}
              onChange={(e) => setIncludeChildren(e.target.checked)}
              className="rounded border-input"
            />
            <span className="text-sm">Import child pages</span>
          </label>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <button
              type="submit"
              disabled={loading || !url.trim()}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="size-3.5 animate-spin" />
                  Importing...
                </span>
              ) : (
                initialUrl ? 'Re-import' : 'Import'
              )}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
