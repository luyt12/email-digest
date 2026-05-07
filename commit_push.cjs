const { execSync } = require("child_process");
const repo = "C:/Users/Lu/.qclaw/workspace/email-digest";

try {
  // Stage all changes
  execSync(`git -C "${repo}" add -A`, { encoding: "utf8", shell: true });
  console.log("Staged");
  
  // Commit
  execSync(`git -C "${repo}" commit -m "debug: print email subjects"`, { encoding: "utf8", shell: true });
  console.log("Committed");
  
  // Push
  execSync(`git -C "${repo}" push origin master`, { encoding: "utf8", shell: true });
  console.log("Pushed!");
} catch (e) {
  console.error("Error:", e.message);
  console.error(e.stdout);
  console.error(e.stderr);
  process.exit(1);
}