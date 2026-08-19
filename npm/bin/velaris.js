#!/usr/bin/env node
// npx velaris hello.vel
//
// Velaris's compiler is one Python file. This hands your arguments to
// it, and if it is not installed, says exactly how to fix that rather
// than failing with a confusing spawn error.

import { spawn, spawnSync } from "node:child_process";

function pythons() {
  return process.platform === "win32"
    ? ["py", "python", "python3"]
    : ["python3", "python"];
}

function findVelaris() {
  for (const exe of pythons()) {
    const probe = spawnSync(exe, ["-c", "import velaris"], {
      stdio: "ignore",
    });
    if (probe.status === 0) return exe;
  }
  return null;
}

const exe = findVelaris();
if (!exe) {
  console.error(
    "Velaris needs its compiler, which is a Python package:\n" +
      "\n    pip install velaris-lang\n" +
      "\nOr try it with nothing installed:\n" +
      "    https://gowrishankar-infra.github.io/velaris-lang/playground.html"
  );
  process.exit(127);
}

const child = spawn(exe, ["-m", "velaris", ...process.argv.slice(2)], {
  stdio: "inherit",
});
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});
