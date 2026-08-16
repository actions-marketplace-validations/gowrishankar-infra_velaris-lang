# Velaris for VS Code

Syntax highlighting AND live errors for `.vel` files. If the `velaris`
command is installed (`pip install .` from the repo), the extension
launches `velaris lsp` automatically: effect, type, and proof errors
appear as red squiggles while you type - each with its numbered fixes
in the hover.

Also covers: keywords, contracts (`requires`,
`ensures`, `invariant`), effects (`uses`), types, builtins, strings with
escapes, and comments.

## Install (no marketplace needed)

Copy this folder into your VS Code extensions directory and restart:

**Windows (PowerShell):**
```
Copy-Item -Recurse -Force editor\vscode "$env:USERPROFILE\.vscode\extensions\velaris-syntax-1.11.0"
```

**macOS / Linux:**
```
cp -r editor/vscode ~/.vscode/extensions/velaris-syntax-1.11.0
```

Then reload VS Code and open any `.vel` file.
