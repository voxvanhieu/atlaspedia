# atlas-learn

**Any topic → your own interactive handbook. One command.**

Tell Claude what you want to learn. It asks a few questions, reads real sources, and builds you a mini-website: chapters, diagrams, quizzes, flashcards - and every fact linked to its source. If something can't be verified, it's marked as missing. Never invented.

![The handbook atlas-learn builds: a hero page describing the topic, its stages and formats](imgs/handbook.png)

## Install

```bash
git clone https://github.com/voxvanhieu/atlas-learn && cd atlas-learn
# macOS / Linux
./install.sh
# Windows
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

No accounts. No keys. Works in every Claude Code session on your machine.

## Learn something

```
/atlas-learn:go how do quadcopters fly?
```

```mermaid
sequenceDiagram
    autonumber
    actor U as You
    participant C as Claude
    U->>C: /atlas-learn:go how do quadcopters fly?
    C-->>U: a few quick questions
    U->>C: answer (or "skip")
    Note over C: plans the chapters<br/>reads live sources<br/>verifies every claim
    C-->>U: your handbook is ready
```

Come back anytime - `/atlas-learn:go` continues exactly where it stopped.

## The journey

What you end up with: a **topics dictionary** to pick a topic from...

![The topics dictionary - filter by name or tag, open a topic](imgs/dictionary.png)

...and the handbook itself:

```mermaid
flowchart LR
    go(["/atlas-learn:go"]) --> a["Interview"] --> b["Plan<br/>you approve"] --> c["Verified<br/>research"] --> d["Interactive<br/>site"] --> done(["Handbook"])
```

| Why it's good            |                                                             |
| ------------------------ | ----------------------------------------------------------- |
| **Facts with receipts**  | every claim cites its source - gaps are shown, never hidden |
| **Actually interactive** | quizzes, flashcards, click-through diagrams                 |
| **Life happens**         | stop anytime, resume anytime                                |
| **Your size**            | one page for quick topics, a full site for big ones         |

Click-through diagrams - switch the layers of a drawing on and off:

![Interactive diagram: the layers of a page, toggled on and off](imgs/figure.png)

Quizzes with answers you think through before revealing:

![A knowledge checkpoint: pick an answer, see where it leads](imgs/quiz.png)

Publication-quality plots, computed live in the page:

![Plots with captions, sources and interactive controls](imgs/plots.png)

## A look inside

Circuits drawn from data, down to the junction dots:

![Schematics generated from JSON](imgs/schematic.png)

Protocol exchanges as sequence diagrams:

![Sequence diagrams written as plain text](imgs/sequence.png)

Simulations with uncertainty you can re-run:

![Uncertainty demos that re-run in the page](imgs/uncertainty.png)

Flashcards generated from the glossary:

![Flashcards generated from the glossary](imgs/flashcards.png)

And a live Python sandbox on the page:

![In-browser Python runner with output](imgs/runner.png)

## Commands

| Command                                                                            | Does                      |
| ---------------------------------------------------------------------------------- | ------------------------- |
| `/atlas-learn:go <topic>`                                                          | the whole journey         |
| `/atlas-learn:go <topic> --single`                                                 | the one-page version      |
| `/atlas-learn:collect-insights` · `/atlas-learn:research` · `/atlas-learn:compose` | run the stages one by one |

## Update · Remove

```bash
# update
claude plugin marketplace update voxvanhieu
claude plugin update atlas-learn@voxvanhieu
# remove
claude plugin uninstall atlas-learn@voxvanhieu
claude plugin marketplace remove voxvanhieu
```

---

The full component catalog with screenshots: [docs/SUPPORTED_FEATURES.md](docs/SUPPORTED_FEATURES.md).

MIT · [voxvanhieu](https://github.com/voxvanhieu)
