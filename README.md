# Velaris

![tests](https://github.com/gowrishankar-infra/velaris-lang/actions/workflows/test.yml/badge.svg)

**The language where you can trust code you didn't write.**

AI now writes a huge share of the world's code, but humans can't review it at
the speed it's produced. Velaris is a small programming language designed
around that problem: a function's *signature* tells you everything it can do —
its types, its effects on the outside world, and its promises about behavior —
and the compiler enforces all three, using mathematical proof where it can.

```
fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
    ensures result <= price
{
    if price > 100 {
        return price - 10
    }
    return price
}
```

Reading that one signature answers the question code review is really asking:
*can I trust this function?* It takes an Int, returns an Int, touches nothing
(no `uses` clause = provably no I/O, network, files, clock, or randomness),
never accepts a negative price, and never returns a negative or increased one.
The compiler rejects the program if any of it is a lie.

## The three superpowers

**1. No hidden effects.** A function may only touch what it declares with
`uses` (`io`, `net`, `fs`, `clock`, `rand`) — checked across the whole call
graph. A "file saver" that secretly phones home does not compile:

```
error[E300] function 'save_report' calls 'fetch' which needs effect 'net',
            but 'save_report' only declares 'uses fs'
  --> caught.vel, line 6
  how to fix (pick one):
    1. add 'uses net' to the signature of 'save_report'
    2. remove the call to 'fetch'
```

**2. No type surprises.** Full type checking before anything runs — wrong
argument types, mixed-type lists, non-boolean conditions, and wrong return
types are all compile errors with numbered fixes.

**3. Promises, enforced — by proof where possible.** `requires`/`ensures`
contracts are verified by the Z3 theorem prover for straight-line integer
code, with exact counterexamples found *without running the program*:

```
error[E700] promise cannot be kept: 'pay_bonus' ensures result >= salary
            - proven without running the program:
            salary = 0, years = 31 gives result = -1000
```

Proofs are *modular*: proving function A uses the contracts of the functions
it calls, and every call site is proven to satisfy the callee's `requires`
(error `E701`). And loops are provable too: give a `while` loop an
`invariant` clause and Velaris proves it holds at entry, survives every
step, and carries the function's promises across the loop
(`examples/loop_proof.vel`). Anything the prover can't handle (lists, text,
loops without invariants) falls back silently to runtime contract checks —
Velaris never claims "proven" unless it is literally true.

Every error has a code, a location, a plain-English message, and numbered
fixes — and `--json` emits the same error machine-readable, designed for AI
agents in fix loops.

## Native speed

After all checks pass, pure integer functions are compiled to machine code
via LLVM (`-O3`), the same backend as Rust and Clang. Measured on a typical
Windows laptop with the included `examples/bench.vel`:

| Mode | Time |
| --- | --- |
| Interpreted (`--no-native`) | ~9,000 ms |
| Native (default) | **~1 ms** |

Effectful and contract-carrying functions deliberately stay interpreted so
promises are never silently skipped.

## Quick start

Requires Python 3.10+. From a clone of this repo:

```
pip install ".[full]"
velaris examples/hello.vel
```

(`[full]` brings z3-solver for compile-time proofs and llvmlite for
native speed; plain `pip install .` works too — promises are then
checked at runtime and everything runs interpreted.)

Without `z3-solver`, promises are checked at runtime instead of proven.
Without `llvmlite`, everything runs interpreted. Nothing else changes.

Run a program (either form works):

```
velaris examples/hello.vel
velaris examples/bench.vel --time
velaris examples/proof_catch.vel        # watch a proof reject a bug
```

**Docs:** a full documentation site lives in `docs/` — open
`docs/index.html` in a browser (library reference is generated from the
real compiler, contracts included; the error index is scraped from the
source). Ready for GitHub Pages the moment the repo is public.

**Zero-install:** open `playground/index.html` in any browser to run
Velaris without installing anything (promises check at runtime there; the
installed version also proves them with Z3 and compiles with LLVM).

Check your install with `python velaris.py --version`, then run the test
suite (28 example programs, each with an expected verdict):

```
python run_tests.py
```

## Editor support

VS Code support lives in `editor/vscode` — syntax highlighting plus
**live errors as you type** (the extension launches `velaris lsp`
automatically when the compiler is installed). Any other LSP-capable
editor can use `velaris lsp` directly. See that folder's README for the
one-line install (no marketplace account needed).

## Language tour

```
// comments start with //

fn add(a: Int, b: Int) -> Int {          // types: Int, Text, Bool, List of T
    return a + b                          // pure: no 'uses' clause
}

fn greet(name: Text) uses io {            // effects: io, net, fs, clock, rand
    print("hello, " + name)               // + joins text
}

fn sum_to(n: Int) -> Int {
    let total = 0                         // let creates, = reassigns
    let i = 1
    while i <= n {                        // while loops; if/else too
        total = total + i
        i = i + 1
    }
    return total
}

fn biggest(xs: List of Int) -> Int
    requires length(xs) > 0               // contracts may use pure functions
{
    let best = get(xs, 0)                 // lists: [1, 2, 3], get, push, length
    let i = 1
    while i < length(xs) {
        if get(xs, i) > best and not (i == 0) {   // and / or / not
            best = get(xs, i)
        }
        i = i + 1
    }
    return best
}
```

The standard library (`stdlib/std.vel`) is written in Velaris and keeps
its own promises: `first` / `last` / `reverse` / `index_of` /
`contains_item` / `apply_to_each` / `keep_if` / `count_where` /
`sum_of` / `max_of` / `min_of` / `sort` (which *ensures*
`is_sorted(result)`) / `sort_by` (generic, by key function) /
`is_sorted` / `join` / `range_list`. Violating a
library `requires` — like `max_of` on a provably empty list — is a
compile error at your call site.

Failure is part of the signature, and ignoring it doesn't compile —
including the builtins: `to_int`, `get` on a map, `read_file`, and
`fetch` are fallible (since v2.0) and must be handled with `check` /
`try`, while `get_or(m, key, default)` offers a never-failing lookup:

```
fn parse_age(t: Text) -> Int or fail {
    ...
    fail "not an age: " + t          // how a function gives up
}

check parse_age(answer) {            // the only way to call it
    ok age { print(age) }
    fail reason { print(reason) }
}
let a = try parse_age(answer)        // or pass failure to YOUR caller
```

Records group named fields into one immutable value:

```
record Point { x: Int  y: Int }
let p = Point(x: 3, y: 4)         // build with named fields
let q = Point(x: p.x + 1, y: p.y) // "change" by building anew
```

Built-ins: `print` and `ask` (io), `read_file`/`write_file` (fs), `fetch`
(net — a real HTTP GET), `now` (clock), `random` (rand), plus pure
`length`, `push`, `get`, and `to_int`. Try `examples/net.vel` to watch a signature-guarded real
network request (needs a connection, so it's not in the offline test suite).

## How it works

```
source (.vel)
   -> lexer -> parser -> AST
   -> effect checker      (E2xx/E3xx: hidden effects, impure contracts)
   -> type checker        (E4xx/E5xx: types, arities, list element types)
   -> proof checker (Z3)  (E700/E701: promises proven broken, modularly)
   -> native compiler     (LLVM -O3 for pure Int functions)
   -> interpreter         (everything else + runtime contract checks E6xx)
```

The whole implementation is one readable Python file, `velaris.py`, in
pipeline order.

## Honest limitations (a.k.a. the roadmap)

- Loops are proven only when you supply `invariant` clauses; **inferring
  invariants automatically** remains open (a live research area). Unproven
  invariants are checked at runtime on every iteration instead.
- List proofs (v0.13, via Z3's theory of arrays) cover `length`, `get`,
  `push`, list equality, and out-of-bounds detection (`E705`); lists of
  lists and quantified properties ("every element is positive") are future
  work.
- `fetch` is HTTP GET only for now — no POST, headers, or status codes yet.
- Native compilation covers pure Int, Float, and Bool functions (v1.15);
  `/` and `%` stay interpreted in both modes so division by zero is always
  a clean error. Text, lists, and records remain interpreted, so far.
- Imports (v0.16) are a flat merge — `import "lib.vel"` pulls in that
  file's functions and records with duplicate-name protection; namespaces
  and a standard library are future work.
- Float proofs (v1.18) use Z3's genuine IEEE-754 theory - the prover
  refutes `x + 0.1 + 0.1 == x + 0.2` with the exact double that breaks
  it. Refutation searches over floats may take ~15s; positive proofs
  are fast. `/` and `%` stay runtime-only in proofs, as in native.
- Quantified list promises (v1.16): `all_of(xs, p)` / `any_of(xs, p)`
  with a simple pure predicate become real Z3 foralls/exists - proven
  where the solver can settle them, runtime-checked where it cannot.
- Record proofs (v1.14) cover records whose fields are Int, Bool, or
  other such records — promises like `ensures result.x == p.x + dx` are
  proven before running. Records containing lists stay
  runtime-checked; Float fields are proven (v1.18).
- The prover is deliberately conservative: it only reports "proven" when the
  counterexample involves no summarized calls, so its claims are always
  literally true.

## FAQ

**Why a new language instead of a checker for existing ones?**
Because the guarantees come from the rules code is *written under*, not from
inspection after the fact. In Python, "does this code secretly touch the
network?" is often unanswerable — access can hide in dependencies, dynamic
strings, and monkey-patching. In Velaris the question can't arise: if the
network is touched anywhere down the call chain, `uses net` must appear in
the signature or the program doesn't compile. It's a building code, not a
building inspector.

**Can't I just ask an AI to review the code?**
You can, and it's useful — but an AI review is an opinion, and opinions vary
by run and miss things. Velaris's checks are mechanical: every path, every
input, the same verdict every time, offline, in milliseconds. AI review
answers "is this well designed?"; Velaris answers "what can this code
possibly do?" — a fact question that deserves proof, not vibes. Use both.

**How does this work with AI coding tools?**
Any AI can write Velaris — paste TUTORIAL.md into your assistant and ask.
Errors come out as structured JSON (`--json`) so agents can self-correct in
a loop. The intended division of labor: humans write signatures (types,
effects, promises), AI writes bodies, the compiler judges both.

**Is "proven" really proven?**
When Velaris says proven, it is literally true — the prover only claims a
counterexample when no summarized call is involved, and everything it can't
prove falls back to runtime checks rather than silence. See "Honest
limitations" below for exactly where the proof boundary sits today.

## License

MIT — see [LICENSE](LICENSE).
