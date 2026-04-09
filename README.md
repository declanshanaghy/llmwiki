# Cribl Knowledge Wiki

[![License](https://img.shields.io/badge/license-Apache%202.0-green)](https://opensource.org/licenses/Apache-2.0)

An internal knowledge platform that imports documentation from Confluence, Google Docs, and Bitbucket repositories, then uses Claude to compile and maintain a structured wiki across Cribl's engineering systems. Cross-correlates design docs, source code, and operational knowledge to build a graph of how things connect — so you can understand how things work and predict what will happen when things change.

1. **Import sources** — Pull pages from Confluence (with full hierarchy), Google Docs, Bitbucket repos, PDFs, and internal notes. Auto-sync keeps everything current.
2. **Connect Claude** — via MCP. It reads your sources, writes wiki pages, maintains cross-references and citations across Cribl systems.
3. **The wiki compounds** — every source imported and every question asked makes it richer. Knowledge about Cribl.Cloud, Stream, Edge, Search, and Lake is built up, not re-derived.
4. **The knowledge graph grows** — connections between Confluence design docs, Google Docs specs, and Bitbucket source trees are tracked. Claude maps which code implements which design, which services depend on which, and what breaks when something changes.

### Source Integrations

| Source | Status | Details |
|--------|--------|---------|
| **Confluence** | Live | Import pages with hierarchy, embedded images, draw.io diagrams. Auto-sync detects updates. Bulk import children or entire spaces. |
| **Bitbucket** | Planned | Track multiple repos. Index source trees, READMEs, config files, and code structure. Cross-reference with design docs to map implementation to intent. |
| **Google Docs** | Planned | Import shared docs with formatting and embedded content. |
| **PDFs** | Live | OCR via Mistral, page-level chunking, inline images. |
| **Office docs** | Live | Word, PowerPoint, Excel — converted via LibreOffice. |
| **Manual notes** | Live | Markdown/text notes created directly in the UI. |

### Three Layers

| Layer | Description |
|-------|-------------|
| **Raw Sources** | Confluence pages, Google Docs, Bitbucket repos, PDFs, notes. Your immutable source of truth. The LLM reads them but never modifies them. |
| **The Wiki** | LLM-generated markdown pages — summaries, entity pages, cross-references, mermaid diagrams, tables. The LLM owns this layer. You read it; the LLM writes it. |
| **The Tools** | Search, read, and write. Claude connects via MCP and orchestrates the rest. |

### Core Operations

The platform ships an **MCP server** that Claude connects to directly. Once connected, Claude has tools to search, read, write, and delete across the entire knowledge vault. All operations below happen through Claude — you talk to it, it maintains the wiki.

**Ingest** — Import a Confluence page (or an entire space), connect a Bitbucket repo, or pull in a Google Doc. Claude reads it, writes a summary, updates entity and concept pages across the wiki, and flags anything that contradicts existing knowledge. A single source might touch 10-15 wiki pages.

**Query** — Ask complex questions against the compiled wiki. "What services does Maestro depend on?" "Which repos implement the billing pipeline?" Knowledge is already synthesized — not re-derived from raw chunks each time. Good answers get filed back as new pages, so your explorations compound.

**Lint** — Run health checks. Find inconsistent data, stale claims, orphan pages, missing cross-references. Detect when source code has diverged from design docs. Claude suggests new questions to investigate and new sources to look for.

**Impact Analysis** — Trace connections across the knowledge graph. "If we change the auth middleware, what Confluence design docs describe the current behavior, which repos implement it, and what downstream services are affected?" The graph of connections between documents and source trees makes this possible.

### Wiki Output

Every wiki page Claude generates is a browsable, richly linked artifact — not a wall of text.

**Source-linked citations** — Wiki pages cite specific source lines, not just filenames. A claim about how auth tokens are validated links directly to the relevant function in `cribl-cloud/src/auth/middleware.ts:47`. ERD pages link to the implementing files across `cribl-cloud`, `cribl`, and `public-api`.

**Diagrams at every layer** — Claude generates Mermaid diagrams for every level of detail:

| Diagram Type | What It Shows | Example |
|-------------|---------------|---------|
| Architecture | System-level service boundaries, data flow between Cribl.Cloud, Stream, Edge, Search, Lake | How requests flow from Maestro through Zeus to single-tenant infrastructure |
| Component | Internal structure of a service — modules, classes, key interfaces | Auth middleware components within Maestro, how they compose |
| Package/Deployment | What gets deployed where — containers, Lambda functions, AWS services, regions | Which services run in the control plane vs. data plane, per-tenant isolation boundaries |
| Sequence | Runtime interactions between services for a specific operation | Token refresh flow across Auth0, Maestro, Zeus, and the tenant workspace |
| Entity Relationship | Data models with field-level detail, cross-repo | How the billing data model in `cribl-cloud` maps to Metronome exports and the FinOps storage schema |
| Dependency | Which repos/packages/services depend on which | What breaks if you change `public-api` response shapes |

Every diagram is generated from source — not hand-drawn. When the source changes, Claude regenerates the diagram on the next sync.

**Browsable hierarchy** — The wiki renders as an expandable tree. Start at the architecture overview, drill into a service, then into a component, then into a specific function's behavior. Every level links to the source docs and source code that back it.

### Cribl Systems Coverage

The wiki compiles knowledge across Cribl's product and infrastructure landscape:

- **Cribl.Cloud** — architecture, multi-tenant services, single-tenant infrastructure
- **Stream / Edge / Search / Lake** — product-specific design docs, ERDs, trade-offs
- **Platform Services** — Zeus, Maestro, Auth0, billing, monitoring, CI/CD, Typhon
- **Engineering Practices** — development patterns, security, FedRAMP, cloud considerations
- **Key Repositories** — `cribl-cloud`, `cribl`, `public-api` — source trees indexed and cross-referenced with design docs

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Next.js   │────▶│   FastAPI   │────▶│  Supabase   │
│   Frontend  │     │   Backend   │     │  (Postgres) │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  MCP Server │◀──── Claude
                    └─────────────┘
```

| Component | Stack | Responsibilities |
|-----------|-------|------------------|
| **Web** (`web/`) | Next.js 16, React 19, Tailwind, Radix UI | Dashboard, PDF/HTML viewer, wiki renderer, onboarding |
| **API** (`api/`) | FastAPI, asyncpg, aioboto3 | Auth, uploads (TUS), Confluence import, document worker, OCR (Mistral) |
| **Converter** (`converter/`) | FastAPI, LibreOffice | Isolated office-to-PDF conversion (non-root, zero AWS creds) |
| **MCP** (`mcp/`) | MCP SDK, Supabase OAuth | Tools for Claude: `guide`, `search`, `read`, `write`, `delete` |
| **Database** | Supabase (Postgres + RLS + PGroonga) | Documents, chunks, knowledge bases, users |
| **Storage** | S3-compatible | Raw uploads, tagged HTML, extracted images |

---

## MCP Tools

Once connected, Claude has full access to your knowledge vault:

| Tool | Description |
|------|-------------|
| `guide` | Explains how the wiki works and lists available knowledge bases |
| `search` | Browse files (`list`) or keyword search with PGroonga ranking (`search`) |
| `read` | Read documents — PDFs with page ranges, inline images, glob batch reads |
| `write` | Create wiki pages, edit with `str_replace`, append. SVG and CSV asset support |
| `delete` | Archive documents by path or glob pattern |

---

### Self-Hosting

#### Prerequisites

- Python 3.11+
- Node.js 20+
- A [Supabase](https://supabase.com) project (or local Docker setup)
- An S3-compatible bucket (needed for file uploads)

#### 1. Database

```bash
psql $DATABASE_URL -f supabase/migrations/001_initial.sql
```

Or use local Docker: `docker compose up -d`

#### 2. API

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env  # edit with your credentials
uvicorn main:app --reload --port 8000
```

#### 3. MCP Server

```bash
cd mcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8080
```

#### 4. Web

```bash
cd web
npm install
cp .env.example .env.local
npm run dev
```

#### 5. Connect Claude

1. Open **Settings** > **Connectors** in Claude
2. Add a custom connector pointing to `http://localhost:8080/mcp`
3. Sign in with your Supabase account when prompted

#### Environment Variables

**API** (`api/.env`)

```
DATABASE_URL=postgresql://...
SUPABASE_URL=https://your-ref.supabase.co
SUPABASE_JWT_SECRET=          # optional, for legacy HS256 projects
MISTRAL_API_KEY=              # for PDF OCR
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET=your-bucket
APP_URL=http://localhost:3000
CONVERTER_URL=               # optional, URL of isolated converter service
```

**Web** (`web/.env.local`)

```
NEXT_PUBLIC_SUPABASE_URL=https://your-ref.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_MCP_URL=http://localhost:8080/mcp
```

---

## Why This Works

Engineering knowledge at Cribl lives across hundreds of Confluence pages, Google Docs, ERDs, design briefs, and dozens of Bitbucket repositories. No single person can hold the full picture. The tedious part is not the reading or the thinking — it's the bookkeeping. Updating cross-references, keeping summaries current, noting when new data contradicts old claims, tracking which code implements which design, maintaining consistency across systems that span Cloud, Stream, Edge, Search, and Lake.

Engineers abandon personal wikis because the maintenance burden grows faster than the value. LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass. The wiki stays maintained because the cost of maintenance drops to near zero.

Import from Confluence, connect your Bitbucket repos, let Claude compile the wiki, ask it questions. The knowledge graph that emerges — connections between design docs, source trees, and operational knowledge — is the real product. The human's job is to curate sources, direct the analysis, and think about what it all means. The LLM's job is everything else.

## License

Apache 2.0
