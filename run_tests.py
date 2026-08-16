#!/usr/bin/env python3
"""Velaris test suite: runs every example and checks its expected verdict.

    python run_tests.py              # uses native compilation if available
    python run_tests.py --no-native  # force full interpretation
"""
import subprocess
import sys
from pathlib import Path

# every example, with its expected verdict
EXPECT = {
    "hello.vel": "RUNS",            "effects.vel": "RUNS",
    "sneaky_fixed.vel": "RUNS",     "loop.vel": "RUNS",
    "contract.vel": "RUNS",         "features.vel": "RUNS",
    "compose.vel": "RUNS",          "bench.vel": "RUNS",
    "sneaky.vel": "REJECTED",       "caught.vel": "REJECTED",
    "types_bad.vel": "REJECTED",    "loop_bad.vel": "REJECTED",
    "contract_broken.vel": "REJECTED",
    "contract_impure.vel": "REJECTED",
    "list_mixed.vel": "REJECTED",   "list_oob.vel": "REJECTED",
    "proof_catch.vel": "REJECTED",  "callsite_bad.vel": "REJECTED",
}


def main() -> int:
    here = Path(__file__).parent
    examples = here / "examples"
    extra = [a for a in sys.argv[1:] if a.startswith("--")]
    failed = 0
    for name, want in EXPECT.items():
        path = examples / name
        if not path.exists():
            print(f"MISSING   {name}")
            failed += 1
            continue
        r = subprocess.run(
            [sys.executable, str(here / "velaris.py"), str(path)] + extra,
            capture_output=True, text=True, timeout=300)
        got = "RUNS" if r.returncode == 0 else "REJECTED"
        ok = got == want
        print(f"{'PASS' if ok else 'FAIL':4}  {name:22} expected {want:8} got {got}")
        if not ok:
            failed += 1
    total = len(EXPECT)
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
