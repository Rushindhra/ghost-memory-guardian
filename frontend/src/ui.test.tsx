import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CitedText, ConfidenceBadge } from "./ui";

const cites = [{ n: 1, memory_id: "m1", title: "Rosa's bread", date: "1978", excerpt: "…" }];

describe("CitedText", () => {
  it("turns a valid [n] marker into a clickable source button", async () => {
    const onCite = vi.fn();
    render(<CitedText text="Rosa baked bread [1]." citations={cites} onCite={onCite} />);
    await userEvent.click(screen.getByRole("button", { name: "1" }));
    expect(onCite).toHaveBeenCalledWith(cites[0]);
  });
  it("leaves markers with no matching source as plain text (never a fake link)", () => {
    render(<CitedText text="Unsupported claim [7]." citations={cites} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/\[7\]/)).toBeInTheDocument();
  });
});

describe("ConfidenceBadge", () => {
  it("shows honest wording and the score", () => {
    render(<ConfidenceBadge level="low" score={0.19} />);
    expect(screen.getByText(/Weak match/)).toBeInTheDocument();
    expect(screen.getByText(/0\.19/)).toBeInTheDocument();
  });
});
