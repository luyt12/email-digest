const { execSync } = require("child_process");
const repo = "C:/Users/Lu/.qclaw/workspace/email-digest";

try {
  execSync(`git -C "${repo}" add -A`, { encoding: "utf8" });
  console.log("Staged");
  
  execSync(`git -C "${repo}" commit -m "fix: use correct message_id field"`, { encoding: "utf8" });
  console.log("Committed");
  
  execSync(`git -C "${repo}" push origin master`, { encoding: "utf8" });
  console.log("Pushed!");
} catch (e) {
  console.error("Error:", e.message);
  process.exit(1);
}