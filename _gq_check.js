const fs = require("fs");
const path = "public/resources/tools/grant-eligibility/index.html";
const t = fs.readFileSync(path, "utf8");
const scripts = [...t.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).filter(s => s.includes("const GRANTS"));
if (!scripts.length) { console.error("no GRANTS script"); process.exit(1); }
try {
  new Function(scripts[0]);
  console.log("JS OK, grants", (scripts[0].match(/name:\s*"/g) || []).length);
} catch (e) {
  console.error("JS ERR", e.message);
  process.exit(1);
}
