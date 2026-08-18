# Velaris for VS Code

Language support for [Velaris](https://gowrishankar-infra.github.io/velaris-lang/) —
the language where a function's signature declares its types, its
effects, whether it can fail, and promises that a theorem prover checks
before the program runs.

## What you get

- **Syntax highlighting** for `.vel` files
- **Live errors as you type**, from the real compiler — including
  promises proven false, with the exact input that breaks them
- **Proof status above every function** — "promises proven before
  running" or "promises checked while running", from the real prover
- **Hover** for any function: its signature, effects, and contracts
- **Go to definition**, across imported files
- An outline of the file's functions
- Comment toggling, bracket matching, and indentation

## Requirements

Velaris itself:

```
pip install velaris-lang
velaris doctor
```

If `velaris` is not on your PATH, set `velaris.command` in settings.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `velaris.command` | `velaris` | How to run Velaris |
| `velaris.checkOnSave` | `true` | Check and prove on save |

MIT licensed. Issues and ideas:
[github.com/gowrishankar-infra/velaris-lang](https://github.com/gowrishankar-infra/velaris-lang/issues)
