export interface MechResult { ok: boolean; failures: string[]; }

export function mechanicalChecks(
  html: string,
  cal: { iso: string; weekday: string },
  requiredSections: readonly string[],
): MechResult {
  const failures: string[] = [];
  for (const s of requiredSections)
    if (!html.includes(s)) failures.push(`missing section: ${s}`);
  const m = html.match(/\((Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\)/);
  if (m && m[1] !== cal.weekday)
    failures.push(`weekday mismatch: report says ${m[1]}, calendar says ${cal.weekday}`);
  return { ok: failures.length === 0, failures };
}
