-- Indexes for Confluence metadata queries on the documents table.
-- All Confluence-specific data lives in the JSONB `metadata` column.

-- Dedup lookups: find existing doc by Confluence page ID
CREATE INDEX IF NOT EXISTS idx_documents_confluence_page_id
  ON documents ((metadata->>'confluence_page_id'))
  WHERE metadata->>'confluence_page_id' IS NOT NULL;

-- Parent-child linking: find children of a given Confluence parent
CREATE INDEX IF NOT EXISTS idx_documents_confluence_parent_id
  ON documents ((metadata->>'confluence_parent_id'))
  WHERE metadata->>'confluence_parent_id' IS NOT NULL;
