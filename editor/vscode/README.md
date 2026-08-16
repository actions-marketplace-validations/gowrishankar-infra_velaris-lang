# Velaris for VS Code

Syntax highlighting for `.vel` files: keywords, contracts (`requires`,
`ensures`, `invariant`), effects (`uses`), types, builtins, strings with
escapes, and comments.

## Install (no marketplace needed)

Copy this folder into your VS Code extensions directory and restart:

**Windows (PowerShell):**
```
Copy-Item -Recurse -Force editor\vscode "$env:USERPROFILE\.vscode\extensions\velaris-syntax-1.1.0"
```

**macOS / Linux:**
```
cp -r editor/vscode ~/.vscode/extensions/velaris-syntax-1.1.0
```

Then reload VS Code and open any `.vel` file.
