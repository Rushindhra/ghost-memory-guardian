import { describe, expect, it } from "vitest";
import { formatBytes, formatMemoryDate, qs } from "./api";

describe("formatMemoryDate", () => {
  it("handles year, month and full dates without timezone drift", () => {
    expect(formatMemoryDate("1984")).toBe("1984");
    expect(formatMemoryDate("1984-06")).toBe("Jun 1984");
    expect(formatMemoryDate("1984-06-01")).toBe("1 Jun 1984");
  });
  it("labels missing dates", () => expect(formatMemoryDate(null)).toBe("Undated"));
});

describe("qs", () => {
  it("drops empty values and encodes the rest", () => {
    expect(qs({ q: "a b", person: "", tag: undefined, k: 5 })).toBe("?q=a+b&k=5");
    expect(qs({})).toBe("");
  });
});

describe("formatBytes", () => {
  it("scales units", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 ** 2)).toBe("5.0 MB");
  });
});
