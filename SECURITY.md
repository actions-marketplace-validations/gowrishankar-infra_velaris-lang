# Security policy

Velaris takes "you can trust code you didn't write" seriously - that
includes trusting the compiler itself.

## Reporting a vulnerability

Please do NOT open a public issue for security problems. Instead, use
GitHub's private reporting: **Security tab -> Report a vulnerability**
on this repository. You will get a response within a few days.

In scope: anything that makes Velaris's guarantees lie - an effect the
checker misses, a "proven" promise that can actually break at runtime,
a sandbox escape through the playground, or unsafe behavior in
`fetch` / `read_file` / `write_file`.

## Soundness reports are security reports

If the prover claims something is proven and you can make it false at
runtime, that is a vulnerability in this language's core promise.
These reports get top priority.
