const { execSync } = require("child_process");
const path = "C:/Users/Lu/.qclaw/workspace/email-digest";

try {
  execSync(`git -C "${path}" commit -m "debug: print email subjects"`, { encoding: "utf8", shell: true });
  console.log("Committed");
  
  execSync(`git -C "${path}" push`, { encoding: "utf8", shell: true });
  console.log("Pushed!");
} catch (e) {
  console.error("Error:", e.message);
  process.exit(1);
}