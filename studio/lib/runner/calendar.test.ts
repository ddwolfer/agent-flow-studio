import { describe, it, expect } from "vitest";
import { calendarFacts } from "./calendar";

describe("calendarFacts", () => {
  it("2026-04-30 is Thursday", () => {
    expect(calendarFacts(new Date("2026-04-30T04:00:00Z")).weekday).toBe("Thursday");
  });
  it("2026-05-01 is Labour Day", () => {
    expect(calendarFacts(new Date("2026-05-01T04:00:00Z")).holiday).toBe("Labour Day");
  });
  it("ordinary day has null holiday", () => {
    expect(calendarFacts(new Date("2026-04-30T04:00:00Z")).holiday).toBeNull();
  });
  it("renders a human-readable block containing the ISO date", () => {
    expect(calendarFacts(new Date("2026-04-30T04:00:00Z")).text).toContain("2026-04-30");
  });
});
