// Velaris VS Code extension: syntax highlighting is declarative (see
// package.json); this file adds LIVE ERRORS by speaking the Language
// Server Protocol to `velaris lsp` directly - no npm dependencies, so
// the folder-copy install keeps working.
const vscode = require("vscode");
const cp = require("child_process");

let proc = null;
let buffer = Buffer.alloc(0);
let nextId = 1;
let collection = null;

function send(msg) {
  if (!proc) return;
  const body = Buffer.from(JSON.stringify(msg), "utf8");
  proc.stdin.write(`Content-Length: ${body.length}\r\n\r\n`);
  proc.stdin.write(body);
}

function onData(chunk) {
  buffer = Buffer.concat([buffer, chunk]);
  for (;;) {
    const headerEnd = buffer.indexOf("\r\n\r\n");
    if (headerEnd < 0) return;
    const header = buffer.slice(0, headerEnd).toString("utf8");
    const m = header.match(/Content-Length: *(\d+)/i);
    if (!m) { buffer = buffer.slice(headerEnd + 4); continue; }
    const len = parseInt(m[1], 10);
    const start = headerEnd + 4;
    if (buffer.length < start + len) return;
    const body = buffer.slice(start, start + len).toString("utf8");
    buffer = buffer.slice(start + len);
    try { handle(JSON.parse(body)); } catch (e) { /* ignore */ }
  }
}

function handle(msg) {
  if (msg.method === "textDocument/publishDiagnostics") {
    const { uri, diagnostics } = msg.params;
    const diags = diagnostics.map((d) => {
      const r = d.range;
      const range = new vscode.Range(
        r.start.line, r.start.character, r.end.line, r.end.character);
      const diag = new vscode.Diagnostic(
        range, d.message, vscode.DiagnosticSeverity.Error);
      diag.source = d.source || "velaris";
      return diag;
    });
    collection.set(vscode.Uri.parse(uri), diags);
  }
}

function docParams(doc) {
  return {
    textDocument: {
      uri: doc.uri.toString(), languageId: "velaris",
      version: doc.version, text: doc.getText(),
    },
  };
}

function activate(context) {
  collection = vscode.languages.createDiagnosticCollection("velaris");
  context.subscriptions.push(collection);
  try {
    proc = cp.spawn("velaris", ["lsp"], { shell: process.platform === "win32" });
  } catch (e) { proc = null; }
  if (!proc) return;
  proc.on("error", () => {
    proc = null;
    vscode.window.showInformationMessage(
      "Velaris: install the compiler (pip install .) to get live errors.");
  });
  proc.stdout.on("data", onData);

  send({ jsonrpc: "2.0", id: nextId++, method: "initialize", params: {} });
  send({ jsonrpc: "2.0", method: "initialized", params: {} });

  const isVel = (doc) => doc.languageId === "velaris";
  for (const doc of vscode.workspace.textDocuments) {
    if (isVel(doc)) {
      send({ jsonrpc: "2.0", method: "textDocument/didOpen",
             params: docParams(doc) });
    }
  }
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((doc) => {
      if (isVel(doc)) send({ jsonrpc: "2.0",
        method: "textDocument/didOpen", params: docParams(doc) });
    }),
    vscode.workspace.onDidChangeTextDocument((ev) => {
      if (!isVel(ev.document)) return;
      send({ jsonrpc: "2.0", method: "textDocument/didChange", params: {
        textDocument: { uri: ev.document.uri.toString(),
                        version: ev.document.version },
        contentChanges: [{ text: ev.document.getText() }],
      }});
    }),
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (isVel(doc)) send({ jsonrpc: "2.0",
        method: "textDocument/didSave", params: {
          textDocument: { uri: doc.uri.toString() },
          text: doc.getText(),
        }});
    }),
    vscode.workspace.onDidCloseTextDocument((doc) => {
      if (isVel(doc)) send({ jsonrpc: "2.0",
        method: "textDocument/didClose", params: {
          textDocument: { uri: doc.uri.toString() } }});
    }),
  );
}

function deactivate() {
  if (proc) {
    send({ jsonrpc: "2.0", id: nextId++, method: "shutdown", params: {} });
    send({ jsonrpc: "2.0", method: "exit" });
    proc = null;
  }
}

module.exports = { activate, deactivate };
