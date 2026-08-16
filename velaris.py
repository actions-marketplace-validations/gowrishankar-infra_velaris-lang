#!/usr/bin/env python3
"""
Velaris v0.9 — "The language where you can trust code you didn't write."

New in v0.9: NATIVE SPEED via LLVM. Pure Int math functions (no effects,
    no contracts, no lists/text) are compiled to real machine code and
    run at C-like speed; everything else stays safely interpreted.
    Flags:  --time       show how long the run took
            --no-native  force the interpreter for everything
    (needs: pip install llvmlite ; without it, everything still runs)

New in v0.8: MODULAR proofs - verification composes across functions.
    When A calls B, the prover uses B's promises to prove A's promises,
    and proves A can never violate B's 'requires' at the call site (E701).
New in v0.7: compile-time PROOFS via the Z3 theorem prover.
    For simple functions, broken promises are now proven false and the
    program is rejected BEFORE it runs - with an exact counterexample.
    Functions Z3 cannot handle (loops, lists, text math) safely fall
    back to runtime promise checks, exactly as in v0.5.
    (needs: pip install z3-solver ; without it, runtime checks still guard)
New in v0.6: negative numbers, and / or / not, and lists.
    let scores = [42, -7, 99]
    fn biggest(xs: List of Int) -> Int requires length(xs) > 0 { ... }
New in v0.5: contracts. Functions make promises; Velaris enforces them.
    fn discount(price: Int) -> Int
        requires price >= 0        <- promise about inputs (caller's duty)
        ensures result >= 0        <- promise about output (function's duty)
Contracts must be pure: a promise cannot print, fetch, or write files.
New in v0.4: while loops and changeable variables.
    while i <= n { total = total + i   i = i + 1 }
New in v0.3: full type checking before the program runs.
    add("hello", 5)   -> rejected at compile time, not a runtime crash
New in v0.2: effects split into io, net, fs, clock, rand.

Pipeline:  source text -> LEXER -> tokens -> PARSER -> AST
           -> EFFECT CHECKER (the special part) -> INTERPRETER

Design rules:
  * Plain English keywords: fn, let, return, if, else, uses
  * A function with no `uses` clause is PURE. Pure functions cannot
    print, touch files, or the network — the compiler proves it.
  * Errors are friendly for humans AND structured (JSON) for AI agents.

Usage:
  python3 velaris.py program.vel          # run a program
  python3 velaris.py program.vel --json   # errors come out as JSON too
"""

import json
import re
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 1. LEXER — turn raw text into a list of tokens
# ---------------------------------------------------------------------------

KEYWORDS = {"fn", "let", "return", "if", "else", "uses", "true", "false", "while", "requires", "ensures", "and", "or", "not"}

TOKEN_SPEC = [
    ("COMMENT", r"//[^\n]*"),
    ("NEWLINE", r"\n"),
    ("SKIP",    r"[ \t\r]+"),
    ("ARROW",   r"->"),
    ("NUMBER",  r"\d+"),
    ("STRING",  r'"[^"\n]*"'),
    ("IDENT",   r"[A-Za-z_][A-Za-z0-9_]*"),
    ("OP",      r"==|!=|<=|>=|[+\-*/<>=(){},:\[\]]"),
]

MASTER_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in TOKEN_SPEC))


@dataclass
class Token:
    kind: str          # NUMBER, STRING, IDENT, KEYWORD, OP, ARROW
    text: str
    line: int


def lex(source: str) -> list[Token]:
    tokens, line = [], 1
    pos = 0
    while pos < len(source):
        m = MASTER_RE.match(source, pos)
        if not m:
            raise VelarisError("E000", f"unexpected character {source[pos]!r}", line,
                              fixes=["remove or replace this character"])
        kind, text = m.lastgroup, m.group()
        pos = m.end()
        if kind == "NEWLINE":
            line += 1
        elif kind in ("SKIP", "COMMENT"):
            pass
        elif kind == "IDENT" and text in KEYWORDS:
            tokens.append(Token("KEYWORD", text, line))
        else:
            tokens.append(Token(kind, text, line))
    tokens.append(Token("EOF", "", line))
    return tokens


# ---------------------------------------------------------------------------
# 2. AST — the tree shapes the parser produces
# ---------------------------------------------------------------------------

@dataclass
class Num:      value: int
@dataclass
class Str:      value: str
@dataclass
class Bool:     value: bool
@dataclass
class Var:      name: str; line: int
@dataclass
class BinOp:    op: str; left: object; right: object; line: int
@dataclass
class Call:     name: str; args: list; line: int
@dataclass
class Let:      name: str; value: object; line: int
@dataclass
class Return:   value: object; line: int
@dataclass
class If:       cond: object; then: list; other: list; line: int
@dataclass
class While:    cond: object; body: list; line: int
@dataclass
class Assign:   name: str; value: object; line: int
@dataclass
class Not:      value: object; line: int
@dataclass
class ListLit:  items: list; line: int
@dataclass
class ExprStmt: expr: object; line: int

@dataclass
class Function:
    name: str
    params: list[tuple[str, str]]      # (name, type)
    return_type: str | None
    effects: set[str]                  # declared with `uses`
    requires: list                     # [(expr, line)] promises about inputs
    ensures: list                      # [(expr, line)] promises about output
    body: list
    line: int


# ---------------------------------------------------------------------------
# Friendly + machine-readable errors
# ---------------------------------------------------------------------------

class VelarisError(Exception):
    def __init__(self, code: str, message: str, line: int, fixes: list[str] | None = None):
        self.code, self.message, self.line = code, message, line
        self.fixes = fixes or []
        super().__init__(message)

    def human(self, filename: str) -> str:
        out = [f"error[{self.code}] {self.message}",
               f"  --> {filename}, line {self.line}"]
        if self.fixes:
            out.append("  how to fix (pick one):")
            for i, f in enumerate(self.fixes, 1):
                out.append(f"    {i}. {f}")
        return "\n".join(out)

    def machine(self, filename: str) -> str:
        return json.dumps({
            "code": self.code, "message": self.message,
            "file": filename, "line": self.line, "fixes": self.fixes,
        }, indent=2)


# ---------------------------------------------------------------------------
# 3. PARSER — recursive descent, one function per grammar rule
# ---------------------------------------------------------------------------

class Parser:
    def __init__(self, tokens: list[Token]):
        self.toks = tokens
        self.i = 0

    def peek(self) -> Token: return self.toks[self.i]
    def next(self) -> Token:
        t = self.toks[self.i]; self.i += 1; return t

    def expect(self, kind: str, text: str | None = None) -> Token:
        t = self.peek()
        if t.kind != kind or (text is not None and t.text != text):
            want = text or kind.lower()
            raise VelarisError("E100", f"expected '{want}' but found '{t.text or 'end of file'}'",
                              t.line, fixes=[f"insert '{want}' here"])
        return self.next()

    def parse_program(self) -> list[Function]:
        funcs = []
        while self.peek().kind != "EOF":
            funcs.append(self.parse_function())
        return funcs

    def parse_function(self) -> Function:
        start = self.expect("KEYWORD", "fn")
        name = self.expect("IDENT").text
        self.expect("OP", "(")
        params = []
        while self.peek().text != ")":
            pname = self.expect("IDENT").text
            self.expect("OP", ":")
            ptype = self.parse_type()
            params.append((pname, ptype))
            if self.peek().text == ",":
                self.next()
        self.expect("OP", ")")
        ret = None
        if self.peek().kind == "ARROW":
            self.next()
            ret = self.parse_type()
        effects: set[str] = set()
        if self.peek().kind == "KEYWORD" and self.peek().text == "uses":
            self.next()
            effects.add(self.expect("IDENT").text)
            while self.peek().text == ",":
                self.next()
                effects.add(self.expect("IDENT").text)
        requires_, ensures_ = [], []
        while (self.peek().kind == "KEYWORD"
               and self.peek().text in ("requires", "ensures")):
            kw = self.next()
            clause = (self.parse_expr(), kw.line)
            (requires_ if kw.text == "requires" else ensures_).append(clause)
        body = self.parse_block()
        return Function(name, params, ret, effects, requires_, ensures_,
                        body, start.line)

    def parse_block(self) -> list:
        self.expect("OP", "{")
        stmts = []
        while self.peek().text != "}":
            stmts.append(self.parse_statement())
        self.expect("OP", "}")
        return stmts

    def parse_statement(self):
        t = self.peek()
        if t.kind == "KEYWORD" and t.text == "let":
            self.next()
            name = self.expect("IDENT").text
            self.expect("OP", "=")
            return Let(name, self.parse_expr(), t.line)
        if t.kind == "KEYWORD" and t.text == "return":
            self.next()
            if self.peek().text == "}":          # bare 'return' with no value
                return Return(None, t.line)
            return Return(self.parse_expr(), t.line)
        if t.kind == "KEYWORD" and t.text == "while":
            self.next()
            cond = self.parse_expr()
            body = self.parse_block()
            return While(cond, body, t.line)
        if t.kind == "IDENT" and self.toks[self.i + 1].text == "=":
            self.next()
            self.expect("OP", "=")
            return Assign(t.text, self.parse_expr(), t.line)
        if t.kind == "KEYWORD" and t.text == "if":
            self.next()
            cond = self.parse_expr()
            then = self.parse_block()
            other = []
            if self.peek().text == "else":
                self.next()
                other = self.parse_block()
            return If(cond, then, other, t.line)
        return ExprStmt(self.parse_expr(), t.line)

    def parse_type(self) -> str:
        t = self.expect("IDENT")
        if t.text == "List":
            of = self.expect("IDENT")
            if of.text != "of":
                raise VelarisError("E100", "expected 'of' after 'List'", of.line,
                                  fixes=["write list types like: List of Int"])
            inner = self.expect("IDENT").text
            return "List of " + inner
        return t.text

    # expressions: or -> and -> not -> comparison -> add/sub -> mul/div -> atoms
    def parse_expr(self):
        left = self.parse_and()
        while self.peek().kind == "KEYWORD" and self.peek().text == "or":
            op = self.next()
            left = BinOp("or", left, self.parse_and(), op.line)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.peek().kind == "KEYWORD" and self.peek().text == "and":
            op = self.next()
            left = BinOp("and", left, self.parse_not(), op.line)
        return left

    def parse_not(self):
        t = self.peek()
        if t.kind == "KEYWORD" and t.text == "not":
            self.next()
            return Not(self.parse_not(), t.line)
        return self.parse_cmp()

    def parse_cmp(self):
        left = self.parse_add()
        while self.peek().text in ("==", "!=", "<", ">", "<=", ">="):
            op = self.next()
            left = BinOp(op.text, left, self.parse_add(), op.line)
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.peek().text in ("+", "-"):
            op = self.next()
            left = BinOp(op.text, left, self.parse_mul(), op.line)
        return left

    def parse_mul(self):
        left = self.parse_atom()
        while self.peek().text in ("*", "/"):
            op = self.next()
            left = BinOp(op.text, left, self.parse_atom(), op.line)
        return left

    def parse_atom(self):
        t = self.next()
        if t.text == "-":                      # negative numbers: -7, -x
            return BinOp("-", Num(0), self.parse_atom(), t.line)
        if t.text == "[":                      # list literal: [1, 2, 3]
            items = []
            while self.peek().text != "]":
                items.append(self.parse_expr())
                if self.peek().text == ",":
                    self.next()
            self.expect("OP", "]")
            return ListLit(items, t.line)
        if t.kind == "NUMBER":
            return Num(int(t.text))
        if t.kind == "STRING":
            return Str(t.text[1:-1])
        if t.kind == "KEYWORD" and t.text in ("true", "false"):
            return Bool(t.text == "true")
        if t.text == "(":
            e = self.parse_expr()
            self.expect("OP", ")")
            return e
        if t.kind == "IDENT":
            if self.peek().text == "(":            # function call
                self.next()
                args = []
                while self.peek().text != ")":
                    args.append(self.parse_expr())
                    if self.peek().text == ",":
                        self.next()
                self.expect("OP", ")")
                return Call(t.text, args, t.line)
            return Var(t.text, t.line)
        raise VelarisError("E101", f"unexpected '{t.text}'", t.line,
                          fixes=["expected a number, string, variable, or function call"])


def expr_str(e) -> str:
    """Turn an AST expression back into readable source text (for errors)."""
    if isinstance(e, Num):  return str(e.value)
    if isinstance(e, Str):  return f'"{e.value}"'
    if isinstance(e, Bool): return "true" if e.value else "false"
    if isinstance(e, Var):  return e.name
    if isinstance(e, Call): return f"{e.name}({', '.join(expr_str(a) for a in e.args)})"
    if isinstance(e, BinOp): return f"{expr_str(e.left)} {e.op} {expr_str(e.right)}"
    if isinstance(e, Not):   return f"not {expr_str(e.value)}"
    if isinstance(e, ListLit): return "[" + ", ".join(expr_str(i) for i in e.items) + "]"
    return "?"


def expr_vars(e) -> set[str]:
    if isinstance(e, Var):   return {e.name}
    if isinstance(e, Not):   return expr_vars(e.value)
    if isinstance(e, ListLit):
        out = set()
        for i in e.items:
            out |= expr_vars(i)
        return out
    if isinstance(e, BinOp): return expr_vars(e.left) | expr_vars(e.right)
    if isinstance(e, Call):
        out = set()
        for a in e.args:
            out |= expr_vars(a)
        return out
    return set()


# ---------------------------------------------------------------------------
# 4. EFFECT CHECKER — the heart of Velaris
#    Rule: a function may only cause effects it declares with `uses`.
# ---------------------------------------------------------------------------

BUILTINS = {
    # name          effects needed      argument types        returns
    "print":      {"effects": {"io"},    "types": ["Any"],         "ret": "Unit"},
    "read_file":  {"effects": {"fs"},    "types": ["Text"],        "ret": "Text"},
    "write_file": {"effects": {"fs"},    "types": ["Text", "Any"], "ret": "Unit"},
    "fetch":      {"effects": {"net"},   "types": ["Text"],        "ret": "Text"},
    "now":        {"effects": {"clock"}, "types": [],              "ret": "Int"},
    "random":     {"effects": {"rand"},  "types": ["Int"],         "ret": "Int"},
    # pure helpers (no effects) - usable everywhere, including promises
    "length":     {"effects": set(),      "types": ["Any"],         "ret": "Int"},
    "push":       {"effects": set(),      "types": ["Any", "Any"],  "ret": "Any"},
    "get":        {"effects": set(),      "types": ["Any", "Any"],  "ret": "Any"},
}

KNOWN_TYPES = {"Int", "Text", "Bool"}

def check_effects(funcs: list[Function]) -> None:
    table = {f.name: f for f in funcs}

    def effects_of_callee(name: str, line: int) -> set[str]:
        if name in BUILTINS:
            return BUILTINS[name]["effects"]
        if name in table:
            return table[name].effects
        raise VelarisError("E200", f"unknown function '{name}'", line,
                          fixes=[f"define 'fn {name}(...)' somewhere",
                                 "check the spelling of the name"])

    def walk(node, fn: Function):
        if isinstance(node, Call):
            needed = effects_of_callee(node.name, node.line)
            missing = needed - fn.effects
            if missing:
                eff = ", ".join(sorted(missing))
                declared = ("declares no effects (it is pure)" if not fn.effects
                            else f"only declares 'uses {', '.join(sorted(fn.effects))}'")
                raise VelarisError(
                    "E300",
                    f"function '{fn.name}' calls '{node.name}' which needs "
                    f"effect '{eff}', but '{fn.name}' {declared}",
                    node.line,
                    fixes=[f"add 'uses {eff}' to the signature of '{fn.name}'",
                           f"remove the call to '{node.name}'"],
                )
            for a in node.args:
                walk(a, fn)
        elif isinstance(node, BinOp):
            walk(node.left, fn); walk(node.right, fn)
        elif isinstance(node, (Let, Return, ExprStmt)):
            inner = node.expr if isinstance(node, ExprStmt) else node.value
            if inner is not None:
                walk(inner, fn)
        elif isinstance(node, If):
            walk(node.cond, fn)
            for s in node.then + node.other:
                walk(s, fn)
        elif isinstance(node, While):
            walk(node.cond, fn)
            for s in node.body:
                walk(s, fn)
        elif isinstance(node, Assign):
            walk(node.value, fn)
        elif isinstance(node, Not):
            walk(node.value, fn)
        elif isinstance(node, ListLit):
            for it in node.items:
                walk(it, fn)

    def walk_pure(node, fn: Function, where: str):
        if isinstance(node, Call):
            eff = effects_of_callee(node.name, node.line)
            if eff:
                raise VelarisError("E310",
                    f"the '{where}' promise of '{fn.name}' calls "
                    f"'{node.name}' which has effects "
                    f"({', '.join(sorted(eff))}); promises must be pure",
                    node.line,
                    fixes=["only use pure functions and math inside promises"])
            for a in node.args:
                walk_pure(a, fn, where)
        elif isinstance(node, BinOp):
            walk_pure(node.left, fn, where)
            walk_pure(node.right, fn, where)
        elif isinstance(node, Not):
            walk_pure(node.value, fn, where)
        elif isinstance(node, ListLit):
            for it in node.items:
                walk_pure(it, fn, where)

    for fn in funcs:
        for stmt in fn.body:
            walk(stmt, fn)
        for expr, _ in fn.requires:
            walk_pure(expr, fn, "requires")
        for expr, _ in fn.ensures:
            walk_pure(expr, fn, "ensures")


# ---------------------------------------------------------------------------
# 4b. TYPE CHECKER — catch wrong-type bugs before the program ever runs
#     Types: Int, Text, Bool.  "Unit" means "returns nothing".
# ---------------------------------------------------------------------------

def check_types(funcs: list[Function]) -> None:
    table = {f.name: f for f in funcs}

    def callee_sig(name: str) -> tuple[list[str], str]:
        if name in BUILTINS:
            return BUILTINS[name]["types"], BUILTINS[name]["ret"]
        f = table[name]
        return [t for _, t in f.params], (f.return_type or "Unit")

    def valid_type(t: str) -> bool:
        if t in KNOWN_TYPES:
            return True
        return t.startswith("List of ") and t[len("List of "):] in KNOWN_TYPES

    TYPE_HINT = "use Int, Text, Bool, or List of <one of those>"

    # first: every declared type must be a real type
    for f in funcs:
        for pname, ptype in f.params:
            if not valid_type(ptype):
                raise VelarisError("E500", f"unknown type '{ptype}' for parameter "
                                  f"'{pname}' of '{f.name}'", f.line,
                                  fixes=[TYPE_HINT])
        if f.return_type is not None and not valid_type(f.return_type):
            raise VelarisError("E500", f"unknown return type '{f.return_type}' "
                              f"for '{f.name}'", f.line,
                              fixes=[TYPE_HINT])

    def check_fn(fn: Function) -> None:
        env = dict(fn.params)                       # variable -> type
        declared_ret = fn.return_type or "Unit"

        def infer(node) -> str:
            if isinstance(node, Num):  return "Int"
            if isinstance(node, Str):  return "Text"
            if isinstance(node, Bool): return "Bool"
            if isinstance(node, Var):
                if node.name not in env:
                    raise VelarisError("E402", f"unknown variable '{node.name}'",
                                      node.line,
                                      fixes=[f"declare it first: let {node.name} = ..."])
                return env[node.name]
            if isinstance(node, Not):
                t = infer(node.value)
                if t != "Bool":
                    raise VelarisError("E501",
                        f"'not' needs a yes/no value (Bool), but this is {t}",
                        node.line, fixes=["use it on a comparison like not (x > 0)"])
                return "Bool"
            if isinstance(node, ListLit):
                if not node.items:
                    raise VelarisError("E506",
                        "cannot tell what an empty list holds", node.line,
                        fixes=["put at least one item in it, e.g. [0]"])
                t0 = infer(node.items[0])
                for it in node.items[1:]:
                    t = infer(it)
                    if t != t0:
                        raise VelarisError("E501",
                            f"a list cannot mix {t0} and {t}", node.line,
                            fixes=["keep every item in a list the same type"])
                return "List of " + t0
            if isinstance(node, Call) and node.name in ("length", "push", "get"):
                n_want = 1 if node.name == "length" else 2
                if len(node.args) != n_want:
                    raise VelarisError("E401",
                        f"'{node.name}' expects {n_want} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {n_want} argument(s)"])
                t0 = infer(node.args[0])
                if node.name == "length":
                    if t0 == "Text" or t0.startswith("List of "):
                        return "Int"
                    raise VelarisError("E501",
                        f"'length' works on Text or a list, but this is {t0}",
                        node.line, fixes=["pass a Text value or a list"])
                if not t0.startswith("List of "):
                    raise VelarisError("E501",
                        f"'{node.name}' needs a list first, but this is {t0}",
                        node.line, fixes=["pass a list as the first argument"])
                elem = t0[len("List of "):]
                t1 = infer(node.args[1])
                if node.name == "push":
                    if t1 != elem:
                        raise VelarisError("E501",
                            f"this list holds {elem}, cannot push a {t1} into it",
                            node.line, fixes=[f"push {'an' if elem == 'Int' else 'a'} {elem} value"])
                    return t0
                if t1 != "Int":                      # get
                    raise VelarisError("E501",
                        f"'get' needs an Int position, but this is {t1}",
                        node.line, fixes=["positions are numbers, e.g. get(xs, 0)"])
                return elem
            if isinstance(node, Call):
                ptypes, ret = callee_sig(node.name)
                if len(node.args) != len(ptypes):
                    raise VelarisError("E401",
                        f"'{node.name}' expects {len(ptypes)} argument(s) "
                        f"but got {len(node.args)}", node.line,
                        fixes=[f"pass exactly {len(ptypes)} argument(s)"])
                for i, (arg, want) in enumerate(zip(node.args, ptypes), 1):
                    got = infer(arg)
                    if got == "Unit":
                        raise VelarisError("E502",
                            f"argument {i} of '{node.name}' is a call to a "
                            f"function that returns nothing", node.line,
                            fixes=["call a function that returns a value here"])
                    if want != "Any" and got != want:
                        raise VelarisError("E501",
                            f"'{node.name}' needs {want} for argument {i}, "
                            f"but this is {got}", node.line,
                            fixes=[f"pass {'an' if want == 'Int' else 'a'} {want} value instead",
                                   f"or change the parameter type to {got}"])
                return ret
            if isinstance(node, BinOp):
                l, r = infer(node.left), infer(node.right)
                if "Unit" in (l, r):
                    raise VelarisError("E502",
                        "this expression uses a function that returns nothing",
                        node.line, fixes=["only use functions that return a value in math/text"])
                op = node.op
                if op in ("and", "or"):
                    if l == "Bool" and r == "Bool":
                        return "Bool"
                    raise VelarisError("E501",
                        f"'{op}' needs yes/no values (Bool) on both sides, "
                        f"but this is {l} {op} {r}", node.line,
                        fixes=["use comparisons on both sides, like x > 0 and x < 10"])
                if op == "+":
                    if l == "Text" or r == "Text":
                        return "Text"                  # text joining, e.g. "n: " + 5
                    if l == "Int" and r == "Int":
                        return "Int"
                    raise VelarisError("E501", f"cannot add {l} and {r}", node.line,
                                      fixes=["'+' works on Int + Int, or joins Text"])
                if op in ("-", "*", "/"):
                    if l == "Int" and r == "Int":
                        return "Int"
                    raise VelarisError("E501",
                        f"'{op}' needs Int on both sides, but this is {l} {op} {r}",
                        node.line, fixes=["make both sides Int"])
                if op in ("<", ">", "<=", ">="):
                    if l == "Int" and r == "Int":
                        return "Bool"
                    raise VelarisError("E501",
                        f"'{op}' compares numbers, but this is {l} {op} {r}",
                        node.line, fixes=["make both sides Int"])
                if l != r:                             # == and !=
                    raise VelarisError("E501",
                        f"cannot compare {l} with {r}", node.line,
                        fixes=["compare values of the same type"])
                return "Bool"

        def check_stmt(node) -> None:
            if isinstance(node, Let):
                t = infer(node.value)
                if t == "Unit":
                    raise VelarisError("E502",
                        f"'{node.name}' would hold nothing: that function "
                        f"returns no value", node.line,
                        fixes=["assign a function that returns a value"])
                env[node.name] = t
            elif isinstance(node, Return):
                if node.value is None:
                    if declared_ret != "Unit":
                        raise VelarisError("E503",
                            f"'{fn.name}' promises to return {declared_ret} "
                            f"but this return gives nothing", node.line,
                            fixes=[f"return a {declared_ret} value"])
                    return
                t = infer(node.value)
                if declared_ret == "Unit":
                    raise VelarisError("E503",
                        f"'{fn.name}' does not declare a return type "
                        f"but returns a {t}", node.line,
                        fixes=[f"add '-> {t}' to the signature of '{fn.name}'",
                               "or remove the returned value"])
                if t != declared_ret:
                    raise VelarisError("E503",
                        f"'{fn.name}' promises to return {declared_ret} "
                        f"but this returns {t}", node.line,
                        fixes=[f"return a {declared_ret} value",
                               f"or change the signature to '-> {t}'"])
            elif isinstance(node, ExprStmt):
                infer(node.expr)
            elif isinstance(node, If):
                c = infer(node.cond)
                if c != "Bool":
                    raise VelarisError("E504",
                        f"'if' needs a yes/no condition (Bool), but this is {c}",
                        node.line, fixes=["use a comparison like x > 0"])
                for s in node.then + node.other:
                    check_stmt(s)
            elif isinstance(node, While):
                c = infer(node.cond)
                if c != "Bool":
                    raise VelarisError("E504",
                        f"'while' needs a yes/no condition (Bool), but this is {c}",
                        node.line, fixes=["use a comparison like i < 10"])
                for s in node.body:
                    check_stmt(s)
            elif isinstance(node, Assign):
                if node.name not in env:
                    raise VelarisError("E402",
                        f"unknown variable '{node.name}'", node.line,
                        fixes=[f"declare it first: let {node.name} = ..."])
                t = infer(node.value)
                have = env[node.name]
                if t != have:
                    raise VelarisError("E501",
                        f"'{node.name}' holds {have}, cannot put a {t} in it",
                        node.line,
                        fixes=[f"assign {'an' if have == 'Int' else 'a'} {have} value",
                               f"or make a new variable: let {node.name}2 = ..."])

        # contracts are checked first, while env holds exactly the parameters
        for expr, cline in fn.requires:
            if infer(expr) != "Bool":
                raise VelarisError("E505",
                    f"'requires' must be a yes/no promise (Bool)", cline,
                    fixes=["use a comparison like price >= 0"])
        if fn.ensures:
            if declared_ret != "Unit":
                env["result"] = declared_ret
            for expr, cline in fn.ensures:
                if infer(expr) != "Bool":
                    raise VelarisError("E505",
                        f"'ensures' must be a yes/no promise (Bool)", cline,
                        fixes=["use a comparison like result >= 0"])
            env.pop("result", None)

        for stmt in fn.body:
            check_stmt(stmt)

    for fn in funcs:
        check_fn(fn)


# ---------------------------------------------------------------------------
# 4c. PROOF CHECKER (v0.8: modular) — proofs now COMPOSE across functions.
#     * When A calls B, the prover uses B's contract as a summary of B:
#       it assumes B's 'ensures' about the result, and PROVES that A always
#       satisfies B's 'requires' at the call site (error E701 if not).
#     * Sound because Velaris has no global state: a call cannot silently
#       change the caller's variables.
#     * Anything unprovable (loops, lists, text math) falls back silently
#       to runtime promise checks.
# ---------------------------------------------------------------------------

def check_proofs(funcs: list[Function]) -> None:
    try:
        import z3
    except ImportError:
        print("note: z3-solver is not installed, so promises are checked "
              "while running instead of proven beforehand "
              "(install with: pip install z3-solver)", file=sys.stderr)
        return

    table = {f.name: f for f in funcs}

    class Unprovable(Exception):
        pass

    FELL_OFF = object()
    counter = [0]

    def mk(name: str, t: str):
        return z3.Int(name) if t == "Int" else z3.Bool(name)

    def fresh(t: str, base: str):
        counter[0] += 1
        return mk(f"__{base}_result_{counter[0]}", t)

    class Ctx:
        """Per-path proof state: path conditions + facts assumed so far.
        param_assum holds only facts about the caller's own parameters
        (never about summarized call results), so violations proven from
        it alone are guaranteed real - never false alarms."""
        def __init__(self, conds, assum, param_assum, caller):
            self.conds, self.assum = conds, assum
            self.param_assum, self.caller = param_assum, caller

        def fork(self, extra):
            return Ctx(self.conds + [extra], list(self.assum),
                       list(self.param_assum), self.caller)

    def has_fresh(e) -> bool:
        """Does this Z3 expression mention a summarized call result?"""
        if z3.is_const(e) and e.decl().name().startswith("__"):
            return True
        return any(has_fresh(c) for c in e.children())

    def bind_params(fnB: Function, args_z3: list) -> dict:
        return {pname: a for (pname, _), a in zip(fnB.params, args_z3)}

    def check_requires_at(fnB, args_z3, ctx, line):
        """Prove the caller always satisfies fnB's requires here (E701)."""
        for r_expr, _ in fnB.requires:
            try:
                need = to_z3(r_expr, bind_params(fnB, args_z3), None)
            except Unprovable:
                continue
            if any(has_fresh(a) for a in args_z3) or \
                    any(has_fresh(c) for c in ctx.conds):
                continue        # could be a false alarm; runtime will guard
            solver = z3.Solver()
            solver.set("timeout", 3000)
            solver.add(*ctx.param_assum)
            solver.add(*ctx.conds)
            solver.add(z3.Not(need))
            if solver.check() == z3.sat:
                m = solver.model()
                vals = ", ".join(
                    f"{pname} = {m.eval(a, model_completion=True)}"
                    for (pname, _), a in zip(fnB.params, args_z3))
                raise VelarisError("E701",
                    f"this call can break a promise: '{fnB.name}' requires "
                    f"{expr_str(r_expr)}, but '{ctx.caller}' can call it "
                    f"with {vals} - proven without running the program",
                    line,
                    fixes=["make sure the value meets the promise before "
                           "calling",
                           "or strengthen the caller's own 'requires' to "
                           "rule this out"])

    def summarize_call(node: Call, env, ctx):
        """Model a call to a pure user function by its contract."""
        fnB = table.get(node.name)
        if (fnB is None or fnB.effects
                or fnB.return_type not in ("Int", "Bool")
                or any(pt not in ("Int", "Bool") for _, pt in fnB.params)):
            raise Unprovable()
        args_z3 = [to_z3(a, env, ctx) for a in node.args]
        check_requires_at(fnB, args_z3, ctx, node.line)
        rv = fresh(fnB.return_type, fnB.name)
        for ens_expr, _ in fnB.ensures:
            e2 = bind_params(fnB, args_z3)
            e2["result"] = rv
            try:
                ctx.assum.append(to_z3(ens_expr, e2, None))
            except Unprovable:
                pass
        return rv

    def to_z3(node, env, ctx):
        if isinstance(node, Num):  return z3.IntVal(node.value)
        if isinstance(node, Bool): return z3.BoolVal(node.value)
        if isinstance(node, Var):
            if node.name not in env:
                raise Unprovable()
            return env[node.name]
        if isinstance(node, Not):
            return z3.Not(to_z3(node.value, env, ctx))
        if isinstance(node, Call):
            if ctx is None:            # inside a contract: no call summaries
                raise Unprovable()
            return summarize_call(node, env, ctx)
        if isinstance(node, BinOp):
            op = node.op
            if op == "and":
                return z3.And(to_z3(node.left, env, ctx),
                              to_z3(node.right, env, ctx))
            if op == "or":
                return z3.Or(to_z3(node.left, env, ctx),
                             to_z3(node.right, env, ctx))
            l = to_z3(node.left, env, ctx)
            r = to_z3(node.right, env, ctx)
            if op == "+":  return l + r
            if op == "-":  return l - r
            if op == "*":  return l * r
            if op == "==": return l == r
            if op == "!=": return l != r
            if op == "<":  return l < r
            if op == ">":  return l > r
            if op == "<=": return l <= r
            if op == ">=": return l >= r
        raise Unprovable()             # Str, ListLit, '/', anything else

    def scan_calls(node, env, ctx):
        """Inside expressions we cannot fully model (like text joining),
        still find user-function calls and prove their requires hold."""
        if isinstance(node, Call):
            for a in node.args:
                scan_calls(a, env, ctx)
            fnB = table.get(node.name)
            if (fnB is not None and fnB.requires
                    and len(fnB.params) == len(node.args)
                    and all(pt in ("Int", "Bool") for _, pt in fnB.params)):
                try:
                    args_z3 = [to_z3(a, env, ctx) for a in node.args]
                except Unprovable:
                    return
                check_requires_at(fnB, args_z3, ctx, node.line)
        elif isinstance(node, BinOp):
            scan_calls(node.left, env, ctx)
            scan_calls(node.right, env, ctx)
        elif isinstance(node, Not):
            scan_calls(node.value, env, ctx)
        elif isinstance(node, ListLit):
            for it in node.items:
                scan_calls(it, env, ctx)

    def explore(stmts, env, ctx):
        i = 0
        while i < len(stmts):
            s = stmts[i]
            if isinstance(s, (Let, Assign)):
                env[s.name] = to_z3(s.value, env, ctx)
            elif isinstance(s, Return):
                r = FELL_OFF if s.value is None else to_z3(s.value, env, ctx)
                return [(ctx, r)]
            elif isinstance(s, If):
                c = to_z3(s.cond, env, ctx)
                rest = stmts[i + 1:]
                yes = explore(list(s.then) + rest, dict(env), ctx.fork(c))
                no = explore(list(s.other) + rest, dict(env),
                             ctx.fork(z3.Not(c)))
                return yes + no
            elif isinstance(s, ExprStmt):
                try:
                    to_z3(s.expr, env, ctx)
                except Unprovable:
                    scan_calls(s.expr, env, ctx)   # still verify call sites
            else:
                raise Unprovable()                 # while-loops etc.
            i += 1
        return [(ctx, FELL_OFF)]

    for fn in funcs:
        env = {}
        for pname, ptype in fn.params:
            if ptype in ("Int", "Bool"):
                env[pname] = mk(pname, ptype)
        ctx = Ctx([], [], [], fn.name)
        try:
            for r_expr, _ in fn.requires:
                try:
                    fact = to_z3(r_expr, dict(env), None)
                    ctx.assum.append(fact)
                    ctx.param_assum.append(fact)
                except Unprovable:
                    pass
            paths = explore(list(fn.body), dict(env), ctx)
            if not fn.ensures:
                continue
            for pctx, ret in paths:
                if ret is FELL_OFF:
                    raise Unprovable()
                for ens_expr, cline in fn.ensures:
                    e2 = dict(env)
                    e2["result"] = ret
                    goal = to_z3(ens_expr, e2, None)
                    solver = z3.Solver()
                    solver.set("timeout", 3000)
                    solver.add(*pctx.assum)
                    solver.add(*pctx.conds)
                    solver.add(z3.Not(goal))
                    verdict = solver.check()
                    if verdict == z3.sat:
                        if has_fresh(ret) or any(has_fresh(c)
                                                 for c in pctx.conds):
                            # counterexample depends on a summarized call:
                            # might be impossible in reality - never claim
                            # "proven"; fall back to runtime checks instead
                            raise Unprovable()
                        m = solver.model()
                        vals = ", ".join(
                            f"{p} = {m.eval(v, model_completion=True)}"
                            for p, v in sorted(env.items()))
                        rv = m.eval(ret, model_completion=True)
                        raise VelarisError("E700",
                            f"promise cannot be kept: '{fn.name}' ensures "
                            f"{expr_str(ens_expr)} - proven without running "
                            f"the program: {vals} gives result = {rv}",
                            cline,
                            fixes=["fix the code so the promise holds for "
                                   "every allowed input",
                                   "or add a 'requires' that rules out "
                                   "such inputs"])
                    if verdict != z3.unsat:
                        raise Unprovable()
        except Unprovable:
            continue                    # runtime promise checks still guard


# ---------------------------------------------------------------------------
# 4d. NATIVE COMPILER (v0.9) — compile pure Int functions to machine code
#     via LLVM. Eligible: params and return are Int; body uses only math,
#     comparisons, and/or/not, if, while, let/assign, and calls to other
#     eligible functions. No effects, no contracts (those must keep their
#     runtime promise checks), no '/', no Text, no lists.
# ---------------------------------------------------------------------------

_NATIVE_KEEPALIVE = []          # prevents the JIT engine being garbage-collected


def native_eligible(funcs: list[Function]) -> set[str]:
    table = {f.name: f for f in funcs}

    def locally_ok(fn: Function):
        if fn.effects or fn.requires or fn.ensures:
            return None
        if fn.return_type != "Int":
            return None
        if any(pt != "Int" for _, pt in fn.params):
            return None
        calls, ok = set(), [True]

        def we(e):
            if isinstance(e, (Num, Bool, Var)):
                return
            if isinstance(e, Not):
                we(e.value)
            elif isinstance(e, BinOp):
                if e.op == "/":
                    ok[0] = False
                else:
                    we(e.left); we(e.right)
            elif isinstance(e, Call):
                if e.name in BUILTINS or e.name not in table:
                    ok[0] = False
                else:
                    calls.add(e.name)
                    for a in e.args:
                        we(a)
            else:
                ok[0] = False          # Str, ListLit

        def ws(s):
            if isinstance(s, (Let, Assign)):
                we(s.value)
            elif isinstance(s, Return):
                if s.value is None:
                    ok[0] = False
                else:
                    we(s.value)
            elif isinstance(s, If):
                we(s.cond)
                for x in s.then + s.other:
                    ws(x)
            elif isinstance(s, While):
                we(s.cond)
                for x in s.body:
                    ws(x)
            elif isinstance(s, ExprStmt):
                we(s.expr)
            else:
                ok[0] = False

        for s in fn.body:
            ws(s)
        return calls if ok[0] else None

    cand = {}
    for f in funcs:
        c = locally_ok(f)
        if c is not None:
            cand[f.name] = c
    changed = True
    while changed:                      # drop anyone calling a non-candidate
        changed = False
        for name in list(cand):
            if not cand[name] <= set(cand):
                del cand[name]
                changed = True
    return set(cand)


def compile_native(funcs: list[Function]) -> dict:
    eligible = native_eligible(funcs)
    if not eligible:
        return {}
    try:
        from llvmlite import ir, binding
    except ImportError:
        print("note: llvmlite is not installed - running fully interpreted "
              "(for native speed: pip install llvmlite)", file=sys.stderr)
        return {}

    i64 = ir.IntType(64)
    module = ir.Module(name="velaris")
    table = {f.name: f for f in funcs}
    llvm_fns = {}
    for name in eligible:
        fn = table[name]
        fty = ir.FunctionType(i64, [i64] * len(fn.params))
        llvm_fns[name] = ir.Function(module, fty, name=name)

    def collect_names(stmts, out):
        for s in stmts:
            if isinstance(s, (Let, Assign)):
                out.add(s.name)
            elif isinstance(s, If):
                collect_names(s.then, out); collect_names(s.other, out)
            elif isinstance(s, While):
                collect_names(s.body, out)

    CMP = {"==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}

    for name in eligible:
        fn = table[name]
        lf = llvm_fns[name]
        entry = lf.append_basic_block("entry")
        b = ir.IRBuilder(entry)
        slots = {}
        names = {p for p, _ in fn.params}
        collect_names(fn.body, names)
        for n in sorted(names):
            slots[n] = b.alloca(i64, name=n)
        for (pname, _), arg in zip(fn.params, lf.args):
            arg.name = pname
            b.store(arg, slots[pname])

        def ee(e):                                  # emit expression -> i64
            if isinstance(e, Num):
                return i64(e.value)
            if isinstance(e, Bool):
                return i64(1 if e.value else 0)
            if isinstance(e, Var):
                return b.load(slots[e.name])
            if isinstance(e, Not):
                return b.xor(ee(e.value), i64(1))
            if isinstance(e, Call):
                return b.call(llvm_fns[e.name], [ee(a) for a in e.args])
            if isinstance(e, BinOp):
                if e.op == "and":
                    return b.and_(ee(e.left), ee(e.right))
                if e.op == "or":
                    return b.or_(ee(e.left), ee(e.right))
                l, r = ee(e.left), ee(e.right)
                if e.op == "+":
                    return b.add(l, r)
                if e.op == "-":
                    return b.sub(l, r)
                if e.op == "*":
                    return b.mul(l, r)
                return b.zext(b.icmp_signed(CMP[e.op], l, r), i64)
            raise AssertionError("unreachable")

        def truthy(e):
            return b.icmp_signed("!=", ee(e), i64(0))

        def es(stmts):                              # emit statements
            for s in stmts:
                if b.block.is_terminated:
                    return
                if isinstance(s, (Let, Assign)):
                    b.store(ee(s.value), slots[s.name])
                elif isinstance(s, Return):
                    b.ret(ee(s.value))
                elif isinstance(s, ExprStmt):
                    ee(s.expr)
                elif isinstance(s, If):
                    bb_then = lf.append_basic_block("then")
                    bb_else = lf.append_basic_block("else")
                    bb_cont = lf.append_basic_block("cont")
                    b.cbranch(truthy(s.cond), bb_then, bb_else)
                    b.position_at_end(bb_then)
                    es(s.then)
                    if not b.block.is_terminated:
                        b.branch(bb_cont)
                    b.position_at_end(bb_else)
                    es(s.other)
                    if not b.block.is_terminated:
                        b.branch(bb_cont)
                    b.position_at_end(bb_cont)
                elif isinstance(s, While):
                    bb_cond = lf.append_basic_block("wcond")
                    bb_body = lf.append_basic_block("wbody")
                    bb_end = lf.append_basic_block("wend")
                    b.branch(bb_cond)
                    b.position_at_end(bb_cond)
                    b.cbranch(truthy(s.cond), bb_body, bb_end)
                    b.position_at_end(bb_body)
                    es(s.body)
                    if not b.block.is_terminated:
                        b.branch(bb_cond)
                    b.position_at_end(bb_end)

        es(fn.body)
        if not b.block.is_terminated:
            b.ret(i64(0))

    for init in ("initialize", "initialize_native_target",
                 "initialize_native_asmprinter"):
        try:                   # each may be required or deprecated,
            getattr(binding, init)()       # depending on llvmlite version
        except (RuntimeError, AttributeError):
            pass
    target = binding.Target.from_default_triple()
    tm = target.create_target_machine(opt=3)
    backing = binding.parse_assembly(str(module))
    backing.verify()
    try:                                    # optimize IR if this API exists
        pto = binding.create_pipeline_tuning_options()
        pto.speed_level = 3
        pb = binding.create_pass_builder(tm, pto)
        pb.getModulePassManager().run(backing, pb)
    except Exception:
        try:
            pmb = binding.PassManagerBuilder()
            pmb.opt_level = 3
            pm = binding.ModulePassManager()
            pmb.populate(pm)
            pm.run(backing)
        except Exception:
            pass                            # unoptimized native is still fast
    engine = binding.create_mcjit_compiler(backing, tm)
    engine.finalize_object()
    _NATIVE_KEEPALIVE.append(engine)

    import ctypes
    out = {}
    for name in eligible:
        n_args = len(table[name].params)
        proto = ctypes.CFUNCTYPE(ctypes.c_int64, *([ctypes.c_int64] * n_args))
        out[name] = proto(engine.get_function_address(name))
    return out


# ---------------------------------------------------------------------------
# 5. INTERPRETER — actually run the program (main() is the entry point)
# ---------------------------------------------------------------------------

class ReturnSignal(Exception):
    def __init__(self, value): self.value = value


def to_text(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(to_text(x) for x in v) + "]"
    return str(v)


def run_builtin(name: str, args: list, line: int):
    import time as _time
    import random as _rand
    if name == "print":
        print(to_text(args[0]))
        return None
    if name == "length":
        return len(args[0])
    if name == "push":
        return args[0] + [args[1]]
    if name == "get":
        xs, i = args
        if i < 0 or i >= len(xs):
            raise VelarisError("E602",
                f"position {i} is outside the list (it has {len(xs)} item(s))",
                line, fixes=["positions go from 0 to length - 1",
                             "check with length(...) before using get"])
        return xs[i]
    if name == "read_file":
        try:
            return open(args[0], encoding="utf-8").read()
        except OSError:
            raise VelarisError("E404", f"cannot read file '{args[0]}'", line,
                              fixes=["check the file exists and the path is correct"])
    if name == "write_file":
        with open(args[0], "w", encoding="utf-8") as f:
            f.write(str(args[1]))
        return None
    if name == "fetch":
        # v0.2: simulated network (deterministic, works offline).
        # A real HTTP request arrives in a later version.
        return "response from " + str(args[0])
    if name == "now":
        return int(_time.time())
    if name == "random":
        n = args[0]
        if n <= 0:
            raise VelarisError("E405", "random(n) needs n greater than 0", line,
                              fixes=["pass a positive number, e.g. random(6)"])
        return _rand.randrange(n)


def interpret(funcs: list[Function], native: dict | None = None) -> None:
    native = native or {}
    table = {f.name: f for f in funcs}
    if "main" not in table:
        raise VelarisError("E400", "no 'main' function found", 1,
                          fixes=["add: fn main() uses io { ... }"])

    def call(name: str, args: list, line: int):
        if name in BUILTINS:
            return run_builtin(name, args, line)
        if name in native:
            return native[name](*args)     # machine code, C-like speed
        fn = table[name]
        if len(args) != len(fn.params):
            raise VelarisError("E401",
                f"'{name}' expects {len(fn.params)} argument(s) but got {len(args)}",
                line, fixes=[f"pass exactly {len(fn.params)} argument(s)"])
        env = {p[0]: a for p, a in zip(fn.params, args)}
        entry = dict(env)                  # snapshot: promises see entry values

        def vals(expr, extra=None):
            scope = dict(entry)
            if extra is not None:
                scope["result"] = extra[0]
            names = sorted(n for n in expr_vars(expr) if n in scope)
            return ", ".join(f"{n} = {scope[n]}" for n in names)

        for expr, cline in fn.requires:
            if not eval_(expr, dict(entry)):
                raise VelarisError("E600",
                    f"broken promise: '{name}' requires "
                    f"{expr_str(expr)}  ({vals(expr)})", cline,
                    fixes=["check the value before calling this function",
                           "or loosen the promise if it is too strict"])

        retval = None
        try:
            for stmt in fn.body:
                run(stmt, env)
        except ReturnSignal as r:
            retval = r.value

        for expr, cline in fn.ensures:
            check_env = dict(entry)
            check_env["result"] = retval
            if not eval_(expr, check_env):
                raise VelarisError("E601",
                    f"broken promise: '{name}' ensures "
                    f"{expr_str(expr)}  ({vals(expr, (retval,))})", cline,
                    fixes=["the code does not keep this promise - fix the code",
                           "or fix the promise if it is wrong"])
        return retval

    def run(node, env):
        if isinstance(node, Let):
            env[node.name] = eval_(node.value, env)
        elif isinstance(node, Return):
            raise ReturnSignal(None if node.value is None else eval_(node.value, env))
        elif isinstance(node, ExprStmt):
            eval_(node.expr, env)
        elif isinstance(node, If):
            branch = node.then if eval_(node.cond, env) else node.other
            for s in branch:
                run(s, env)
        elif isinstance(node, While):
            while eval_(node.cond, env):
                for s in node.body:
                    run(s, env)
        elif isinstance(node, Assign):
            env[node.name] = eval_(node.value, env)

    def eval_(node, env):
        if isinstance(node, Num):  return node.value
        if isinstance(node, Str):  return node.value
        if isinstance(node, Bool): return node.value
        if isinstance(node, Var):
            if node.name not in env:
                raise VelarisError("E402", f"unknown variable '{node.name}'", node.line,
                                  fixes=[f"declare it first: let {node.name} = ..."])
            return env[node.name]
        if isinstance(node, Call):
            return call(node.name, [eval_(a, env) for a in node.args], node.line)
        if isinstance(node, Not):
            return not eval_(node.value, env)
        if isinstance(node, ListLit):
            return [eval_(i, env) for i in node.items]
        if isinstance(node, BinOp):
            if node.op == "and":
                return eval_(node.left, env) and eval_(node.right, env)
            if node.op == "or":
                return eval_(node.left, env) or eval_(node.right, env)
            l, r = eval_(node.left, env), eval_(node.right, env)
            if node.op == "+":
                if isinstance(l, str) or isinstance(r, str):
                    return to_text(l) + to_text(r)
                return l + r
            if node.op == "-":  return l - r
            if node.op == "*":  return l * r
            if node.op == "/":
                if r == 0:
                    raise VelarisError("E403", "division by zero", node.line,
                                      fixes=["check the divisor before dividing"])
                return l // r
            return {"==": l == r, "!=": l != r, "<": l < r,
                    ">": l > r, "<=": l <= r, ">=": l >= r}[node.op]

    call("main", [], table["main"].line)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    filename = sys.argv[1]
    as_json = "--json" in sys.argv
    try:
        try:
            source = open(filename, encoding="utf-8").read()
        except OSError:
            raise VelarisError("E001", f"cannot find file '{filename}'", 1,
                              fixes=["check the file name spelling",
                                     "make sure you are in the folder that contains it"])
        tokens = lex(source)
        funcs = Parser(tokens).parse_program()
        check_effects(funcs)          # superpower 1: no hidden effects
        check_types(funcs)            # superpower 2: no type surprises
        check_proofs(funcs)           # superpower 3: broken promises proven early
        native = {} if "--no-native" in sys.argv else compile_native(funcs)
        import time as _t
        t0 = _t.perf_counter()
        interpret(funcs, native)
        if "--time" in sys.argv:
            ms = (_t.perf_counter() - t0) * 1000
            mode = "interpreted" if not native else "native+interpreted"
            print(f"[--time] ran in {ms:.1f} ms ({mode})", file=sys.stderr)
        return 0
    except VelarisError as e:
        print(e.machine(filename) if as_json else e.human(filename), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
