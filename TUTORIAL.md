# Learn Velaris in 15 minutes

Velaris is a small language with one big idea: **a function's signature tells
you everything it can do, and the compiler makes sure it's true.** This
tutorial takes you from nothing to watching a mathematical proof reject a
buggy program.

You need Python 3.10+. For the full experience (proofs + native speed):

```
pip install z3-solver llvmlite
```

All commands below are run from the repo folder.

## 1. Hello, world

Create a file `hi.vel`:

```
fn main() uses io {
    print("hello from velaris")
}
```

Run it:

```
python velaris.py hi.vel
```

Two things to notice already. Programs start at `main`. And `main` says
`uses io` — because printing to the screen is an *effect*, and in Velaris
**every effect must be declared in the signature**.

## 2. Purity is the default

Delete `uses io` from `hi.vel` and run it again. You get:

```
error[E300] function 'main' calls 'print' which needs effect 'io',
            but 'main' declares no effects (it is pure)
```

A function with no `uses` clause is **pure**: the compiler guarantees it
cannot print, read or write files, touch the network, look at the clock, or
use randomness. Not "probably doesn't" — *cannot*. The five effects are
`io`, `fs`, `net`, `clock`, and `rand`, and they're checked through the whole
call chain: if anything a function calls (or anything *those* call) needs an
effect, the signature must say so.

This is the feature that makes AI-written code auditable at a glance: a
function claiming to be a calculator cannot secretly phone home, because
`uses net` would have to appear in its first line. Try it — the example
`examples/caught.vel` is a "file saver" hiding a network call; run it and
watch it get rejected.

## 3. Types

Velaris has `Int`, `Text`, `Bool`, and `List of <type>`. Everything is
checked before anything runs:

```
fn add(a: Int, b: Int) -> Int {
    return a + b
}

fn main() uses io {
    print(add("hello", 5))
}
```

```
error[E501] 'add' needs Int for argument 1, but this is Text
```

Variables are created with `let` and updated with plain `=` — and they keep
their type:

```
let total = 0
total = "oops"        // error: 'total' holds Int, cannot put a Text in it
```

`+` adds numbers and joins text (`"n = " + 5` works). Comparisons, `and`,
`or`, `not`, `if`/`else`, and `while` all behave the way you'd guess. Lists:

```
let xs = [3, 1, 4]              // List of Int - mixing types won't compile
print(length(xs))               // 3
print(get(xs, 0))               // 3  (out-of-range is a clean error)
let ys = push(xs, 1)            // push returns a new, longer list
```

## 4. Contracts: promises the language enforces

Here's where Velaris leaves ordinary languages behind. Signatures can carry
**promises**:

```
fn discount(price: Int) -> Int
    requires price >= 0        // promise about the input  (caller's duty)
    ensures result >= 0        // promise about the output (function's duty)
    ensures result <= price
{
    if price > 100 {
        return price - 10
    }
    return price
}
```

`requires` and `ensures` are not comments — they're checked. Promises must
be pure (a promise that tries to `fetch` something is rejected at compile
time), and `result` refers to the returned value.

## 5. Proofs: bugs found without running the program

For straight-line integer code, Velaris doesn't just *check* promises at
runtime — it hands them to the Z3 theorem prover and tries to **prove** them
before the program runs. Run the included nightmare-bug example:

```
python velaris.py examples/proof_catch.vel
```

```
error[E700] promise cannot be kept: 'pay_bonus' ensures result >= salary
            - proven without running the program:
            salary = 0, years = 31 gives result = -1000
```

That bug only triggers when `years > 30` — every normal test would pass and
it would ship. Z3 searched *all possible inputs* mathematically and returned
the exact one that breaks the promise. Nothing was executed.

Proofs are **modular**: proving one function uses the *contracts* of the
functions it calls (see `examples/compose.vel`), and every call site is
proven to satisfy the callee's `requires` — passing `-3` to a function that
`requires price >= 0` is a compile error with the violating value named
(`examples/callsite_bad.vel`).

And Velaris is honest about limits: loops, lists, and text are beyond the
prover today, so those promises are checked at runtime instead — every call,
every return. When Velaris says "proven," it is literally true.

## 6. Native speed

After all checks pass, pure integer functions are compiled to machine code
via LLVM. See it yourself:

```
python velaris.py examples/bench.vel --time
python velaris.py examples/bench.vel --time --no-native
```

Same program, same answers — typically thousands of times faster native.
Safety isn't traded for speed: nothing compiles until effects, types, and
proofs all pass, and contract-carrying functions deliberately stay
interpreted so promises are never skipped.

## 7. Errors are for agents too

Add `--json` to any run and errors come out machine-readable:

```
python velaris.py examples/sneaky.vel --json
```

```json
{
  "code": "E300",
  "message": "function 'discount' calls 'print' which needs effect 'io', ...",
  "file": "examples/sneaky.vel",
  "line": 5,
  "fixes": ["add 'uses io' to the signature of 'discount'",
            "remove the call to 'print'"]
}
```

This is deliberate: increasingly, the "developer" reading compiler errors is
an AI agent in a fix loop. Velaris speaks both languages.

## 8. The workflow Velaris is built for

1. A **human** writes the signature: types, effects, promises.
2. An **AI** writes the body. (Paste this tutorial or the README into any
   AI assistant and ask it to write Velaris — it will.)
3. The **compiler** is the judge neither can fool.

You state *what* must be true; the machine writes *how*; the math checks it.
That's the whole idea.

## Where to go next

Read the 18 programs in `examples/` — half of them are *designed to be
rejected*, and each rejection demonstrates a guarantee. Then write something
real, break a promise on purpose, and watch the compiler catch you. That
moment is Velaris.
