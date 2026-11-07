# Runner — in-browser code runners (JavaScript sandbox, Python via Pyodide)

Use when the reader should edit an algorithm and run it on the page: a filter step, a bit trick, a numeric method, a small simulation. The runtime turns `div.runner[data-lang]` around a plain `pre > code` into an editable code area with Run (Ctrl/Cmd+Enter), Reset and Copy, an output pane that tells stdout from stderr and, when you give the expected output, a pass/fail chip. Snippets: `runner-js.html` (two JavaScript runners, one with hidden setup code), `runner-python.html` (a standard-library Python computation).

## Shape

```html
<script type="text/plain" id="kf-setup">…helper code the reader need not see…</script>
<div class="runner" id="kf-step" data-lang="js" data-setup="kf-setup" data-timeout="3000" data-expected="line 1&#10;line 2">
<pre><code class="language-javascript">…starting code, escaped (&lt; &amp;)…</code></pre>
</div>
```

| Attribute | Meaning |
|---|---|
| `id` | Required and unique on the page: the reader's edits are saved in this browser per page and runner id; Reset clears them. |
| `data-lang` | `js` or `python`. |
| `data-expected` | Optional. The stdout the code prints **as written**, newlines as `&#10;`, `"` as `&quot;`, `<` `>` `&` escaped. Compared after trimming trailing spaces and blank lines; stderr is ignored. |
| `data-timeout` | Optional, milliseconds, a positive integer (default 5000). JavaScript: the frame is removed. Python: the worker is stopped and Python restarts on the next run. |
| `data-setup` | Optional. The id of a `<script type="text/plain">` on the same page whose text is prepended to the code at run time (data, helpers, imports). It is never executed as page JavaScript and the validator does not syntax-check it, so it may hold Python. |

Before the runtime runs (no JavaScript, print preview of the source) the starting code shows as an ordinary code block. Printing shows the code and the last output, without buttons.

## Security model

- JavaScript runs in an `iframe sandbox="allow-scripts"` (no `allow-same-origin`) built from `srcdoc`: an opaque origin with no access to the page, its storage, cookies or other runners; it works from `file://`.
- Output returns only by `postMessage`, accepted when `event.source` is that frame and a per-run token matches; output is capped at 20 000 characters; the timeout removes the frame.
- Python runs in Pyodide inside a Blob-URL Web Worker (terminated on timeout, fresh globals per run); if the browser refuses the worker it falls back to the page's main thread, where the timeout is best effort. Nothing is ever `eval`ed in the page's own context.

## Network

JavaScript runners need no network. Python runners load Pyodide **v0.26.4** from `cdn.jsdelivr.net` only after the reader presses Run and accepts a one-time notice ("downloads about 10 MB from cdn.jsdelivr.net; needs a network"); the browser caches it afterwards. Offline, the output pane says Python could not be loaded and Run can be pressed again. Standard library only: no `numpy`, no `micropip` installs, no file or network access from the code. A single-format page (`bundle.py`, offline-first) should not carry Python runners — the validator warns.

## Rules

- One runner per algorithm the reader should change; put the numbers they will vary at the top of the starting code, commented with units.
- `data-expected` must be the real output of the code as written (authoring rules, H4): run it yourself — `node` for JavaScript (with the setup prepended), `python -I` for Python — and paste the stdout. `console.log` of an object or array prints JSON (`[1,2]`) in the runner; log strings and numbers when the expected output matters. Set `ATLAS_RUN_RUNNERS=1` before `validate.py` to have node re-run every JavaScript runner that has `data-expected`.
- Keep runs short (well under the timeout) and deterministic: no `Math.random()` or clocks in code with `data-expected`.
- A runner is not an executed example: it carries no `data-executed` badge. Use `core/code-executed.html` for code the reader only reads.

## Validator messages this module can trigger

`runner without id` · `runner X: unknown data-lang "rb" (js or python)` · `runner X has no starting code (pre > code)` · `runner X: data-setup "s" not found` · `runner X: data-setup "s" must be a <script type="text/plain">` · `runner X: data-timeout "5s" is not a positive integer (milliseconds)` · `duplicate runner id X` · warning `runner X: Python runner on a single-format page — the bundle is offline-first and Pyodide needs a network` · opt-in (`ATLAS_RUN_RUNNERS=1`): `runner X: node output differs from data-expected at line n` · `runner X: node run failed: …` · warning `runner node check skipped (node not on PATH)`.
