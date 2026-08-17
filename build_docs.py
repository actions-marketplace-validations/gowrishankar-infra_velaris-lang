#!/usr/bin/env python3
"""Generate the Velaris documentation site into docs/.

Pages: index (pitch + quickstart), tutorial (from TUTORIAL.md),
library (parsed from stdlib/std.vel BY THE REAL COMPILER, contracts
included), errors (every E-code scraped from velaris.py), and the
playground. Rebuild with:  python build_docs.py
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import velaris  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "docs"
OUT.mkdir(exist_ok=True)

STYLE = """
:root { --bg:#14161a; --panel:#1d2026; --ink:#e8e6e3; --dim:#8a8f98;
        --accent:#7aa2f7; --ok:#9ece6a; --err:#f7768e; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font-family:system-ui,sans-serif; line-height:1.6; }
nav { display:flex; gap:18px; padding:14px 22px; align-items:baseline;
      border-bottom:1px solid #2a2e37; flex-wrap:wrap; }
nav .brand { font-weight:700; font-size:18px; color:var(--ink);
             text-decoration:none; }
nav a { color:var(--dim); text-decoration:none; font-size:14px; }
nav a:hover, nav a.here { color:var(--accent); }
main { max-width:880px; margin:0 auto; padding:28px 22px 80px; }
h1 { font-size:30px; margin:.4em 0; }
h2 { margin-top:1.6em; border-bottom:1px solid #2a2e37;
     padding-bottom:6px; }
code { background:var(--panel); padding:2px 6px; border-radius:5px;
       font:13px ui-monospace,Consolas,monospace; }
pre { background:var(--panel); padding:14px 16px; border-radius:9px;
      overflow-x:auto; }
pre code { background:none; padding:0; }
.tag { color:var(--dim); }
.sig { color:var(--accent); font:14px ui-monospace,Consolas,monospace; }
.contract { color:var(--ok); font:13px ui-monospace,Consolas,monospace;
            margin-left:22px; }
.card { background:var(--panel); border-radius:10px; padding:16px 18px;
        margin:14px 0; }
.ecode { color:var(--err); font-weight:600;
         font-family:ui-monospace,Consolas,monospace; }
table { border-collapse:collapse; width:100%; }
td, th { border-bottom:1px solid #2a2e37; padding:8px 10px;
         text-align:left; font-size:14px; vertical-align:top; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,
        minmax(240px,1fr)); gap:14px; margin:22px 0; }
a { color:var(--accent); }
"""

PAGES = [("index.html", "Home"), ("tutorial.html", "Tutorial"),
         ("library.html", "Library"), ("errors.html", "Errors"),
         ("playground.html", "Playground")]


def shell(title: str, here: str, body: str) -> str:
    links = "".join(
        f'<a href="{p}" class="{"here" if p == here else ""}">{n}</a>'
        for p, n in PAGES)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} - Velaris</title>
<style>{STYLE}</style></head><body>
<nav><a class="brand" href="index.html">Velaris</a>{links}
<span class="tag">v{velaris.VERSION}</span></nav>
<main>{body}</main></body></html>"""


def md_to_html(md: str) -> str:
    out, in_code = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            out.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        e = html.escape(line)
        e = re.sub(r"`([^`]+)`", r"<code>\1</code>", e)
        e = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", e)
        if e.startswith("### "):
            out.append(f"<h3>{e[4:]}</h3>")
        elif e.startswith("## "):
            out.append(f"<h2>{e[3:]}</h2>")
        elif e.startswith("# "):
            out.append(f"<h1>{e[2:]}</h1>")
        elif e.startswith("- "):
            out.append(f"<li>{e[2:]}</li>")
        elif e.strip() == "":
            out.append("<br>")
        else:
            out.append(f"<p>{e}</p>")
    return "\n".join(out)


def fn_signature(f) -> str:
    ps = ", ".join(f"{n}: {t}" for n, t in f.params)
    sig = f"fn {f.name}({ps})"
    if f.return_type and f.return_type != "Unit":
        sig += f" -> {f.return_type}"
    if f.type_vars:
        sig += " for any " + ", ".join(f.type_vars)
    if f.can_fail:
        sig += " or fail"
    if f.effects:
        sig += " uses " + ", ".join(sorted(f.effects))
    return sig


def library_page() -> str:
    funcs, _ = velaris.load_program(str(HERE / "stdlib" / "std.vel"))
    body = ["<h1>The standard library</h1>",
            "<p>Every function below is written in Velaris "
            "(<code>stdlib/std.vel</code>) and parsed onto this page by "
            "the real compiler &mdash; including its machine-checked "
            "promises. A violated <code>requires</code> is a compile "
            "error at <i>your</i> call site.</p>"]
    for f in funcs:
        body.append('<div class="card">')
        body.append(f'<div class="sig">{html.escape(fn_signature(f))}'
                    '</div>')
        for expr, _ in f.requires:
            body.append(f'<div class="contract">requires '
                        f'{html.escape(velaris.expr_str(expr))}</div>')
        for expr, _ in f.ensures:
            body.append(f'<div class="contract">ensures '
                        f'{html.escape(velaris.expr_str(expr))}</div>')
        body.append("</div>")
    body.append("<h2>Built-in functions</h2><table><tr><th>name</th>"
                "<th>effects</th><th>takes</th><th>gives</th></tr>")
    for name, info in sorted(velaris.BUILTINS.items()):
        eff = ", ".join(sorted(info["effects"])) or "pure"
        fall = (" <span class='ecode'>or fail</span>"
                if name in velaris.FALLIBLE_BUILTINS else "")
        body.append(f"<tr><td><code>{name}</code>{fall}</td>"
                    f"<td>{eff}</td>"
                    f"<td>{html.escape(', '.join(info['types']))}</td>"
                    f"<td>{html.escape(info['ret'])}</td></tr>")
    body.append("</table><p class='tag'>get on a map can also fail "
                "(missing key); get_or never fails.</p>")
    return "\n".join(body)


def errors_page() -> str:
    src = (HERE / "velaris.py").read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for m in re.finditer(
            r'VelarisError\(\s*"(E\d+)",\s*((?:f?"(?:[^"\\]|\\.)*"\s*)+)',
            src):
        code = m.group(1)
        msg = " ".join(re.findall(r'f?"((?:[^"\\]|\\.)*)"', m.group(2)))
        msg = re.sub(r"\s+", " ", msg).strip()
        if code not in found or len(msg) > len(found[code]):
            found[code] = msg
    body = ["<h1>Every error Velaris can give</h1>",
            "<p>Scraped from the compiler source itself, so this list "
            "cannot go stale. Placeholders in braces are filled with "
            "your program's names and values; every error also comes "
            "with numbered fixes.</p><table><tr><th>code</th>"
            "<th>message template</th></tr>"]
    for code in sorted(found):
        body.append(f'<tr><td class="ecode">{code}</td>'
                    f'<td>{html.escape(found[code])}</td></tr>')
    body.append("</table>")
    return "\n".join(body)


def index_page() -> str:
    return f"""
<h1>The language where you can trust code you didn't write.</h1>
<p>A Velaris signature tells you <b>everything</b>: the types, the
effects it may perform, whether it can fail, and promises that are
<b>proven by the Z3 theorem prover before the program runs</b> &mdash;
in genuine IEEE-754 for floats. Pure numeric functions compile to
native code via LLVM.</p>
<div class="grid">
<div class="card"><b>Effects are visible</b><br><span class="tag">A
function without <code>uses net</code> can never touch the network.
Hidden behavior does not compile.</span></div>
<div class="card"><b>Promises are proven</b><br><span class="tag">
<code>ensures result &gt;= 0</code> is checked by Z3 for every possible
input, with exact counterexamples when broken.</span></div>
<div class="card"><b>Failure is unignorable</b><br><span class="tag">
<code>or fail</code> in the signature; forgetting the error path is a
compile error &mdash; builtins included.</span></div>
<div class="card"><b>Fast where it's safe</b><br><span class="tag">
Pure Int/Float/Bool functions run as machine code, verified identical
to the interpreter.</span></div>
</div>
<h2>Sixty seconds of Velaris</h2>
<pre><code>fn discount(price: Int) -&gt; Int
    requires price &gt;= 0
    ensures result &gt;= 0        // PROVEN before running
{{
    return price - 10           // error[E700]: price = 5 gives -5
}}</code></pre>
<h2>Quick start</h2>
<pre><code>pip install ".[full]"
velaris examples/hello.vel
velaris repl</code></pre>
<p>Or skip installing: open the <a href="playground.html">playground
</a> and run Velaris in your browser.</p>"""


(OUT / "index.html").write_text(
    shell("Velaris", "index.html", index_page()), encoding="utf-8")
(OUT / "tutorial.html").write_text(
    shell("Tutorial", "tutorial.html",
          md_to_html((HERE / "TUTORIAL.md").read_text(encoding="utf-8"))),
    encoding="utf-8")
(OUT / "library.html").write_text(
    shell("Library", "library.html", library_page()), encoding="utf-8")
(OUT / "errors.html").write_text(
    shell("Errors", "errors.html", errors_page()), encoding="utf-8")
play = (HERE / "playground" / "index.html").read_text(encoding="utf-8")
(OUT / "playground.html").write_text(play, encoding="utf-8")
n_err = errors_page().count('class="ecode"')
print(f"docs/ written: 5 pages, {n_err} error codes documented")
