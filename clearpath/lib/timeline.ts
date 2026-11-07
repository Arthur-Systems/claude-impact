// Timeline math. Every number here is either a legal limit (cited) or a
// labeled assumption. Change the assumptions here, in one place.

// Legal limit: city must approve or deny a COMPLETE ADU application within
// 60 days, or it is deemed approved. (California Gov. Code 66317)
export const DECISION_DAYS = 60;

// Legal limit: city must say in writing whether the application is complete
// within 15 business days. (California Gov. Code 66317)
export const COMPLETENESS_LIMIT_BUSINESS_DAYS = 15;

// ASSUMPTION: Irvine says staff check completeness in about two business
// days, so we budget 4 calendar days. Replace with real Irvine data.
export const COMPLETENESS_CHECK_DAYS = 4;

export const PREP_OPTIONS = [
  { days: 7, label: "1 week" },
  { days: 14, label: "2 weeks" },
  { days: 30, label: "1 month" },
  { days: 60, label: "2 months" },
];

export type Estimate = { prep: number; check: number; decide: number; total: number };

export function estimate(prepDays: number): Estimate {
  const check = COMPLETENESS_CHECK_DAYS;
  const decide = DECISION_DAYS;
  return { prep: prepDays, check, decide, total: prepDays + check + decide };
}

export const toWeeks = (days: number) => Math.ceil(days / 7);
