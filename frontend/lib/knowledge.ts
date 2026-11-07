// Small set of real, sourced entries used by the demo Search and Navigator.
// The backend (pgvector search) will replace this.
export type Entry = { id: string; title: string; text: string; url: string; source: string; tags: string };

export const IRVINE_ADU_PAGE = "https://cityofirvine.gov/node/69676";
export const IRVINE_PORTAL = "https://gopost-irvine.eplansoftreview.com/#/login?portal=irvine";
export const HCD_FACT_SHEET = "https://www.hcd.ca.gov/sites/default/files/docs/planning-and-community/adu.pdf";

export const ENTRIES: Entry[] = [
  {
    id: "irvine-submittal",
    title: "Irvine ADU submittal requirements",
    text: "Irvine requires a completed ADU application and an ADU Verification Form for every ADU and JADU project. The package also includes building plans, calculations, and construction documents, a development standards checklist for the site plan, a hold harmless affidavit, a notarized covenant, a signed owner and applicant affidavit, and a developer deposit case set-up form.",
    url: IRVINE_ADU_PAGE,
    source: "City of Irvine",
    tags: "required documents checklist forms submittal application verification affidavit covenant plans need",
  },
  {
    id: "irvine-how",
    title: "How to apply in Irvine",
    text: "Irvine takes ADU applications online through the IrvineReady portal. Create an account, start a new submittal, and choose For Permitting, Other as the project type. City staff check for completeness in about two business days, then email a link to pay fees.",
    url: IRVINE_ADU_PAGE,
    source: "City of Irvine",
    tags: "apply submit portal online irvineready account where payment completeness",
  },
  {
    id: "state-timeline",
    title: "State review deadlines for ADUs",
    text: "State law gives the city 15 business days to tell you in writing whether your ADU application is complete, and 60 days after it is complete to approve or deny it. If the city misses the 60 day deadline, the application is deemed approved.",
    url: HCD_FACT_SHEET,
    source: "California HCD",
    tags: "timeline how long time days deadline approval approve review deemed approved wait weeks",
  },
  {
    id: "irvine-preapproved",
    title: "Pre-approved ADU plans in Irvine",
    text: "Since January 1, 2025, state law (AB 1332) requires Irvine to offer a program that pre-approves ADU plans. Using a pre-approved plan can simplify your application.",
    url: "https://cityofirvine.gov/building-permits-and-inspections/pre-approved-adu-plans-program",
    source: "City of Irvine",
    tags: "pre-approved preapproved plans program faster simpler",
  },
  {
    id: "irvine-fees",
    title: "Irvine permit fees",
    text: "Irvine emails you a payment link after the completeness review. Current fee rates are listed on the city's fee schedule page.",
    url: "https://cityofirvine.gov/node/4706",
    source: "City of Irvine",
    tags: "fees fee cost pay payment price schedule money",
  },
  {
    id: "hcd-handbook",
    title: "California ADU Handbook",
    text: "The state's ADU Handbook explains statewide ADU rules in plain language, including review timelines, for homeowners and cities.",
    url: "https://www.hcd.ca.gov/sites/default/files/docs/policy-research/adu-handbook-update.pdf",
    source: "California HCD",
    tags: "handbook state rules law guide regulations",
  },
  {
    id: "irvine-contact",
    title: "Contact the Irvine Planning Team",
    text: "Questions about an Irvine ADU go to the Planning Team at planning@cityofirvine.org or 949-724-6308.",
    url: IRVINE_ADU_PAGE,
    source: "City of Irvine",
    tags: "contact question help email phone planning team ask city",
  },
];

const STOP = new Set(["the", "and", "for", "what", "how", "can", "does", "with", "are", "was", "this", "that", "from", "have", "need", "much", "long"]);

export function searchEntries(query: string): Entry[] {
  const tokens = query.toLowerCase().split(/[^a-z0-9]+/).filter((t) => t.length > 2 && !STOP.has(t));
  if (tokens.length === 0) return [];
  return ENTRIES.map((e) => {
    const hay = `${e.title} ${e.text} ${e.tags}`.toLowerCase();
    return { e, score: tokens.filter((t) => hay.includes(t)).length };
  })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((x) => x.e);
}
