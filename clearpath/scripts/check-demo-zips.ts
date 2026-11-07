// Run: node --experimental-strip-types scripts/check-demo-zips.ts (from clearpath/)
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { listZipEntries } from "../lib/zip.ts";
import { matchRequirement } from "../lib/docmatch.ts";

const REQS = [
  { key: "adu-verification-form", title: "ADU Verification Form" },
  { key: "adu-permit-application", title: "ADU Permit Application" },
  { key: "building-plans-calcs", title: "Building plans, calculations, and construction documents" },
  { key: "development-standards-checklist", title: "Development Standards Checklist for Site Plan" },
  { key: "covenant", title: "Covenant" },
  { key: "signed-affidavit-esig", title: "Signed affidavit from property owner and applicant" },
  { key: "developer-deposit-case-setup", title: "Developer Deposit Case Set-Up form" },
  { key: "school-fee-determination-form", title: "School Fee Determination Form" },
  { key: "tca-form", title: "Transportation Corridor Agency Form" },
  { key: "address-application", title: "Address Application" },
];
const EXPECTED: Record<string, string | null> = {
  "01_ADU_Permit_Application.pdf": "adu-permit-application",
  "02_ADU_Verification_Form.pdf": "adu-verification-form",
  "03_Address_Application.pdf": "address-application",
  "04_Building_Plans_and_Calculations.pdf": "building-plans-calcs",
  "05_School_Fee_Determination_Form.pdf": "school-fee-determination-form",
  "06_TCA_Transportation_Corridor_Agency_Form.pdf": "tca-form",
  "07_Covenant.pdf": "covenant",
  "08_Developer_Deposit_Case_Setup_Form.pdf": "developer-deposit-case-setup",
  "09_Development_Standards_Checklist_Form_67-01.pdf": "development-standards-checklist",
  "10_Signed_Affidavit_Owner_and_Applicant.pdf": "signed-affidavit-esig",
  "Site_Photos.pdf": null,
};

const dir = join(import.meta.dirname, "..", "public", "demo");
let fail = 0;
const seen = new Set<string>();
const archives = readdirSync(dir).filter((f) => f.endsWith(".zip")).sort();
const expectedArchives = ["clearpath-demo-1-application.zip", "clearpath-demo-2-plans-and-forms.zip", "clearpath-demo-3-final.zip", "clearpath-demo-all.zip"];
for (const name of expectedArchives) if (!archives.includes(name)) { fail++; console.log(`MISSING ZIP ${name}`); }
for (const z of archives) {
  const b = readFileSync(join(dir, z));
  const ab = b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
  console.log(`${z}:`);
  for (const name of listZipEntries(ab)) {
    const key = matchRequirement(name, REQS);
    const ok = name in EXPECTED && EXPECTED[name] === key;
    if (!ok) fail++;
    seen.add(name);
    console.log(`  ${ok ? "OK  " : "FAIL"} ${name} -> ${key ?? "(unmatched)"}`);
  }
}
for (const n of Object.keys(EXPECTED)) if (!seen.has(n)) { fail++; console.log(`  MISSING ${n}`); }
console.log(fail ? `FAILED: ${fail}` : "ALL OK: 11 entries match the expected table");
process.exit(fail ? 1 : 0);
