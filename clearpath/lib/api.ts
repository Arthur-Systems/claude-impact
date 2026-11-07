import { ENTRIES, IRVINE_ADU_PAGE, IRVINE_PORTAL, HCD_FACT_SHEET } from "./knowledge";
import { COMPLETENESS_LIMIT_BUSINESS_DAYS, DECISION_DAYS } from "./timeline";

export type Source = { label: string; url: string };
export type NavReply = { answer: string; sources: Source[]; mock: boolean };
export type NavContext = { missing: string[]; flagged: number; address: string | null };

// BACKEND CONTRACT
// If NEXT_PUBLIC_API_URL is set (for example http://localhost:8000), this sends
//   POST {url}/api/navigator   { question, context }
// and expects back  { answer: string, sources: [{label, url}] }.
// If it is not set, or the request fails, a demo answer is used instead.
export async function askNavigator(question: string, context: NavContext): Promise<NavReply> {
  const base = process.env.NEXT_PUBLIC_API_URL;
  if (base) {
    try {
      const res = await fetch(`${base}/api/navigator`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, context }),
      });
      if (res.ok) {
        const data = await res.json();
        return { answer: data.answer, sources: data.sources ?? [], mock: false };
      }
    } catch {
      // fall through to the demo answer
    }
  }
  await new Promise((r) => setTimeout(r, 500));
  return demoAnswer(question, context);
}

const src = (id: string): Source => {
  const e = ENTRIES.find((x) => x.id === id)!;
  return { label: `${e.source}: ${e.title}`, url: e.url };
};

function demoAnswer(q: string, ctx: NavContext): NavReply {
  const t = q.toLowerCase();
  const has = (re: RegExp) => re.test(t);

  if (has(/fee|cost|pay|price/)) {
    return {
      mock: true,
      answer: "Irvine emails you a payment link after staff finish the completeness check. I do not have verified fee amounts, so check the city's current fee schedule.",
      sources: [src("irvine-fees")],
    };
  }
  if (has(/long|time|timeline|approv|when|weeks|days/)) {
    return {
      mock: true,
      answer: `State law gives the city ${COMPLETENESS_LIMIT_BUSINESS_DAYS} business days to tell you if your application is complete, then ${DECISION_DAYS} days to approve or deny it once it is complete. Irvine says it usually checks completeness in about two business days. Missing documents delay the start of that ${DECISION_DAYS} day clock. See the Timeline tab for your estimate.`,
      sources: [{ label: "California HCD: ADU Housing Law Fact Sheet", url: HCD_FACT_SHEET }, src("irvine-how")],
    };
  }
  if (has(/where|apply|portal|online|irvineready/)) {
    return {
      mock: true,
      answer: "Irvine takes ADU applications online through the IrvineReady portal. Create an account, start a new submittal, and choose For Permitting, Other as the project type.",
      sources: [{ label: "IrvineReady portal", url: IRVINE_PORTAL }, src("irvine-how")],
    };
  }
  if (has(/pre-?approved/)) {
    return { mock: true, answer: "Irvine runs a pre-approved ADU plans program. Using a pre-approved plan can simplify your application.", sources: [src("irvine-preapproved")] };
  }
  if (has(/need|missing|still|submit|checklist|document|ready/)) {
    const lines = ctx.missing.length
      ? `You are still missing: ${ctx.missing.join(", ")}.`
      : "All of your required documents are in.";
    const flagged = ctx.flagged ? ` You also have ${ctx.flagged} uploaded file${ctx.flagged > 1 ? "s" : ""} that need${ctx.flagged > 1 ? "" : "s"} attention.` : "";
    return {
      mock: true,
      answer: `${lines}${flagged} Irvine also requires its ADU application and an ADU Verification Form for every ADU project, so check those against the city's list.`,
      sources: [src("irvine-submittal")],
    };
  }
  return {
    mock: true,
    answer: "I can help with what documents you still need, how long approval takes, where to apply, and fees. For anything else, you can ask the city directly in the Ask the City tab.",
    sources: [src("irvine-contact")],
  };
}
