const { execSync } = require("child_process");
const r = "C:/Users/Lu/.qclaw/workspace/email-digest";
execSync(`git -C "${r}" add -A`, { stdio: "inherit" });
execSync(`git -C "${r}" commit -m "add word/char count display in digest email"`, { stdio: "inherit" });
execSync(`git -C "${r}" push origin master`, { stdio: "inherit" });
console.log("Done!");
