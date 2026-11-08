# Offline bundle and PDF export (G1, G2)

Two optional steps after a site is built, for instructors (a classroom without network, printed handouts) and
engineers (a PDF to file or annotate). Neither changes the content; both are re-runnable.

## G1 — offline bundle: `scaffold.py <site> --offline`

```
python <SCRIPTS>/scaffold.py <site> --offline                     # downloads once (about 2.5 MB)
python <SCRIPTS>/scaffold.py <site> --offline --vendor-from <dir> # copies from a local cache, no network
python <SCRIPTS>/validate.py <site>
```

- Copies into `assets/vendor/`: KaTeX 0.16.9 (`katex/`: css, js, `contrib/auto-render.min.js`, every font the css
  names, its `url(fonts/…)` kept relative), highlight.js 11.9.0 (`highlight/`: the three files `app.js` loads) and the
  Google Fonts (`fonts/fonts.css` for the template's families, `fonts/atkinson.css` for the dyslexia-friendly reading
  setting, the woff2 files beside them, fetched with a browser User-Agent so Google serves woff2).
- Rewrites every page's CDN `<link>`/`<script>` (the `_*.html` skeletons too, with `../` under `pages/`), drops the
  fonts preconnect hints and sets `site.json` `"vendor": true`; the runtime then loads highlight.js and the F2 font
  from `assets/vendor/` as well. Pages written later from the skeletons are already local.
- `assets/vendor/manifest.json` records each file's source URL, size and sha256. A re-run fetches only what is missing
  or changed, so it needs no network; files nothing needs any more are deleted.
- `--vendor-from <dir>`: a folder laid out like `assets/vendor/` — another site's `assets/vendor/` is the usual cache
  (its `manifest.json` supplies the source URLs).
- No network and no cache: the step stops with `could not download <url> … are you offline?` and `site.json` keeps no
  flag.
- A later `scaffold.py --plan` on a vendored site keeps the flag and re-applies the rewrite to recopied pages.
- `validate.py` fails a vendored page that still loads a CDN `<link>`/`<script>`, and a vendor file that is missing or
  whose sha256 differs from the manifest; the fix is `scaffold.py <site> --offline`.
- **Single page**: run `--offline` on `tmp/site/`, then `bundle.py` as usual. The bundle inlines the vendored css with
  the fonts as data: URIs (KaTeX woff2 only, Google Fonts latin and latin-ext only), KaTeX, and highlight.js when the
  page has code: about 1 MB, one file that renders maths with no network. It warns when it is over `budgetKb`. The
  dyslexia-friendly font is not inlined; that one opt-in setting still needs the network in a bundle.
- Generated files belong to the topic's site, never to the plugin template.

## G2 — PDF and print

The stylesheet's print rules apply to any print (Ctrl+P, `QC.printHandout()`, `print_pdf.py`): the shell is hidden;
details open; figures, tables and callouts are kept whole; every section of a module page starts a new page; external
links print their URL; page n / N at the bottom right, site · page title at the top left, version · licence at the
bottom left (Chrome/Edge 131+; other browsers ignore the margin boxes); canvases are swapped for PNG snapshots and dark
mode prints light, restored after printing (`QC.printPrepare()` / `QC.printRestore()`). What shows of the solutions
follows the reading mode (B3): reader and instructor prints include solutions, **handout** mode hides solutions,
instructor notes and quiz explanations and adds a Name / Date line.

```
python <SCRIPTS>/print_pdf.py <site> [--pages a.html,b.html] [--handout] [--out <dir>] [--browser <path>]
```

- One PDF per page, in the reading order of `site.json`: `<out>/NN-<name>.pdf` (`-handout.pdf` with `--handout`);
  `<out>` defaults to `<site>/tmp/pdf/` (a topic folder; `tmp/` is git-ignored), else `<site>/pdf/`.
- `--handout` opens every page as `page.html?mode=handout` (the B3 query; nothing is stored).
- The browser: `--browser <path>`, else `$ATLAS_BROWSER`, else Chrome, Edge or Chromium on PATH or in the usual
  install folders (Windows, macOS, Linux). None found: exit code 2 with a message saying what to install.
- Runs `--headless=new --no-pdf-header-footer --virtual-time-budget=<--budget-ms, default 15000>
  --print-to-pdf=<file>` with a throw-away profile, so KaTeX, highlight.js and the plots finish before printing. A
  vendored site prints with no network.
- `pypdf` is an optional dependency: when it is importable the PDFs are also merged into `site.pdf`
  (`site-handout.pdf`); without it the RESULT line says `combined=none` (`pip install pypdf` to get it).
- Ends with `RESULT: tool=print_pdf status=PASS|FAIL errors=n warnings=n pages=n pdfs=n combined=… handout=yes|no out=<dir>`.
