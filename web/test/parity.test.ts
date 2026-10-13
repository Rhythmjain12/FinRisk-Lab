import { expect, test } from "vitest";
import { analyse } from "../src/engine/analyse";
import fixture from "./fixtures/parity.json";

/**
 * The TypeScript engine must reproduce the Python engine on the same prices.
 * Every number in Python's results.json is compared (null there means NaN).
 */
function compare(actual: unknown, expected: unknown, path: string, problems: string[]) {
  if (expected === null) {
    if (!(typeof actual === "number" && Number.isNaN(actual))) problems.push(`${path}: expected NaN, got ${actual}`);
  } else if (typeof expected === "number") {
    const tolerance = 1e-9 * Math.max(1, Math.abs(expected));
    // written as !(<=) so that a NaN on our side fails instead of slipping through
    if (typeof actual !== "number" || !(Math.abs(actual - expected) <= tolerance)) {
      problems.push(`${path}: python ${expected}, typescript ${actual}`);
    }
  } else if (typeof expected === "object") {
    for (const [key, value] of Object.entries(expected as object)) {
      compare((actual as Record<string, unknown> | undefined)?.[key], value, `${path}.${key}`, problems);
    }
  } else if (actual !== expected) {
    problems.push(`${path}: python ${expected}, typescript ${actual}`);
  }
}

test("matches the Python engine on every metric", () => {
  const results = analyse(
    { dates: fixture.dates, names: fixture.names, rows: fixture.rows },
    fixture.weights, fixture.benchmark,
    { benchmarkName: "^NSEI", riskFreeRate: fixture.risk_free_rate, groups: fixture.groups },
  );
  const problems: string[] = [];
  compare(results, fixture.expected, "results", problems);
  expect(problems).toEqual([]);
  // guard against a vacuous pass: the fixture really does carry the headline numbers
  expect(Object.keys(fixture.expected.portfolio_metrics).length).toBeGreaterThanOrEqual(9);
  expect(Object.keys(fixture.expected.exposure)).toEqual(["Asset Class", "Region"]);
});
