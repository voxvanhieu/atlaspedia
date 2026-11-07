# Protocol — timing, bit-field, sequence and state diagrams written as data

Use when a page explains a protocol, a bus, a register layout or a message exchange: a timing diagram from JSON (`figure.timing`), a register or packet layout from JSON (`figure.bitfield`), a message sequence from text (`figure.seq`) or a state machine from text (`figure.fsm`). The writer writes data, never coordinates; the runtime draws the SVG, so the drawing is always to scale, consistent and dark-mode safe. Snippets: `timing.html`, `bitfield.html`, `sequence.html`, `fsm.html`.

## Shape (all four)

- `figure.<kind>[id]` > one source element + `figcaption` (bold "Figure n.m — Title." + what to notice) + an optional `.legend`. The source is `<script type="application/json">` for `timing` and `bitfield`, `<script type="text/plain">` (or a `<pre>`) for `seq` and `fsm`. Inside a script, write `<` and `&` as they are; never write `</script` or `<!--` there.
- The runtime (`protocol`, phase `shell`) parses the source, inserts `svg.proto-svg[role=img]` before the caption with a `<title>` (the caption's bold title, or `data-title` on the figure) and a `<desc>` summary such as "timing diagram: 4 signals over 11 cycles", and adds the class `diagram` to the figure. From there everything in `diagrams/` applies automatically: zoom, pan, fullscreen and the C9 SVG/PNG download (the figure id is the file name). `data-nozoom` opts out as usual.
- A source that does not parse is not drawn: `div.proto-error` names the problem (with the line for text sources) in place of the drawing. The validator reports the same problem with the page line, so fix it before hand-off.
- Every colour is a class in `style.css` (`tm-*`, `bf-*`, `sq-*`, `fsm-*`, `pr-c2…pr-c9`); every text is escaped. `QC.protocol.{timing, bitfield, seq, fsm}` return `{ vb, body, summary }` for page scripts; `QC.protocol.render(fig)` draws a figure added later.

## Timing / waveform — `timing.html` (C2)

```json
{ "signal": [ { "name": "SCLK", "wave": "0.pppp", "node": "..a" }, {}, ["Group", { "name": "MOSI", "wave": "x.==x.", "data": ["A7", "A6"] }] ],
  "edge": ["a->b t_setup"], "config": { "hscale": 1.5 } }
```

- One wave character per cycle: `0` low, `1` high, `x` unknown (hatched), `z` high impedance (mid line), `=` and `2`–`9` a bus cell (`=` and `2` plain, `3`–`9` tinted), `p` / `n` a clock period starting with a rising / falling edge, `P` / `N` the same with an arrow on the active edge, `.` continues the previous cycle, `|` continues it and draws the gap marker (cycles left out).
- `data`: one label per bus cell in order (array, or a space-separated string). `{}` is an empty spacer row; a nested array is a group with its label first (drawn as a bracket on the left). `node`: a letter at a cycle position names that point; `edge`: `"a->b label"` (also `<->`, `-`, `~>`) draws a dashed arrow between two named points. `config.hscale` widens every cycle (default 1 = 40 px).
- Cycle numbers run along the top; vertical guides mark every cycle boundary.

## Bit field / packet frame — `bitfield.html` (C3)

```json
{ "lanes": 32, "msbFirst": true, "unit": "bit", "fields": [ { "name": "Version", "bits": 4, "attr": "4", "type": 3 }, { "bits": 1, "type": "reserved" } ] }
```

- `fields` in order from offset 0; `bits` a whole number > 0. `lanes` = units per row (default: the total when ≤ 32, else 32, or 16 for bytes). A field that crosses a row boundary is drawn in both rows.
- Register mode (default): the most significant bit is on the left and the indices above each field are absolute bit numbers. `msbFirst: true` (network order, RFC style): fields run left to right, top to bottom, the indices are column numbers 0…lanes−1 and the left column gives the byte offset of each row.
- `unit: "byte"` draws a packet frame in bytes (absolute byte offsets above the boxes). `type: "reserved"` or a field without a name is greyed out; `type: 2`…`9` tints the box like a bus cell. `attr` (a string or a list) is printed under the box — access (RW, RO), reset value, unit.
- Names that do not fit wrap onto two lines, then turn vertical, then shorten with "…"; the full name, size and range are always in the box's tooltip.

## Sequence — `sequence.html` (C4)

```text
autonumber
participant C as Client
C->>S: request          (solid, filled arrow)
S-->>C: reply           (dashed)
C-xS: lost              (cross at the receiver)   ->  -->  -)  --)  also work
note over C,S: text      note left of C: text     note right of S: text
loop every second … end   alt condition … else other … end   opt condition … end
```

- One statement per line; `%%` starts a comment; a leading `sequenceDiagram` is allowed. Participants appear in the order they are declared or first used, so an undeclared one still works (the validator warns when some are declared and others are not). `actor` draws a tinted head box. `<br>` breaks a label or note into lines. `autonumber` puts a numbered dot at the start of each message.

## State machine — `fsm.html` (C4)

```text
stateDiagram-v2
direction LR              (or TB)
[*] --> Idle
Idle --> Run : start
Run --> [*]
state Run : motor on      (a description line; Run : motor on also works)
state "Waiting for ack" as Wait
```

- Layered layout: the longest path from the initial state decides each state's column (row with `direction TB`); edges that point back are drawn as curved arcs on alternating sides, self-loops as a small loop; labels sit on a background so they stay readable over lines. `[*]` as a source is the initial dot, as a target the final ring. Composite states (`state X { … }`), forks, choice and notes are not supported — split them into separate figures.

## Validator messages this module can trigger

Every message starts with the kind and figure id and points at the line in the page. Errors: `timing <id> has no <script type="application/json"> source` · `timing <id>: invalid JSON: …` · `timing <id>: JSON needs a "signal" array` · `timing <id>: every signal entry must be an object or a group array` · `timing <id>: signal "MOSI": unknown wave character "q"` · `timing <id>: signal "MOSI": 3 data labels for 6 bus cells` · `timing <id>: config.hscale must be a number > 0` · `bitfield <id>: invalid JSON: …` · `bitfield <id>: JSON needs a non-empty "fields" array` · `bitfield <id>: field 3 "DSCP": bits must be a whole number > 0` · `bitfield <id>: lanes must be a whole number > 0` · `bitfield <id>: unit "word" must be bit or byte` · `sequence <id>: line does not parse: …` · `sequence <id>: "else" outside an alt block` · `sequence <id>: "end" without loop, alt or opt` · `sequence <id>: "loop" is never closed with "end"` · `sequence <id>: no participants and no messages` · `fsm <id>: line does not parse: …` · `fsm <id>: a transition from [*] to [*]` · `fsm <id>: no states` · `sequence <id> has no <script type="text/plain"> or <pre> source`. Warnings: `timing <id>: signal "MISO" has 9 cycles, the longest has 11` · `timing <id>: edge "a->q" names a node no signal defines` · `bitfield <id>: 158 bits do not fill rows of 32 (last row 30)` · `bitfield <id>: field 2: type "blue" is not reserved or 2–9 (drawn plain)` · `sequence <id>: message to undeclared participant "R"` · `fsm <id>: no initial [*] transition` · `<kind> <id> has no figcaption`.
