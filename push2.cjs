const { execSync } = require("child_process");
const repo = "C:/Users/Lu/.qclaw/workspace/email-digest";

try {
  execSync(`git -C "${repo}" add -A`, { encoding: "utf8", shell: true });
  console.log("Staged");
  
  execSync(`git -C "${repo}" commit -m "fix: filter to incoming emails only, newest first"`, { encoding: "utf8", shell: true });
  console.log("Committed");
  
  execSync(`git -C "${repo}" push origin master`, { encoding: "utf8", shell: true });
  console.log("Pushed!");
} catch (e) {
  console.error("Error:", e.message);
  process.exit(1);
}