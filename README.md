<div align="center">

# Velaris

**Trust code you didn't write.**

A language where the signature tells you everything — the types, the
effects, whether it can fail, and promises **mathematically proven
before the program runs**.

[![PyPI](https://img.shields.io/pypi/v/velaris-lang)](https://pypi.org/project/velaris-lang/)
[![tests](https://github.com/gowrishankar-infra/velaris-lang/actions/workflows/test.yml/badge.svg)](https://github.com/gowrishankar-infra/velaris-lang/actions/workflows/test.yml)
[![release](https://img.shields.io/github/v/release/gowrishankar-infra/velaris-lang)](https://github.com/gowrishankar-infra/velaris-lang/releases)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[**Playground**](https://gowrishankar-infra.github.io/velaris-lang/playground.html) · [**Documentation**](https://gowrishankar-infra.github.io/velaris-lang/) · [**Library reference**](https://gowrishankar-infra.github.io/velaris-lang/library.html) · [**Error index**](https://gowrishankar-infra.github.io/velaris-lang/errors.html)

</div>

---

```
fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
{
    return price - 10
}
```

```
error[E700] promise cannot be kept: 'discount' ensures result >= 0
  proven without running the program: price = 5 gives result = -5
```

That `ensures` is not a comment or a runtime assert. The Z3 theorem
prover verifies it for **every possible input** before execution — and
refutes it with an exact counterexample when it lies.

## Why Velaris

| Guarantee | What it means |
|---|---|
| **Effects are visible** | `uses io, net, fs` — a function without `uses net` can never touch the network, transitively. Hidden behavior does not compile. |
| **Promises are proven** | `requires` / `ensures` / loop `invariant`, verified by Z3 with modular call summaries — including records, maps, nested lists, quantified list properties, failure paths, and floats in **genuine IEEE-754** (the prover refutes `x + 0.1 + 0.1 == x + 0.2` with the exact double that breaks it). |
| **Failure is unignorable** | `-> Int or fail` in the signature; callers must `check` or `try`. Forgetting the error path is a compile error — builtins included. |
| **Fast where it's safe** | Pure functions over numbers, list reads, and text — including text built inside them — JIT to native code via LLVM (~10,000× on hot arithmetic, ~45× on text building), differential-tested against the interpreter. Native reads are bounds-guarded and text is built in a runtime-owned buffer, so results always match interpreted. |

Why floats are proven in IEEE-754 rather than as real numbers, and what
that costs: [docs/floats.md](docs/floats.md).

Loops without written invariants are handled where the boring
invariants suffice: the compiler proposes bounds on each counter and
keeps the ones a loop step cannot break (see `examples/inferred.vel`).
Anything richer — membership, sortedness — still needs an `invariant`
line.

The prover **never** claims "proven without running" unless the
counterexample is premise-complete — untranslatable assumptions abandon
the proof to runtime checks rather than risk a false alarm. Soundness
reports are treated as [security issues](SECURITY.md).

## Install

```
pip install velaris-lang
velaris doctor
velaris new hello && cd hello && velaris main.vel
```

**Standalone executable** (no Python required) — download for
Windows / Linux / macOS from the
[latest release](https://github.com/gowrishankar-infra/velaris-lang/releases),
then:

```
velaris doctor
```

**With Python 3.10+:**

```
pip install velaris-lang
velaris new hello && cd hello && velaris main.vel
```

**Zero install** — the
[playground](https://gowrishankar-infra.github.io/velaris-lang/playground.html)
runs the real compiler in your browser.

Optional extras for source installs: `pip install ".[full]"` adds
`z3-solver` (compile-time proofs) and `llvmlite` (native speed);
without them, promises are checked at runtime and everything runs
interpreted — same language, honestly degraded.

## Everyday ergonomics

```
keep_if(xs, fn(n: Int) -> Bool { return n % 2 == 0 })   // inline functions
format("hi {}, {} left", name, count)                    // text with holes
args()                                                   // command line
post(url, body) / fetch_status(url)                      // not just GET
```

Function values are lifted to real functions, so proofs and native
compilation apply to them unchanged — and they can carry their own
`requires` / `ensures`, proven like any other function's. They can't capture surrounding
variables — the compiler tells you to pass them in instead.

## Two real programs

`examples/ledger.vel` — an expense tracker: records, integer cents,
file persistence, sorted reports.
`examples/wordcount.vel` — text analysis: `velaris examples/wordcount.vel
<file> [n]` counts word frequencies and prints a ranked histogram.
`examples/fetcher.vel` — an HTTP tool: checks a status, then summarises
a page, with every network call declared and every failure handled.

## Imports

```
import "lib/geo.vel" as geo      // named: geo.distance(a, b)
import "std.vel"                 // flat: sort(xs)
```

A named import prefixes that library's functions, so two libraries that
both export `distance` can be used in the same file.

## Tooling

`velaris test program.vel` (runs every `test_*` function written in
Velaris) ·
`velaris check program.vel` (compile without running; several files at
once, `--json` for tools) ·
`velaris explain program.vel` (a walkthrough of every function: effects,
promises, and whether they are proven — `explain <folder>` maps a whole
project) ·
`velaris repl` (definitions are proof-checked as you type them) ·
`velaris fmt` (canonical style, `--check` for CI) · `velaris lsp`
(errors as you type in any LSP editor; a dependency-free VS Code
extension lives in [`editor/vscode`](editor/vscode)) ·
`velaris doctor` · `velaris new` · `--json` errors for automation.

## Standard library

Written in Velaris, in [`stdlib/std.vel`](stdlib/std.vel) — and it
keeps its own promises: `sort` carries `ensures is_sorted(result)`,
`max_of` requires a nonempty list, and violating a library `requires`
is a compile error at *your* call site. Full
[reference](https://gowrishankar-infra.github.io/velaris-lang/library.html),
generated from the real compiler.

## Stability

Semantic versioning: breaking changes **only at major versions** (v2.0
migrated the fallible builtins, compiler-guided). CI tests every push
on Linux and Windows, Python 3.10 and 3.12, with and without the
optional dependencies. Errors are stable, numbered, and
[fully documented](https://gowrishankar-infra.github.io/velaris-lang/errors.html).

## Contributing

The entire implementation is one readable file, `velaris.py`, in
pipeline order — lexer to LSP. Start with
[CONTRIBUTING.md](CONTRIBUTING.md); 52 example programs in
[`examples/`](examples) each carry an expected verdict (half are
*designed* to be rejected — each rejection demonstrates a guarantee).

## License

[MIT](LICENSE) © Gowri Shankar
