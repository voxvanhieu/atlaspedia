# Plots — log axes, error bars, heatmaps, function plotters, vector fields and parameter sweeps

Use when a page needs a computed curve that goes beyond a demo's line plot: data spanning decades (log axes), measurements with error bars, a second y-axis, scatter/bar/step/area series, a two-input landscape (heatmap), a formula the reader should bend with sliders without any page script (`figure.fnplot`), a 2-D vector field or phase portrait (`figure.field`, `QC.field`) or a family of curves over one parameter (`figure.sweep`, `QC.sweep`). Every plotted canvas gets PNG · CSV · Copy tools on hover. Snippets: `plot-log.html` + `plot-log.js`, `heatmap.html` + `heatmap.js`, `fnplot.html`, `field.html` + `field.js`, `sweep.html` + `sweep.js`.

## Shape

- **Script-drawn figure**: `figure.plot[id]` > `canvas[id]` (+ `.short|.tall`) + `figcaption`; the page's `qc:ready` handler calls `QC.plot`, `QC.heatmap`, `QC.field` or `QC.sweep` on the canvas. A canvas inside a `.demo` (see `demos/`) works the same way and counts as a demo in the trust footer; a `figure.plot` does not.
- **Declarative figures** (no script): `figure.fnplot[data-fn][data-x]…`, `figure.field[data-fx][data-fy]…`, `figure.sweep[data-fn][data-x][data-sweep]…`, each with a `figcaption`. The runtime inserts the controls (`div.fn-controls` with one `.ctl` per slider), the canvas and, when an expression is wrong, a `div.fn-error` before the caption — nothing throws.
- Ranges are written `data-x="min,max"` and `data-y="min,max"`; an optional third item is the axis label (`data-x="-75,75,latitude φ [°]"`). `data-y` may be left out for an automatic range.

## QC.plot(canvas, cfg) — reference

Draws on a DPR-aware canvas and keeps the config on `canvas._qcplot`; redraws on resize, theme change, tab change and when a `<details>` opens. Every option is optional except `series`. A config from the first template (`{ series, xLabel, yLabel, hlines, legend }`) draws exactly as before.

| Option | Meaning |
|---|---|
| `series: [{…}]` | One entry per curve. `data: [[x, y], …]` (NaN, or a value ≤ 0 on a log axis, breaks the line). `label` (legend; rows wrap). `type`: `'line'` (default) · `'scatter'` (dots only) · `'bar'` (bars grouped per x; `barWidth` = group width as a fraction of the x spacing, default 0.7) · `'step'` (hold the value until the next x) · `'area'` (line + fill to y = 0). `color: 'var(--s2)'` or a hex (default `--s1…--s6` in order), `dash: [4,4]`, `width`, `alpha`, `fill: true` (same as `area` on a line), `points: true` (dots on the line), `size` (dot radius). `axis: 'y2'` puts the series on the right-hand axis. |
| error bars | On a series: `errors: [[x, y, err], …]` (± err) or `[[x, y, lo, hi], …]` (absolute bounds) — drawn with caps, centre dot when the series has no `data`; or `yerr: [err, …]` parallel to `data` (an entry may be `[minus, plus]`). Both extend the automatic range. |
| `title` | One line at the top, in the UI font. |
| `xLabel`, `yLabel`, `y2Label` | Axis titles (units in brackets). The right axis and its tick labels take the colour of the first `y2` series. |
| `xRange`, `yRange`, `y2Range` | `[min, max]`; otherwise from the data (y padded 8 % and extended to the nice ticks; x exactly, bars get half a slot of room). |
| `xScale`, `yScale`, `y2Scale` | `'linear'` (default) or `'log'`: decade ticks with 2× and 5× minors (labelled when the span is ≤ 3 decades); points ≤ 0 are skipped; a given range must be positive. |
| `xTicks`, `yTicks`, `y2Ticks` | A tick count (target) or an explicit array of values. |
| `xFormat`, `yFormat`, `y2Format` | `v => string` for the tick labels (default `QC.fmt`, or `1e5`-style on log axes). |
| `grid: false` | Short tick marks instead of grid lines. |
| `hlines`, `vlines`, `bands` | `[{ y, label, color, axis? }]`, `[{ x, label, color }]`, `[{ y0, y1, color }]` — dashed reference lines and shaded bands (as before). |
| `legend: false` | No legend row (the plot area starts higher). |
| `under(g, f)`, `draw(g, f)` | Custom drawing below / above the series inside the clipped plot area: `g` is the 2-D context, `f = { X, Y, Y2, x0, x1, y0, y1, W, H, P, color, v, pal }` (`X`/`Y` map data to pixels, `v('--accent')` reads a variable). `QC.field` uses this; page scripts may too. |

Helpers: `QC.fmt(v, decimals?)`, `QC.niceTicks(min, max, n)`, `QC.onTheme(fn)`, `QC.isDark()`, `QC.plotCsv(canvas)` (the CSV text the tools download).

## QC.heatmap(canvas, cfg)

`{ z: [[…], …], x?, y?, xLabel, yLabel, zLabel, title, zRange?: [min, max], palette?: 'viridis' | 'diverging' | 'grey' | [colours], cells?: true, values?: true, zFormat? }`. `z[j][i]` is the value at `y[j]`, `x[i]`; `x`/`y` are numbers (cell centres, uniform or not) or category strings; missing → indices. Non-finite cells keep the background. `viridis` (9 stops, interpolated) is the default; `diverging` runs `--s1` → surface → `--s2` and is centred on 0 unless `zRange` says otherwise; `grey` runs surface → ink. A colour bar with nice ticks sits on the right; `cells` draws cell borders, `values` prints each value when the cells are large enough. The config is kept on `canvas._qcheat` and redraws like a plot.

## Download tools

Every canvas drawn by `QC.plot`, `QC.heatmap`, `QC.field` or `QC.sweep` is wrapped in `div.plot-wrap`; hovering it or tabbing into it shows `div.plot-tools` with **PNG** (the canvas on a solid background in the current theme, `<canvas or figure id>.png`), **CSV** (`x,<series labels>` rows over the union of x values, empty cells for gaps; a heatmap exports one row per y with the x values as columns) and **Copy** (the same CSV to the clipboard). The download goes through `QC.download` when another feature provides it, else a Blob link. Hidden in print.

## figure.fnplot — declarative function plotter

```html
<figure class="fnplot" id="fig-k" data-fn="a*sin(b*x)+c; cos(x)" data-x="-10,10,x" data-y="-4,4" data-vars="a=1:3:0.1:1.5, b=0.5:4:0.1:1, c=-2:2:0.5:0" data-labels="f, g" data-scale="linear"><figcaption>…</figcaption></figure>
```

`data-fn`: expressions in `x` separated by `;`. `data-x`: required range (+ label). `data-y`: optional range (+ label); set it for functions with asymptotes. `data-vars`: `name=min:max[:step[:value]]` per slider, in order (default step = range/100, default value = midpoint). `data-labels`: legend text per function. `data-scale`: `linear` (default), `log` (y), `logx`, `loglog`. 401 samples per function, re-plotted on every input (no debounce needed). Values beyond ±1e9 become gaps.

**Expression language** (`QC.parseExpr(src) → f(scope)`; `f.vars` lists the identifiers it reads): numbers (`1e-3`), `x`, the slider names, `pi`, `e`; `+ - * / ^ %`, unary minus, parentheses; functions `sin cos tan asin acos atan atan2 sinh cosh tanh exp ln log log10 log2 sqrt cbrt abs floor ceil round sign min max pow hypot clamp step` (`log` = natural log, `step(x)` = 0 for x < 0 else 1, `clamp(x, lo, hi)`). No implicit multiplication (`2x` is an error), no `=`, no strings, no `eval`. A wrong expression shows its message in `.fn-error` and the other functions still draw.

## figure.field and QC.field — vector field / phase portrait

```html
<figure class="field" id="fig-flow" data-fx="y" data-fy="-x - 0.3*y" data-x="-3,3" data-y="-3,3" data-grid="16" data-trajectories="1,0; -2,1"><figcaption>…</figcaption></figure>
```

`data-fx`/`data-fy`: expressions in `x` and `y` (required). Optional: `data-grid` (arrows per side, 4–60, default 18), `data-trajectories` (`x,y` starts separated by `;`, at most 24), `data-labels` (legend per trajectory), `data-streamlines="n"`, `data-nullclines`, `data-normalize="false"` (arrow length ∝ magnitude), `data-dt`, `data-steps`.

`QC.field(canvas, { f: (x, y) => [dx, dy], xRange, yRange, grid: 18, normalize: true, streamlines: 0, trajectories: [[x0, y0], …], labels, dt: 0.02, steps: 600, nullclines: false, xLabel, yLabel, title, legend })`: arrows at the cell centres coloured by magnitude (`--s1` → `--s2`), trajectories integrated with RK4 (at most 2000 steps each, stopping when they leave the box) drawn as lines with a start dot, streamlines seeded on a lattice and integrated both ways in grey, nullclines as dots where dx = 0 (`--s1`) and dy = 0 (`--s2`). Built on `QC.plot`, so the download tools and redraws apply (the CSV holds the trajectories).

## figure.sweep and QC.sweep — parameter sweep

```html
<figure class="sweep" id="fig-decay" data-fn="exp(-k*x)*cos(3*x)" data-x="0,10" data-sweep="k=0:1:0.2"><figcaption>…</figcaption></figure>
```

`data-fn`: an expression in `x` and the swept name; `data-sweep`: `name=min:max:step` (at most 24 members); `data-x` required, `data-y`, `data-scale` and `data-labels` as for fnplot. A slider highlights one member (the middle one at first); the legend reads `k = 0.2`, …

`QC.sweep(canvas, { param: { name: 'k', values: [0.1, 0.3, 1, 3] }, fn: (p, x) => y, xRange, samples: 400, highlight: index, xLabel, yLabel, title, yRange, xScale, yScale, legend, hlines, vlines })` — or `fn: (p) => [[x, y], …]` returning the points itself. Members are coloured along `--s1` → `--s6`; with `highlight` the chosen member is drawn thick and the rest faded; more than 12 members label only the first, middle, last and highlighted ones.

## Rules

- **Evidence (evidence policy §5, §7):** a computed figure (`fnplot`, `field`, `sweep`, a `QC.plot` of a formula) plots a documented calculation and says it is computed; a data figure plots exactly the source's values — never interpolated, smoothed, averaged or extended past them. Either cites its source with `data-cite="#ref-…"` on the `figure` (the runtime adds a "Sources: [n]" line) or a cite in the caption; the validator fails a figure that cites nothing.
- Label both axes with units; put what to notice in the caption, and only what the plotted evidence shows.
- Use a log axis when the data spans more than two decades; never put a zero or negative value on one.
- Error bars need a stated meaning (spread over n runs, ± tolerance, 95 % interval) in the caption; `errors` entries are `[x, y, err]` or `[x, y, lo, hi]`, never mixed in one series.
- A second axis is for a different quantity that shares the x values (phase next to magnitude, count next to time); name it in `y2Label` and keep its series labelled.
- Declarative figures: set `data-y` for functions with asymptotes, keep every slider range meaningful (the validator rejects `a=1` and `min ≥ max`), ≤ 24 sweep members, trajectories inside the field's box. Expressions use the language above, not JavaScript.
- Everything is drawn with the CSS variables (`--s1…--s6`, `--line`, `--muted`, `--surface`): dark mode and print need nothing from the writer.

## Validator messages this module can trigger

`fnplot without data-fn` · `fnplot data-x must be two numbers` · `fnplot data-y must be two numbers` · `fnplot data-x must be positive on a log axis` · `fnplot data-scale "x" is not linear, log, logx or loglog` · `fnplot var "a=1" needs min:max` · `fnplot var "a=3:1" needs min < max` · `fnplot var "a=1:3:0" needs a positive step` · `fnplot expression: unknown function "foo"` · `fnplot expression: unknown variable "q"` · `fnplot expression: unbalanced parentheses` · `fnplot expression: unexpected character "$"` · `fnplot expression: empty expression` · `field figure needs data-fx and data-fy` · `field expression: …` (same sub-messages, names x and y) · `field data-x must be two numbers` / `field data-y must be two numbers` · `field trajectory "1" needs x, y` · `field data-grid "x" is not a whole number` · `sweep without data-fn` · `sweep without data-sweep` · `sweep data-sweep "k=0:1" must be name=min:max:step` · `sweep data-sweep "k=1:0:0.1" needs min < max and a positive step` · `sweep has 101 members, max 24` · `sweep data-x must be two numbers` · `sweep expression: …` (names x and the swept name) · warnings `fnplot figure without figcaption` (also field, sweep) and `fnplot has 1 labels for 2 functions` · inline-script syntax errors (node) for the script-drawn figures.
