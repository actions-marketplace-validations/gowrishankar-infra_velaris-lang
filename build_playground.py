#!/usr/bin/env python3
"""Generate playground/index.html with the real velaris.py embedded.

Run after any change to velaris.py:   python build_playground.py
Open playground/index.html in a browser - no install, no server needed.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
SRC = (HERE / "velaris.py").read_text(encoding="utf-8")

EXAMPLES = {
    "hello": """fn greet(name: Text) uses io {
    print("hello, " + name)
}

fn main() uses io {
    greet("world")
    print("2 + 2 = " + (2 + 2))
}""",
    "sneaky effect (rejected)": """// This "pure calculator" secretly prints.
// The effect checker refuses to run it.

fn discount(price: Int) -> Int {
    print("leaking: " + price)
    return price - 10
}

fn main() uses io {
    print(discount(200))
}""",
    "broken promise (caught)": """// The promise says the result is never negative.
// (In the browser, promises are checked while running -
// the installed version PROVES this before running, via Z3.)

fn discount(price: Int) -> Int
    ensures result >= 0
{
    return price - 10
}

fn main() uses io {
    print("discount(200) = " + discount(200))
    print("discount(5) = " + discount(5))
}""",
    "records": """record Point {
    x: Int
    y: Int
}

fn shift(p: Point, dx: Int) -> Point {
    return Point(x: p.x + dx, y: p.y)
}

fn main() uses io {
    let p = Point(x: 3, y: 4)
    print(p)
    print(shift(p, 10))
}""",
    "fizzbuzz": """fn fizzbuzz(n: Int) -> Text {
    if n % 15 == 0 {
        return "fizzbuzz"
    } else if n % 3 == 0 {
        return "fizz"
    } else if n % 5 == 0 {
        return "buzz"
    }
    return to_text(n)
}

fn main() uses io {
    let i = 1
    while i <= 15 {
        print(fizzbuzz(i))
        i = i + 1
    }
}""",
}

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Velaris Playground</title>
<style>
  :root { --bg:#14161a; --panel:#1d2026; --ink:#e8e6e3; --dim:#8a8f98;
          --accent:#7aa2f7; --ok:#9ece6a; --err:#f7768e; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font-family: system-ui, sans-serif; height:100vh;
         display:flex; flex-direction:column; }
  header { padding:10px 16px; display:flex; align-items:center; gap:14px;
           border-bottom:1px solid #2a2e37; flex-wrap:wrap; }
  header h1 { font-size:16px; margin:0; }
  header .tag { color:var(--dim); font-size:12px; }
  select, button { background:var(--panel); color:var(--ink);
    border:1px solid #2a2e37; border-radius:6px; padding:6px 12px;
    font-size:13px; cursor:pointer; }
  button#run { background:var(--accent); color:#10121a; font-weight:600; }
  button:disabled { opacity:.5; cursor:wait; }
  main { flex:1; display:flex; min-height:0; }
  textarea { flex:1; background:var(--bg); color:var(--ink); border:none;
    resize:none; padding:14px; font:13px/1.5 ui-monospace, Consolas,
    monospace; outline:none; }
  #out { flex:1; background:var(--panel); margin:0; padding:14px;
    overflow:auto; font:13px/1.5 ui-monospace, Consolas, monospace;
    white-space:pre-wrap; border-left:1px solid #2a2e37; }
  .err { color: var(--err); } .note { color: var(--dim); }
  @media (max-width: 800px) { main { flex-direction:column; }
    #out { border-left:none; border-top:1px solid #2a2e37; } }
</style>
</head>
<body>
<header>
  <h1>Velaris</h1>
  <span class="tag">the language where you can trust code you didn't
  write &mdash; running entirely in your browser</span>
  <select id="examples"></select>
  <button id="run" disabled>loading&hellip;</button>
</header>
<main>
  <textarea id="code" spellcheck="false"></textarea>
  <pre id="out"><span class="note">Loading Python runtime (first visit
takes a few seconds)&hellip;

Note: in the browser, promises (requires/ensures/invariant) are checked
while the program runs. The installed version also PROVES them before
running, using the Z3 theorem prover, and compiles hot functions to
native code with LLVM. github.com/gowrishankar-infra/velaris-lang</span></pre>
</main>
<script>
const VELARIS_SRC = __SRC__;
const EXAMPLES = __EXAMPLES__;

const sel = document.getElementById("examples");
const code = document.getElementById("code");
const out = document.getElementById("out");
const runBtn = document.getElementById("run");

for (const name of Object.keys(EXAMPLES)) {
  const o = document.createElement("option");
  o.value = name; o.textContent = name;
  sel.appendChild(o);
}
code.value = EXAMPLES[Object.keys(EXAMPLES)[0]];
sel.onchange = () => { code.value = EXAMPLES[sel.value]; };

let pyodide = null;
async function boot() {
  pyodide = await loadPyodide();
  pyodide.setStdin({ stdin: () => window.prompt("the program asks:") });
  pyodide.FS.writeFile("/velaris.py", VELARIS_SRC);
  runBtn.disabled = false;
  runBtn.textContent = "Run \\u25B6";
  out.innerHTML = '<span class="note">Ready. Pick an example or write ' +
    'your own, then press Run.</span>';
}

async function run() {
  runBtn.disabled = true; runBtn.textContent = "running\\u2026";
  out.textContent = "";
  pyodide.FS.writeFile("/prog.vel", code.value);
  const py = `
import importlib.util, io, json, sys
from contextlib import redirect_stdout, redirect_stderr
spec = importlib.util.spec_from_file_location("velaris", "/velaris.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
sys.argv = ["velaris.py", "/prog.vel", "--no-native"]
o, e = io.StringIO(), io.StringIO()
try:
    with redirect_stdout(o), redirect_stderr(e):
        try:
            mod.main()
        except SystemExit:
            pass
except Exception as ex:
    e.write(f"playground error: {ex}")
json.dumps([o.getvalue(), e.getvalue()])
`;
  try {
    const res = JSON.parse(await pyodide.runPythonAsync(py));
    const [stdout, stderr] = res;
    out.textContent = "";
    if (stdout) out.append(stdout);
    if (stderr) {
      const s = document.createElement("span");
      s.className = "err"; s.textContent = stderr;
      out.appendChild(s);
    }
    if (!stdout && !stderr) {
      out.innerHTML = '<span class="note">(no output)</span>';
    }
  } catch (err) {
    out.innerHTML = '<span class="err">playground error: ' + err + '</span>';
  }
  runBtn.disabled = false; runBtn.textContent = "Run \\u25B6";
}
runBtn.onclick = run;
</script>
<script src="https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js"
        onload="boot()"></script>
</body>
</html>
"""

html = TEMPLATE.replace("__SRC__", json.dumps(SRC)) \
               .replace("__EXAMPLES__", json.dumps(EXAMPLES))
outdir = HERE / "playground"
outdir.mkdir(exist_ok=True)
(outdir / "index.html").write_text(html, encoding="utf-8")
print(f"playground/index.html written ({len(html)//1024} KB)")
