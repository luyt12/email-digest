const { execSync } = require("child_process");
const path = "C:/Users/Lu/.qclaw/workspace/email-digest";

try {
  // Commit
  const msg = "Initial commit: Email Digest project";
  execSync(`git -C "${path}" commit -m "${msg}"`, { encoding: "utf8", shell: true });
  console.log("Committed");
  
  // Create remote repo
  console.log("Creating GitHub repo...");
  execSync(`gh repo create email-digest --public --source="${path}" --push`, { encoding: "utf8", shell: true });
  console.log("Repo created and pushed!");
} catch (e) {
  console.error("Error:", e.message);
  process.exit(1);
}