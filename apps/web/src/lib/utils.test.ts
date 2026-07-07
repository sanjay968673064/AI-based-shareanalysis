import { describe, expect, it } from "vitest";

import { formatCurrency, formatPercent } from "./utils";

describe("formatters", () => {
  it("formats rupee values for Indian investors", () => {
    expect(formatCurrency(163525.6)).toBe("₹1,63,526");
  });

  it("keeps the sign on positive percentages", () => {
    expect(formatPercent(9.923)).toBe("+9.92%");
  });
});
