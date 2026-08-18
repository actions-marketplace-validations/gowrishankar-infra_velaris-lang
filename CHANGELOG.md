# Velaris changelog

## 2.28 - velaris build: hand someone your program
`velaris build program.vel` produces a single executable containing
your program, everything it imports, the standard library, and the
compiler itself. The person you give it to needs nothing installed -
not Python, not Velaris - which is the difference between a language
you write scripts in and one you deliver software with.

The program is compiled and proof-checked before it is built, so a
program that does not compile is never shipped. Command line arguments
reach `args()` as usual. Building needs PyInstaller
(`pip install pyinstaller`), and the compiler says so plainly when it
is missing.

## 2.27 - Handles: real libraries, not just functions
A `Handle` is a ticket for something living on the Python side - a
database connection, an HTTP session, a file. That is the difference
between calling functions and using libraries:

    py_new(module, function, args)   -> Handle    make one
    py_do(handle, method, args)      -> Text      call a method on it
    py_field(handle, name)           -> Text      read an attribute
    py_close(handle)                              let it go

`examples/database.vel` opens a real SQLite database, creates a table,
inserts a row, counts the rows and closes the connection - all from
Velaris, and all behind `uses ffi`, so a program that talks to a
database says so in its signatures.

Arguments travel as JSON and a trailing JSON object becomes keyword
arguments, which many Python APIs require. Handles pass through calls
as arguments too, and anything Python hands back that is not JSON
comes back as a handle rather than being flattened into a string.

## 2.26 - JSON, and calling Python with real data
The FFI shipped in 2.25 could only pass text and receive a scalar,
which is not "call any Python library" - it is "call the ones that
happen to take strings". `py_json(module, function, args_json)` sends
arguments and receives the answer as JSON, so numbers, lists and
nested data survive the trip: `py_json("math", "sqrt", "[16]")` now
gives back 4.0 rather than failing on a string.

JSON is first class and **pure** - reading a document is not an effect:

    json_get(doc, "user.name")     json_int(doc, "user.age")
    json_float(doc, "price")       json_len(doc, "tags")
    json_has(doc, "user.email")    json_of(anything)

Paths walk objects and lists (`tags[1]`, `items[0].price`), records
serialise straight to JSON, and every read can fail - a missing field
is a real possibility, not a crash, and the message says exactly which
step of the path was missing.

## 2.25 - Reaching the outside world, visibly
Velaris can call Python now, which means it can reach every library
Python has - JSON, dates, hashing, databases, anything - through three
builtins:

    py(module, function, args)        -> Text
    py_int(module, function, args)    -> Int
    py_float(module, function, args)  -> Float

They need `uses ffi`, so a function that reaches outside says so in its
signature, and a pure function still cannot do it - nor can anything it
calls. All three can fail (module missing, function absent, bad
argument), so callers handle it like any other failure. `velaris
explain` lists `ffi` next to the functions that use it, which is the
whole point: the power is available and it is never hidden.

Two conveniences, both deterministic: a dotted module path like
`datetime.date` is resolved by importing what imports and reaching the
rest by name, and a function that wants bytes rather than text gets the
text as UTF-8 after the first refusal.

## 2.24.1 - The extension follows the language's version
The 2.23 release tried to publish the extension as 2.22.1 - a version
already on the Marketplace - and reported that as a failure. The
extension's version now comes from the tag itself, an
already-published version is treated as nothing to do rather than an
error, and the test suite fails if the extension's version ever drifts
from the compiler's.

## 2.24 - Lists of text, and split
`List of Text` is modelled symbolically now, so promises about lists of
words are proven rather than checked while running -
`ensures length(result) == length(words) + 1` for a push, for instance.
List literals pick their element sort from their values, and pushing a
value of the wrong sort simply falls back to a runtime check instead of
being forced into a formula that would not mean the same thing.

`split` is modelled as an unknown list with a known minimum: the pieces
themselves are opaque to the prover, but it knows there is always at
least one, which is what contracts about splitting usually rest on.

## 2.23 - Libraries you can actually share
Until now, using someone's Velaris library meant copying a file and
hoping. Three commands fix that:

    velaris add <url or path> [as name]   vendor it into lib/
    velaris deps                          what this project depends on
    velaris verify                        are they exactly as recorded?

`add` fetches the file (local path or https), **compiles it before
accepting it** - a library that does not compile is not added - and
records its exact sha256 in `velaris.toml`. It then tells you what you
just took on: how many functions, how many with proven promises, and
what effects the library performs. `verify` re-checks every hash, so a
library that changed underneath you is something you find out about
rather than run.

Deliberately not a registry: the file lives in your repository where
you can read it, there is no resolver inventing versions for you, and
nothing is fetched at build time.

## 2.22.1 - First extension publish
A version bump so the tagged release has something newer than the
Marketplace has, now that the publisher and token exist. Nothing about
the language changed.

## 2.22 - The editor extension, ready to publish
The VS Code extension is packaged properly: real publisher and
repository metadata, an icon, a license, a written README, settings
for where Velaris lives and whether to check on save, and categories
so it can be found by search. A release workflow publishes it to the
Marketplace when a `VSCE_TOKEN` secret exists, and quietly skips when
it does not - so nothing breaks while that waits on a one-time setup.

## 2.21 - Watching a program run, and case-changing proofs
`velaris trace program.vel` prints every call as it happens - indented
by depth, arguments going in, answer coming back, and `FAILED` with the
reason when a call fails. Native calls are shown too, marked as such,
so a trace never hides half the program. It is the tool a beginner
reaches for when reading is not enough.

The prover models `upper` and `lower` as functions that keep a text's
length, so `ensures length(result) == length(word)` is proven rather
than checked at runtime. Honest limit: a *false* promise about them is
still caught at runtime rather than at compile time, because the
solver cannot pin down the letters themselves - proven claims stay
true, they are just fewer.

## 2.20 - Whole numbers have a size, and outgrowing it is an error
The fuzzer added in 2.16 found a real disagreement: native code holds
whole numbers in 64 bits and wraps around, while the interpreter used
Python's unlimited integers and kept counting. Same program, two
answers, silently.

Neither behaviour is acceptable, so both are gone. A whole number in
Velaris is 64-bit, and arithmetic that outgrows it is an error (E407)
in both engines - the interpreter checks the range, native code uses
the processor's overflow flag through LLVM's checked intrinsics. The
two seeds that found the bug now agree, and so do 250 fresh random
programs.

This is the first bug the fuzzer caught on its own, which is the
entire reason it exists.

## 2.19 - pip install velaris-lang
Velaris is on PyPI. Installing is now one line with no repository URL
to remember, and every release publishes automatically from its tag
through trusted publishing. The README, tutorial and docs site lead
with it.

## 2.18.2 - Minimal-mode expectations for the newest proofs
`div_bad.vel` and `grid_bad.vel` demonstrate bugs only the prover can
see: divide-by-zero on a path that happens not to be taken, and a row
read that is in range for the example data. Without z3 installed both
programs simply run, so the test suite expected the wrong verdict and
every no-dependency leg failed on all three platforms. They are now
listed with the other proof-only examples, and the suite passes with
and without the solver.

## 2.18.1 - Releases stay green
The PyPI job added in 2.18 cannot succeed until a pending publisher
exists on pypi.org, and a release should not be reported as broken for
a step that is waiting on a one-time setup. It no longer blocks the
release; the executables build and attach as before.

## 2.18 - Records holding lists, and publishing
A record's fields may now be lists, floats or text and still take part
in proofs, so `ensures length(result.items) == length(b.items) + 1` is
proven rather than checked at runtime.

Turning that on immediately found a real bug in the ledger app: with
records fully modelled, the prover could see that `describe` calls
`money(e.amount)` on an amount nothing had constrained to be positive.
`money` is now total - a negative amount formats as a refund - and the
app compiles honestly instead of relying on an assumption nobody
checked.

Releases now publish to PyPI on every tag (trusted publishing, no
stored token), so installing becomes `pip install velaris-lang`.

Also: the version in pyproject.toml had drifted to 1.9.0 while the
compiler said 2.17. The test suite now fails if the two ever disagree.

## 2.17 - for loops, tests in Velaris, and text containment proofs
`for i in 0 to n` and `for item in xs` are here. They are turned into
the while loops the rest of the compiler already understands, so
invariant inference and proofs work through them unchanged - the
shorter form costs nothing.

`velaris test program.vel` runs every function named `test_*` that
takes no arguments and reports which returned true.
`examples/std_test.vel` is the first suite: seven tests for the
standard library, written in Velaris, and CI runs them on every push.
The language can now test itself.

The prover models `contains` on text through Z3's string theory, so
`ensures contains(result, word)` is proven rather than checked at
runtime.

## 2.16 - Catching the next one, a third app, and a current tutorial
`fuzz_native.py` generates random Velaris programs - integer maths,
loops, list scans, text scans, floats, branches - runs each one
interpreted and natively, and fails if the two ever disagree. CI runs
it on every push, now across Linux, Windows **and macOS**: the exact
combination that would have caught the 2.15 problem before it reached
anyone.

`examples/fetcher.vel` is a third real program, and the first to use
the network: it reads a URL from the command line, checks the status
before downloading a body, and summarises what it got. Every network
call is behind `uses net` and can fail, so all three failure paths
(bad status, unreachable host, no arguments) are visible in the code
rather than assumed away.

TUTORIAL.md is rewritten for the language as it actually is. The old
one predated lambdas, namespaces, format, args, map proofs, invariant
inference and the whole toolset - someone arriving today was reading a
description of a language from fifteen releases ago.

## 2.15.1 - Native text building, made portable
Two examples failed on Windows in 2.15: a function that RETURNS text
handed a small struct back across the machine-code boundary, and how
that is done depends on the platform's calling convention. Rather than
guess at an ABI this project cannot test everywhere, text results now
stay interpreted. Text built *inside* a native function still uses the
arena and is still fast (183.5 ms interpreted, 4.1 ms native here).

Native compilation is also fail-safe now: if anything about a machine's
backend disagrees with the compiler, the program runs interpreted and
behaves identically, instead of failing. A speed optimisation should
never be able to stop a correct program from running.

## 2.15 - Native text building (the arena)
Concatenation compiles to machine code. Text is built in a scratch
buffer the runtime owns, reset at every call, so native code never has
to decide who frees what. If a call needs more room than the buffer
holds, **nothing is copied**: the buffer grows and the call runs again,
so the answer is always the one the interpreter would have given. A
million characters built through a 64 KB starting buffer comes back
byte-correct, unicode and emoji included, checked against 200 random
strings.

Measured: 172.8 ms interpreted, 0.9 ms native.

Getting there needed one more fix: `length` and `code_at` now work on
any text-valued expression, not just a variable. Before that,
`length(banner(word))` kept a whole loop interpreted, and crossing the
native boundary once per iteration was *slower* than staying
interpreted - the benchmark said so before the fix, which is why the
benchmark is in the example.

## 2.14 - Native text reads, and proven functions run fast
Text scanning compiles to machine code. Text crosses into native code
as Unicode code points plus a length, so `length` still counts
characters and non-English text behaves identically - verified against
300 random strings including accents and emoji. Reads are
bounds-guarded like list reads. Measured: 696.8 ms interpreted, 22.3 ms
native.

New builtin `code_at(text, i)` gives the code point at a position with
no allocation - the operation native scanning needs, and useful
interpreted too.

Two rules changed for the better. A function whose promises are
**proven** may now compile natively: an unproven promise still needs
its runtime check, but a proven one is already true, so there is
nothing to check. And the prover learned `length` on text and a sound
uninterpreted model of `code_at`, so text-scanning loops can be proven
at all.

Building text (concatenation) stays interpreted - that allocates, and
allocation gets its own release.

## 2.13 - Native lists
Pure functions that read `List of Int` now compile to machine code.
The list crosses into native code as a pointer plus a length, and every
read is bounds-guarded: an out-of-range position records the mistake
and returns without touching memory, so you get the same E602 you would
have got interpreted rather than a segfault. Measured on a
500-element list summed 200 times: 782.6 ms interpreted, 2.7 ms native,
identical results. Differential-tested as always.

Writing to lists (push) stays interpreted - that needs allocation, and
allocation needs an ownership story this language has not designed yet.

## 2.12 - Lists of lists, proven
A grid is now modelled symbolically - its rows, each row's length, and
how many rows - so `length`, `get` and `push` on nested lists take part
in proofs, and an out-of-range row is caught before the program runs
exactly as it is for a flat list. Nested list *types* also parse now:
`List of List of Int` was previously a syntax error.

That closes the last container with no proof story. Ints, Bools,
Floats (in IEEE-754), Texts, records, lists, nested lists and maps are
all proof territory; only Text contents remain runtime-checked.

## 2.11 - Invariant inference (the boring ones, for free)
Loops without a written `invariant` can now be crossed by the prover.
Candidate invariants are proposed for every counter a loop moves - it
never goes below, or never above, the value it started at - assumed
together, and whatever one loop step can break is dropped, repeating
until the set is stable. (Houdini, kept small.) `examples/inferred.vel`
proves three promises with no invariant lines at all.

Honest about the limits: this infers simple bounds on counters, not
membership or sortedness, so the standard library's loops still need
their hand-written invariants.

Also fixed something that had been quietly lying since 2.6: `explain`
and the inspector reported a function as "proven" whenever the file had
no errors, even when the prover had actually given up and left the
promise to a runtime check. The status now comes from the prover
itself, so "proven" means proven.

## 2.10 - Contracts on function values
An inline function can carry `requires` and `ensures` of its own, and
they are proven like any other function's - so a function value is a
first class citizen rather than a convenience. Because lambdas are
lifted to real functions, this needed no new machinery in the prover.
Errors about them now say "this function value" instead of leaking the
generated name.

## 2.9 - Map proofs
Maps are now modelled symbolically - the values, plus which keys are
actually present - so `put`, `get_or` and `has` take part in proofs.
Promises like "this key now holds one more than before" are proven
before the program runs, and wrong ones are refuted with the offending
key. Text values became symbolic strings to make map keys work, which
also lets Text cross call summaries.

Lists remain arrays of Ints: anything else (Text lists, lists of
lists) is explicitly guarded now and falls back to runtime checks
rather than being forced into a sort it does not fit.

## 2.8 - A second real app, and Text ordering
`examples/wordcount.vel` reads a file, counts word frequencies and
prints a ranked histogram - a different shape of program from the
ledger, exercising maps, records, lambdas, namespaced imports, format,
args, and three separate failure paths (missing file, unreadable count
argument, no words found).

Writing it found a real hole: Text had no ordering, so `c >= "a"` did
not compile and words could not be sorted alphabetically. `<`, `>`,
`<=` and `>=` now work on Text, comparing alphabetically. Promises
about Text comparisons are checked at runtime rather than proven, and
the prover does not pretend otherwise.

Also: the error de-duplication from 2.5.1 now lives in the shared
analysis, so `check`, `explain` and the browser inspector report one
message per problem too.

## 2.7 - Reading a codebase
`velaris check program.vel` compiles without running - for CI, editors,
and pre-commit hooks - and takes several files at once. `velaris
explain` now puts *your* functions first and summarises imported
libraries in one line (`--all` expands them), because the first real
run of explain buried a ten-function app under eighteen library
functions. `velaris explain <folder>` maps every .vel file under a
directory: functions, proven promises, effects, and any errors.

## 2.6 - Division proofs, and seeing what your code promises
`velaris explain program.vel` walks through a file function by
function: what it may do, what it needs, what it promises, and whether
those promises are proven or left to runtime. The browser playground
gains an **Inspect** button showing the same thing as cards, with
errors and their fixes in place. `--json` gives the whole report as
data for tools.

Contract printing is now precedence-aware, so `(result + 1) * count`
no longer prints as `result + 1 * count` (it did, on the docs site).

## 2.6 - Division proofs
`/` and `%` on whole numbers are now proof territory: the compiler
proves the divisor is never zero (E706, with the value that breaks it)
and can prove what the result means. Translated only when the divisor
is provably positive, because Velaris floors like Python while Z3's
integer division is Euclidean - the two disagree on negative divisors,
so that case falls back to a runtime check rather than a formula that
would quietly lie.

## 2.5.1 - One problem, one message
The effect checker and type checker could both report the same unknown
function, so a single mistake printed twice. Identical errors are now
reported once.

## 2.5 - Namespaced imports
`import "lib/geo.vel" as geo` then `geo.distance(a, b)`. A named import
prefixes that library's functions, rewriting its internal references so
the library is unchanged from the inside. Two libraries exporting the
same name can now be used in one file, which was impossible before.
Unknown namespaces and unknown functions inside a namespace get their
own messages (E200 lists what the namespace does offer), and a local
variable may not shadow an import name (E514). Plus a written piece on
why float proofs use IEEE-754 rather than reals: docs/floats.md.

## 2.4 - The everyday things
Function values inline: `keep_if(xs, fn(n: Int) -> Bool { return n > 4 })`.
They are lifted to real top-level functions, so types, effects, proofs
and native codegen treat them like any other function - and they cannot
capture surrounding variables, which keeps them pure and gives a clear
error when you try. Also: `format("hi {}", name)` with placeholder
count checked at compile time, `args()` for command line arguments,
`post(url, body)` and `fetch_status(url)` alongside `fetch`. The ledger
app now uses a lambda for its report sorting.

## 2.3 - Public launch polish
New visual identity across the docs site, playground, and README:
light professional design, verified-green brand, refined typography.
Landing page rebuilt. Fixed minimal-mode CI: fail_proof_bad's bug is
only findable by proof, so without z3 it is expected to run.

## 2.2 - Out-of-the-box readiness
velaris doctor (self-diagnosing setup with exact fixes), velaris new
(scaffold a project that runs), standalone executables for
Windows/Linux/macOS built and attached to every release (no Python
required), SECURITY.md with soundness-is-security policy, issue
templates, and a semver stability promise in the README.

## 2.1 - Documentation site
build_docs.py generates docs/: landing page, tutorial, a library
reference parsed from stdlib/std.vel by the real compiler (contracts
shown), an error index scraped from velaris.py (cannot go stale), and
the playground. Built in CI; one click from GitHub Pages.

## 2.0 - The builtins keep the language's promise (BREAKING)
to_int, get-on-a-map, read_file, and fetch are now fallible: they must
be called through check or try, and their failures can finally be
handled instead of killing the program. Migration is compiler-guided -
error E520 points at every call needing a wrap. get on a LIST is
unchanged (bounds are the prover's domain, proven at compile time).
New: get_or(m, key, default), a total map lookup. All examples
migrated; guess.vel now survives typos, net.vel survives outages, and
the ledger's loader shrank.

## 1.20 - sort_by + ledger reports
std.vel gains generic sort_by(xs, key) - sort anything by an Int key
function. The ledger uses it for a new report command: sorted-by-amount
listing with biggest, smallest, and totals. The CI session exercises it.

## 1.19 - Standard library sprint
std.vel grows to sixteen functions, all in Velaris: sort (ensures
is_sorted(result)), min/max (ensures membership), sum, keep_if,
count_where, join, range_list, is_sorted, insert_sorted; apply_to_each
and reverse rewritten with typed lets, dropping their nonempty
requirements. Library requires are enforced at importer call sites.

## 1.18 - Float proofs (real IEEE-754)
Float promises proven in Z3's floating-point theory - bit-for-bit the
machine's arithmetic. The prover refutes real-number identities that
rounding breaks, with the exact double as counterexample. FP queries
get a bigger solver budget; integer proofs stay instant.

## 1.17 - Failure-aware proofs
The prover understands fail / check / try: promises on 'or fail'
functions are proven for every returning path, fail-guards become
facts on those paths, and fallible callees' promises flow through try
and check. CI actions bumped past the Node 20 deprecation.

## 1.16 - Quantified list proofs
`all_of` / `any_of` with a predicate function; in contracts they become
Z3 foralls/exists with the predicate's body symbolically inlined.
Fixed a latent soundness-of-reporting hole: an untranslatable
`requires` now aborts the proof instead of being silently dropped
(dropped premises manufacture false counterexamples).

## 1.15 - Native Float and Bool
Typed LLVM codegen (f64, typed allocas/boundaries); division stays
interpreted so divide-by-zero is always a clean error;
differential-tested against the interpreter.

## 1.14 - Record proofs
Symbolic records (one Z3 value per field): field promises proven,
record-aware summaries, records printed in counterexamples.

## 1.13 - The first real app
examples/ledger.vel expense tracker; chars/file_exists builtins; typed
let enabling empty [] and {}; order-flexible signature clauses;
scripted-stdin testing so interactive apps run in CI.

## 1.12 - Continuous integration
GitHub Actions matrix (Linux/Windows x 3.10/3.12 x full/minimal deps),
dependency-aware suite, CHANGELOG, CONTRIBUTING.

## 1.11 - Language server
`velaris lsp`: standard LSP over stdio. Effect/type errors on every
keystroke, full pipeline with Z3 proofs on save; per-file diagnostics
(bugs in imported files squiggle in those files). Dependency-free VS
Code client bundled in `editor/vscode`.

## 1.10 - Formatter
`velaris fmt` (in-place, `--stdout`, `--check`). Comment-preserving,
idempotent, proven meaning-safe by re-running the whole suite on
formatted code. All repo examples reformatted.

## 1.9 - REPL
`velaris repl`: loose lines run immediately; fn/record/import
definitions pass effects, types, and proofs before joining the session.
CLI subcommands (run / repl / version). Unknown functions became a
friendly E200 everywhere.

## 1.8 - Real installation
`pip install ".[full]"` and a `velaris` command. Standard-library
search path: `import "std.vel"` works from any folder.

## 1.7 - Generics + first stdlib
`for any T` with call-site inference and clear conflict errors
(bindings shown). `stdlib/std.vel`: first/last/reverse/index_of/
contains_item/apply_to_each - written in Velaris.

## 1.6 - First-class functions
`fn(Int) -> Int` as a type; pass by name; call through parameters.
Only pure functions travel as values, so nothing is smuggled.

## 1.5 - Unignorable failure
`-> Int or fail`, `fail "reason"`, mandatory `check { ok / fail }`
handling, `try` propagation. Ignoring failure is a compile error.

## 1.4 - Maps
`{"a": 1}` typed `Map of K to V`; get/has/put/keys/length; typed keys
and values; clean E610 for missing keys.

## 1.3 - Float
Decimal numbers with NO silent Int/Float mixing - conversion is
explicit (`to_float`, `round`). Proper negation node.

## 1.2 - Browser playground
The real compiler running in-browser via Pyodide. Zero install.

## 1.1 - Escapes + editor
String escapes (\n \t \" \\) with friendly E002; VS Code syntax
highlighting.

## 1.0 - Testers' release
Multi-error reporting (all broken functions in one run, JSON array for
agents), `to_text`, `--version`, tutorial.

## 0.x - The climb
0.1 effects (io) - 0.2 effect split (io/net/fs/clock/rand) - 0.3 type
checking - 0.4 loops - 0.5 contracts (requires/ensures) - 0.6 lists,
and/or/not, negatives - 0.7 Z3 compile-time proofs - 0.8 modular
verification with sound false-alarm discipline - 0.9 LLVM native
compilation (~10,000x on hot loops) - 0.10 loop invariants - 0.11 real
HTTP fetch - 0.12 interactive input - 0.13 list proofs via array
theory with bounds obligations - 0.14 else-if, %, text tools - 0.15
records - 0.16 imports with per-file error blame.
