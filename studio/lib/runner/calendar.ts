const WD = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
const FIXED_HOLIDAYS: Record<string, string> = {
  "01-01": "New Year's Day", "05-01": "Labour Day", "10-10": "National Day",
};

export interface CalendarFacts { iso: string; weekday: string; holiday: string | null; text: string; }

export function calendarFacts(d: Date): CalendarFacts {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(d);
  const g = (t: string) => parts.find((p) => p.type === t)!.value;
  const iso = `${g("year")}-${g("month")}-${g("day")}`;
  const weekday = WD[new Date(`${iso}T00:00:00Z`).getUTCDay()]!;
  const holiday = FIXED_HOLIDAYS[`${g("month")}-${g("day")}`] ?? null;
  const text = `Today is ${iso} (${weekday})${holiday ? `, a public holiday: ${holiday}` : ""}. Do not infer the weekday yourself; use this fact.`;
  return { iso, weekday, holiday, text };
}
