# Research protocol

How atlaspedia research agents gather and verify material into the dossier, and how the labour is split: **researchers find and judge, the verifier checks mechanically, the consolidator merges, page writers only consume.** Everything here applies `references/evidence-policy.md` (the plugin root's `references/`): a fact enters the dossier only from a source the researcher retrieved and that states it (§4), a number is computed only by a documented method (§5), a relationship is recorded only when a source states it (§6), and what cannot be established is labelled, never filled (§3, §8). Page writers never search the web; a fact a writer needs and cannot find in the dossier comes back as `gaps=` in its report and is researched by one narrowed `atlaspedia:module-researcher`, then written. This is what keeps the search budget and the single source of truth intact.

## 1. Source tiers and what each may support

| Tier | Sources | May support |
|---|---|---|
| 1 | academic textbooks; peer-reviewed papers, reviews, handbooks | theory, methods, quantitative claims, "established" labels |
| 2 | official documentation, standards, regulators, datasheets, reference manuals; preprints (arXiv) and theses — marked "preprint/thesis" | specifications, procedures, product features, regulations, recent methods |
| 3 | reputable engineering blogs, project wikis, tutorials, conference talks/videos | practical know-how, worked examples, pointers — never the sole support for a quantitative claim |
| lead-only | Wikipedia, forums, Q&A sites, vendor marketing | finding primary sources, availability/price indications; never cited as evidence |

Mark each source's status: `foundational` (classic, still taught), `established`, `recent`, `experimental` (research-stage results), `discontinued` (product/tool no longer maintained), `preprint`.

**I5 source classes.** Beyond papers, books and web pages, the brief's `Discovery` line may switch on four extra classes. Each source row may carry a `Kind` (`paper | dataset | code | standard | lecture | book | web`; `check_dossier.py` checks the vocabulary when the column is there):

| Class (Kind) | Where to look | Tier | Record |
|---|---|---|---|
| datasets (`dataset`) | Zenodo, Dryad, figshare, PhysioNet, UCI, the field's own archive; the paper that published it | 2 when the authors or an institution publish it with a DOI; Kaggle mirrors are lead-only | DOI, version, licence, size, the paper that describes it |
| code (`code`) | the official repository of a cited paper or tool (GitHub, GitLab, Codeberg), Papers with Code | 2 for the official repository of a cited work or project; 3 for other repositories | URL, licence, last release or commit date, language |
| standards (`standard`) | IEEE, ISO, IEC, IETF (RFC), ITU, ASTM, national bodies | 2 | the number with edition year (`IEEE 754-2019`, `ISO 8601-1:2019`, `IEC 61508-1:2010`, `RFC 9293`); paywalled → cite the official catalogue page, never a pirated PDF |
| lectures (`lecture`) | MIT OpenCourseWare, university course pages and syllabi, conference talk videos | 2 for an official course page or syllabus; 3 for a video | institution, course code, year, lecturer; videos verified by oEmbed |

## 2. Verification — who does what

`check_links.py` (run by `atlaspedia:source-verifier`) does every mechanical fetch and writes `<file>.links.md`; the verifier compares what the script found (title, authors, year, content type) with what the dossier cites and fills the `Verified` column. Researchers verify only what they must to decide whether to cite (they may run `WebFetch` on a DOI or a doc root); they never spend searches on mechanical checks.

| What | How (`check_links.py` kind) | Accept when |
|---|---|---|
| DOI | `doi` → `https://api.crossref.org/works/<DOI>` | title/authors/year match what is cited |
| arXiv | `arxiv` → `https://export.arxiv.org/api/query?id_list=<id>` | same |
| ISBN / book | `isbn` → `https://openlibrary.org/isbn/<ISBN>.json` or the publisher's page | title, authors, edition, year match |
| Web page / documentation | `page` → fetch; status + `<title>` | 200 and the content is what is cited (not a redirect to a home page) |
| Product status | official product page; "discontinued", "end of life", "legacy", last update date | state "as of <month year>" |
| YouTube video | `youtube` → oEmbed | 200 with title + author_name (record both for attribution) |
| Vimeo video | `vimeo` → oEmbed | 200 with title |
| Wikimedia Commons image | `commons` → imageinfo API (`url`, `extmetadata.LicenseShortName`, `Artist`) | returns the `upload.wikimedia.org` URL to embed plus licence and artist |
| Any image URL | `image` → content-type `image/*` | 200 image |
| PDF | `pdf` → content-type `application/pdf` | 200 |
| Regulation | the regulator's own site (eCFR, EUR-Lex, EASA, national authority) | current consolidated text; note the date |

Verified-column vocabulary: `Crossref ✓` · `arXiv ✓` · `OpenLibrary ✓` · `fetched ✓` · `oEmbed ✓` · `Commons ✓` · `not confirmed automatically — kept as published by <source>` (blocked/timeout on a link the researcher did open) · `✗ dead link` · `✗ mismatch: <what differs>`. There is no "model knowledge" value: a reference the researcher remembers but did not retrieve is not a source row — it goes to `## Could not verify` as `Not available in sources — <what>` (evidence policy §3; `check_dossier.py` fails the old value).

If an endpoint blocks automated fetches, keep a link the researcher opened with "not confirmed automatically" rather than dropping it — and say so.

**What a source row must carry.** The passage that supports each fact: `Key facts and numbers` has a `Locator` column (section, page, table, figure, equation, or `whole page` for a short page) and the source's date or version. A search-result snippet is a lead, not evidence, when the original is reachable; when it is not, the fact is `Insufficient evidence — snippet only` under `## Could not verify`. A methods section the reader can implement goes to `## Documented calculations` (`C1…`: the formula as the source writes it, every input with its source or `reader input`, the output unit and the validity range); a stated dependency, flow or composition goes to `## Documented relationships` (`R1…`). Demos and diagrams are built only from these two tables.

**I4 must-cite, must-avoid and citation style.** The brief's §2.1 carries two lists derived from the interview: *must cite* sources are fetched first (their roots, tables of contents and the chapters that touch the module) before any search is spent, and every module that touches them cites them; *must avoid* sources are never cited, not even as leads or "reported, unverified" — a fact only they support is a gap, listed under `## Could not verify`. The citation style in §2.3 (`numeric` | `author-year`) is the writers' business; researchers record authors, year and title for every source so either style can be built. The licence and accessibility rows do not change the research.

## 3. Search budgeting (researchers)

Web-search quotas run out; the first report's writers all hit the limit. Therefore:
- Send searches in batches of 3–5 per turn; `standard` mode by default, `extended` only for niche or very recent facts.
- Prefer **fetching known roots** (project docs, publisher pages, Crossref/arXiv endpoints) over searching for them.
- Spend in priority order: references that support quantitative or safety-relevant claims → product status/specs → media candidates → everything else.
- When the budget is gone, stop adding sources; list the remaining items under `## Could not verify` as `Not available in sources — <what>` and report `status=PARTIAL`. Never fill them from memory.
- Scout (`atlaspedia:field-scout`): 2–5 searches total. Brief author: ≤ 5, only to complete topic lists. Page writers: none.
- **Discovery (I5), opt-in:** with the brief's `Discovery` line at `none` (the default) nothing changes. Each class it names adds **at most 2 searches per module per class** to a researcher's budget (a module with `code, standards` gets up to 4 extra), spent after the priority order above; fetching a known root (a repository, a standards catalogue page) is still preferred over a search. The cap is a first guess: tune it after the first run from the researchers' budget reports. A class with nothing useful for a module costs nothing: skip it and say so under `## Freshness notes` or `## Could not verify`.
- **OpenAlex enrichment (I5)** — `enrich_openalex.py <topic>` (run by the main agent after the verifier wave when `Discovery` is not `none` or verification is `strict`) looks up every DOI and arXiv id at OpenAlex: open-access copy, citation count, year, venue, type and retraction status, cached in `tmp/openalex.json`, one `Enriched:` line per source under `## OpenAlex enrichment`. It spends no web searches. A retracted work is an error: the source is dropped or replaced (or cited only as retracted, with a reason); a year that differs from the cited one is a warning the consolidator lists under §6 conflicts (online-first and print years often differ by one).

## 4. Handling difficulties

- **Paywalled paper**: cite from the abstract/metadata (Crossref/arXiv); do not quote numbers you could not read.
- **Conflicting sources**: record both values with sources, dates and conditions; never pick one; the writer presents the conflict.
- **Unknown exact spec/price**: record `Not specified — <spec>` (a source covers the product but not the value) or `Not available in sources — <spec>` under `## Could not verify`. A range is recorded only when a source states that range; a price only with the source, its date and "varies by vendor" when the source says so.
- **Missing calculation input or method**: the calculation is not recorded and not performed; list `Not specified — <input>` or `Not available in sources — <method>` under `## Could not verify` (evidence policy §5).
- **A fact the user stated in the interview**: research it like any other claim. Confirmed → cite the source; contradicted → record it under `## Conflicts and limitations` (user vs source); not found → keep it as `user` (running-example parameters only) or list it as `Not available in sources`. Never record it as a sourced fact.
- **Discontinued/renamed tools**: say what replaced them and when (a project archived, a fork, a rename).
- **Regulation**: summarise structure and link the authority; always state that rules change and that the reader must check their jurisdiction.
- **Topic too large for the budget**: a technically meaningful overview, keywords, 3–5 best readings and a learning direction beat a thin treatment of everything — every sentence of that overview still cites a retrieved source.

## 5. Allocation (main agent)

1–3 modules per researcher; the priority module alone; synthesis parts (`S` rows) with the researcher whose modules overlap most; ≤ 5 researchers per wave. The brief's `## 12. Research allocation` is the default grouping. One dossier file per module or part, named `<id>-<slug>.md` (`m04-multi-rate-fusion.md`, `s01-project.md`). The researcher's `RESULT:` line names every file written; the gate `check_dossier.py` runs on each before the plan row flips.

## 6. Consolidation (`atlaspedia:dossier-consolidator`)

The consolidator reads every dossier file and writes `dossier/00-overview.md` with the eight numbered sections of `dossier-template.md`: running-example parameter sheet (one table every writer copies), overlaps and ownership, glossary seed, bibliography seed, media list, conflicts and limitations, unverified items, and **build notes** with one `### Page …` block per future page — the page specs the writers receive (format in `contracts.md` §6). The main agent never consolidates by hand.
