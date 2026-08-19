# velaris-lang

Run code you did not write.

```
npx velaris-lang script.vel --allow io
```

That program cannot read a file, reach the network or call Python -
whatever its source says about itself - and a refusal cannot be caught
and carried past.

```javascript
import { audit, run } from "velaris-lang";

const report = await audit(source);
console.log(report.effects);        // ['fs', 'net']
console.log(report.proven_share);   // 66.7

const result = await run(source, { allow: ["io"] });
console.log(result.ok, result.output, result.refusedEffect);
```

Velaris is a language where a function's signature declares its types,
the effects it may perform, whether it can fail, and promises a theorem
prover checks before the program runs. This package is a thin wrapper:
the compiler is a Python package, so `pip install velaris-lang` once.

Not a security boundary - allowing `ffi` grants everything Python can
do. It is a real guard for running a script a model wrote.

[Documentation](https://gowrishankar-infra.github.io/velaris-lang/) ·
[Playground](https://gowrishankar-infra.github.io/velaris-lang/playground.html) ·
[Source](https://github.com/gowrishankar-infra/velaris-lang)
