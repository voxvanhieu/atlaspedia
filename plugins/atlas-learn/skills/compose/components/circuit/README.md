# Circuit — schematic symbols, schematics from data, pinouts and register maps

Use for electronics pages: a circuit drawn from library symbols inside an ordinary diagram, a small schematic written as data, a chip or connector pinout with a pin table, and a peripheral's register map with bit grids and field tables. Everything is drawn at view time from markup in the page (no file is fetched, so it works from `file://`). Snippets: `symbols.html`, `schematic.html`, `pinout.html`, `regmap.html`.

## Symbol library — `symbols.html`

Nineteen symbols, drawn in `currentColor` so light and dark both work: `sym-resistor`, `sym-capacitor`, `sym-cap-polar`, `sym-inductor`, `sym-diode`, `sym-led`, `sym-zener`, `sym-npn`, `sym-pnp`, `sym-nmos`, `sym-pmos`, `sym-opamp`, `sym-ground`, `sym-vcc`, `sym-battery`, `sym-switch`, `sym-crystal`, `sym-fuse`, `sym-port`. Place one in a normal `figure.diagram` SVG with `<use href="#sym-resistor" x="80" y="60"/>`; for a rotated part write the whole placement as a transform, `<use href="#sym-capacitor" transform="translate(150 60) rotate(90)"/>` (do not mix `x`/`y` with a rotation: SVG applies `x`/`y` after the transform). Draw your own wires as `path.sym-wire` (or `polyline.sym-wire`) and junctions as `circle.sym-dot` (r 2.6), and labels with `d-text b` (name) and `d-text mono` (value).

Every part sits on a 10-unit grid with its pins on grid points, so wires meet pins when you keep coordinates on multiples of 10:

| Symbols | Pins (local coordinates, before rotation) |
|---|---|
| resistor, capacitor, cap-polar (+ at 0), inductor, diode / led / zener (anode at 0, cathode at 40), battery (+ at 0), switch, crystal, fuse | (0, 0) and (40, 0) |
| npn | base (0, 0), collector (20, −20), emitter (20, 20) |
| pnp | base (0, 0), emitter (20, −20), collector (20, 20) |
| nmos | gate (0, 0), drain (20, −20), source (20, 20) |
| pmos | gate (0, 0), source (20, −20), drain (20, 20) |
| opamp | inverting input (0, −10), non-inverting input (0, 10), output (40, 0) |
| ground (drawn downwards), vcc (drawn upwards), port (an off-page arrow pointing right; rotate 180 for an input on the left) | (0, 0) |

`rotate(90)` turns a part clockwise around its pin (0, 0): a two-terminal part then runs from (0, 0) down to (0, 40). The runtime injects one hidden sprite (`div#qc-symbols`) only on a page that uses a symbol, and expands every `<use href="#sym-…">` inside `<main>` into a copy of the drawing, so zoom, pan, step-through layers and the SVG/PNG download (C9) all see real shapes. `QC.symbols()` lists the names and `QC.symbolMarkup(name)` returns one symbol's SVG markup for a page script; a script that adds `<use>` elements after load calls `QC.injectSymbols()` first.

**Use when** a circuit explains the mechanism: a filter, a driver stage, a supply, a bias network. **Avoid** a full board schematic — link the vendor's PDF instead.

## Schematic from data — `schematic.html`

`figure.schematic[id]` holding a `<template>` with JSON: `title` (the accessible title; the caption text is used when it is missing), `parts: [{ sym, x, y, rot, label, value }]` (`sym` is a library name with or without `sym-`; `rot` 0, 90, 180 or 270, clockwise around the part's pin (0, 0)), `wires: [[x1, y1, x2, y2, …]]` (a polyline each) and `dots: [[x, y]]` (junctions). The runtime draws the parts, the wires and the labels (name above and value below a lying part, both to the right of a standing one; a port's name beyond its tip), computes the viewBox, inserts the `svg[role=img]` with its `<title>` before the figcaption and adds the class `diagram`, so zoom, pan, fullscreen and the download apply as for any diagram. Write `<` inside the JSON as `<`. **Use when** the circuit is small and its layout simple; draw by hand with `symbols.html` when labels need careful placement or the figure has step-through layers.

## Pinout — `pinout.html`

`figure.pinout[id]` holding a `<template>` with JSON: `package` (`DIP`, `SOIC`, `QFP` or `header`, optionally with the count, `DIP-28`), `rows` (1 or 2, header only; two rows put odd pins left and even pins right), `title` (printed on the package), `pins: [{ n, name, type, note }]`. Types: `power`, `ground`, `io`, `input`, `output`, `analog`, `clock`, `control`, `nc` (default `io`). DIP and SOIC count down the left side from pin 1 at the notch and back up the right; QFP counts anticlockwise from the dot (left, bottom, right, top). The runtime draws the package (a `.diagram`, so zoom and download work), a legend of the types used and a pin table in an open `details.pinout-details`; hovering or focusing a pin (each pin is focusable with an `aria-label`) highlights its table row, and hovering a row highlights the pin. **Use when** the reader wires the part up or reads a datasheet alongside the page. **Avoid** BGA packages (no ball grid here) — use a table.

## Register map — `regmap.html`

`figure.regmap[id]` holding a `<template>` with JSON: `width` (8, 16 or 32), `registers: [{ addr, name, reset, desc, fields: [{ name, msb, lsb, access, reset, desc }] }]`. Numbers may be JSON numbers or strings such as `"0x1C"`, `"0b1010"`, `"0x0000_0700"`. Access: `RW`, `RO`, `WO`, `W1C` (write 1 to clear) or `RSVD`. Cover every bit: name unused bits `RSVD` with access `RSVD` (a bit no field covers is still drawn as reserved, and the validator warns). A field's reset is taken from the register's reset when it has none. The runtime renders one row per register — address, name, description, reset — with a bit grid coloured by access (scrolls sideways on a phone), a `details` with the field table (Bits, Field, Access, Reset, Description), an access legend and, from three registers on, a find box: `0x1C` finds that address, any other text matches register and field names (a field match opens its table and marks the field). **Use when** the reader will program the peripheral. **Avoid** maps longer than about 30 registers on one page — split by function.

## Validator messages this module can trigger

`unknown symbol "sym-x" in <use href>` (a `#sym-…` reference to a library symbol is never reported as a broken link) · `schematic <id> has no <template> holding its JSON` · `schematic <id>: invalid JSON (…)` (on the JSON's own line) · `schematic <id> has no parts` · `schematic <id>: part n has unknown symbol "x"` · `part n needs numeric x and y` · `part n rot must be 0, 90, 180 or 270` · `wire n needs an even list of at least 4 numbers` · `dot n needs [x, y]` · `pinout <id>: package "x" is not DIP, SOIC, QFP or header` · `pinout <id> has no pins` · `pin #k has no number n` · `duplicate pin number n` · `pin n has no name` · `pin numbers must run 1..N (missing …)` · `package DIP-28 but n pins` · `DIP needs an even pin count (got n)` (also SOIC) · `QFP needs a pin count divisible by 4 (got n)` · `header rows must be 1 or 2` · `header with 2 rows needs an even pin count` · `regmap <id>: width must be 8, 16 or 32 (got n)` · `regmap <id> has no registers` · `NAME addr "x" is not a number` · `duplicate register address 0x04 (A, B)` · `NAME reset 0x1FF does not fit 8 bits` · `NAME.FIELD needs whole-number msb and lsb` · `NAME.FIELD msb 2 is below lsb 4` · `NAME.FIELD bits 33:32 outside a 32-bit register` · `NAME.FIELD access "x" is not RW, RO, WO, W1C or RSVD` · `NAME.FIELD reset 0x9 does not fit 3 bits` · `NAME fields A and B overlap at bit n`. Warnings: `NAME bits 7:5 are not covered by a field — mark them RSVD` · `pin n type "x" is not one of …` · `<kind> figure without id` · `<kind> <id> has no figcaption`.
