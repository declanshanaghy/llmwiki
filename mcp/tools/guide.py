from mcp.server.fastmcp import FastMCP, Context

from config import settings
from db import scoped_query
from .helpers import get_user_id

GUIDE_TEXT = """# LLM Wiki — How It Works

You are connected to an **LLM Wiki** — a personal knowledge workspace where you compile and maintain a structured wiki from raw source documents. Sources are the immutable truth; the wiki is your compiled, cross-referenced interpretation of them.

## Architecture

1. **Raw Sources** (path: `/`) — uploaded documents (PDFs, Confluence HTML, notes, images, spreadsheets). Source of truth. Read-only. Never modify.
2. **Compiled Wiki** (path: `/wiki/`) — markdown pages YOU create and maintain. You own this layer entirely.
3. **Tools** — `guide`, `search`, `read`, `write`, `delete` — your interface to both layers.

---

## Wiki Structure

These categories are the backbone of every wiki. They are not suggestions.

### Overview (`/wiki/overview.md`) — THE HUB PAGE
Always exists. The front page. Must contain:
- Summary of scope
- **Source count** and **page count** (update on every ingest)
- **Key Findings** — top insights across all sources
- **Architecture diagram** — a Mermaid graph showing the system with branded component colors
- **Recent Updates** — last 5-10 actions

Update the Overview after EVERY ingest or major edit. If you only update one page, it should be this one.

### Concepts (`/wiki/concepts/`) — ABSTRACT IDEAS
Theoretical frameworks, methodologies, principles, cross-cutting themes.

Each concept page must: define it, explain why it matters, cite sources, include at least one diagram, and cross-reference related pages.

### Entities (`/wiki/entities/`) — CONCRETE THINGS
Services, products, technologies, people, organizations — anything you can point to.

Each entity page must: describe what it is, include an architecture diagram, list key attributes in a table, cite sources, and cross-reference related pages.

### Log (`/wiki/log.md`) — CHRONOLOGICAL RECORD
Always exists. Append-only. Records every ingest, major edit, and lint pass. Never delete entries.

Format — each entry starts with a parseable header:
```
## [YYYY-MM-DD] ingest | Source Title
- Created concept page: [Page Title](concepts/page.md)
- Updated entity page: [Page Title](entities/page.md)
- Updated overview with new findings
- Key takeaway: one sentence summary
```

### Additional Pages
You can create pages outside of concepts/ and entities/:
- `/wiki/comparisons/x-vs-y.md` — deep comparisons
- `/wiki/timeline.md` — chronological narratives

But concepts/ and entities/ are primary. When in doubt, file there.

## Page Hierarchy

Wiki pages use parent/child hierarchy via paths:
- `/wiki/concepts.md` — parent page (summarizes all concepts)
- `/wiki/concepts/attention.md` — child page (goes deep)

The UI renders this as an expandable tree. Parent pages summarize; child pages go deep.

---

## Page Template

Every wiki page MUST follow this exact structure:

```markdown
Summary paragraph here — 2-3 sentences explaining what this is and why it matters.
No H1 heading — the title is rendered by the UI.

## Architecture / Overview

(Mermaid diagram with branded component colors — see below)

| Attribute | Detail |
|-----------|--------|
| **Key** | Value |

## Section Name

Prose with inline citations[^1]. Bullet points for facts, prose for synthesis.

## Related Pages

- [Page Name](relative-path.md) — one-line description of relationship
- [Page Name](../entities/other.md) — cross-reference

[^1]: Human Readable Source Name.html
[^2]: Another Source.html, p.3
```

---

## Mermaid Diagrams — MANDATORY

**Every wiki page MUST include at least one Mermaid diagram.** A page with only prose is incomplete.

### Rules

1. **No `%%{init}%%` block** — the renderer handles light/dark theming automatically
2. **No HTML in labels** — HTML is disabled. Use `\\n` for line breaks: `Node["Line 1\\nLine 2"]`
3. **Always quote labels** — use `["Label"]` syntax for ALL node labels
4. **Keep labels short** — max 3-4 words per line, 2-3 lines per node
5. **Use subgraphs** for logical grouping — always quote subgraph labels too
6. **Direction**: `TB` for hierarchies, `LR` for flows
7. **Always apply component colors** via `style` directives (see below)
8. Supported types: flowcharts, sequence, state, ER, class, gantt, pie

### Component Colors (LIGHT MODE — dark mode auto-remapped)

Every Cribl component has an assigned color. Use these EXACT hex values so diagrams are consistent across the entire wiki. The renderer automatically remaps to dark-mode equivalents.

```
%% Products — Cribl Brand Guide colors
style Stream fill:#00CCCC,stroke:#009999,color:#000
style Edge fill:#66CC33,stroke:#4da626,color:#000
style Search fill:#0B6CD9,stroke:#0958B3,color:#fff
style Lake fill:#008080,stroke:#006666,color:#fff

%% Control Plane Services
style Zeus fill:#FF6600,stroke:#CC5200,color:#000
style Maestro fill:#FF944D,stroke:#CC7640,color:#000
style Auth0 fill:#CC190A,stroke:#991307,color:#fff
style Billing fill:#00CC99,stroke:#009973,color:#000
style Admin fill:#D98C0B,stroke:#B37309,color:#000
style Entitlements fill:#00CC99,stroke:#009973,color:#000

%% Infrastructure & Platform
style Typhon fill:#8B5CF6,stroke:#7C3AED,color:#fff
style CICD fill:#A78BFA,stroke:#8B6FD9,color:#000
style ECS fill:#64748B,stroke:#4B5563,color:#fff
style EKS fill:#64748B,stroke:#4B5563,color:#fff
style CFN fill:#94A3B8,stroke:#6B7A8D,color:#000
style VPC fill:#475569,stroke:#374151,color:#fff
style NLB fill:#475569,stroke:#374151,color:#fff
style S3 fill:#059669,stroke:#047857,color:#fff
style Monitoring fill:#EC4899,stroke:#BE185D,color:#fff

%% Concepts / Containers
style Org fill:#E8E8E8,stroke:#CCCCCC,color:#000
style Workspace fill:#D8D8D8,stroke:#CCCCCC,color:#000
style WorkerGroup fill:#CCCCCC,stroke:#999999,color:#000
```

### Example with Colors

````
```mermaid
graph TB
    Zeus["Zeus"] --> Stream["Stream"]
    Zeus --> Search["Search"]
    Maestro["Maestro"] --> Zeus

    style Zeus fill:#FF6600,stroke:#CC5200,color:#000
    style Maestro fill:#FF944D,stroke:#CC7640,color:#000
    style Stream fill:#00CCCC,stroke:#009999,color:#000
    style Search fill:#0B6CD9,stroke:#0958B3,color:#fff
```
````

### Tables

Use tables for ANY structured comparison — feature matrices, attribute lists, pros/cons, timelines. If you have 3+ items with attributes, it should be a table.

---

## Citations — REQUIRED

Every factual claim MUST cite its source via markdown footnotes. Citations are the link between the wiki and the source documents — they are how readers trace claims back to their origin.

### Format

```
Zeus provides the API for all Cribl.Cloud resources[^1].

[^1]: API & Organization Management Service (Zeus).html
[^2]: Single Tenant Infrastructure.html, p.3
```

### Rules

1. **Human-readable source names** — URL-decode filenames. Write `Cribl.Cloud Architecture Deep Dive.html` NOT `Cribl.Cloud+Architecture+Deep+Dive.html`
2. **Full filename** — never truncate. Include the extension (.html, .pdf)
3. **Page numbers for PDFs** — `paper.pdf, p.3` or `paper.pdf, p.12-14`
4. **One citation per claim** — don't batch unrelated claims under one footnote
5. **Every factual statement needs a citation** — if you can't cite it, don't write it
6. The UI renders citations as hoverable popover badges inline, and as a collapsible "Sources" panel at the bottom of each page. Source names in the panel are clickable links that navigate to the source document.

### Cross-References

Link between wiki pages using relative markdown links:
```
- [Zeus](../entities/zeus.md) — the API backend
- [Authorization](authorization.md) — same-level reference
```

---

## Core Workflows

### Ingest a New Source
1. Read it: `read(path="source.pdf", pages="1-10")` — use batch reads for multiple files
2. Identify key entities and concepts
3. Create or update **entity** pages under `/wiki/entities/` — one per service/product/technology
4. Create or update **concept** pages under `/wiki/concepts/` — one per cross-cutting theme
5. Every new page must have: summary, diagram with colors, table, citations, related pages
6. Update `/wiki/overview.md` — source count, key findings, recent updates
7. Append an entry to `/wiki/log.md`
8. A single source typically touches 5-15 wiki pages — that's expected

### Answer a Question
1. `search(mode="search", query="term")` to find relevant content
2. Read relevant wiki pages and sources
3. Synthesize with citations — every claim must trace back to a source
4. If the answer is valuable, file it as a new wiki page
5. Append a query entry to `/wiki/log.md`

### Maintain the Wiki (Lint)
Check for: contradictions, orphan pages, missing cross-references, stale claims, concepts mentioned but lacking their own page, diagrams missing component colors, citations with URL-encoded names. Append a lint entry to `/wiki/log.md`.

## Available Knowledge Bases

"""


def register(mcp: FastMCP) -> None:

    @mcp.tool(
        name="guide",
        description="Get started with LLM Wiki. Call this to understand how the knowledge vault works and see your available knowledge bases.",
    )
    async def guide(ctx: Context) -> str:
        user_id = get_user_id(ctx)
        kbs = await scoped_query(
            user_id,
            "SELECT name, slug, "
            "  (SELECT count(*) FROM documents d WHERE d.knowledge_base_id = kb.id AND d.path NOT LIKE '/wiki/%%' AND NOT d.archived) as source_count, "
            "  (SELECT count(*) FROM documents d WHERE d.knowledge_base_id = kb.id AND d.path LIKE '/wiki/%%' AND NOT d.archived) as wiki_count "
            "FROM knowledge_bases kb ORDER BY created_at DESC",
        )
        if not kbs:
            return GUIDE_TEXT + "No knowledge bases yet. Create one at " + settings.APP_URL + "/wikis"

        lines = []
        for kb in kbs:
            lines.append(f"- **{kb['name']}** (`{kb['slug']}`) — {kb['source_count']} sources, {kb['wiki_count']} wiki pages")
        return GUIDE_TEXT + "\n".join(lines)
