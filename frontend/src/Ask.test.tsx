import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Ask from "./pages/Ask";

const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
const base = { query: "q", supported: false, results: [], elapsed_ms: 3, retrieval: { embedder: "lexical-hash-v1", neural: false, min_score: 0.2, strong_score: 0.4 } };

afterEach(() => vi.restoreAllMocks());

describe("Ask page", () => {
  it("shows the exact not-found sentence when the backend finds no evidence", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => json({ ...base, answer: { status: "not_found", text: "I couldn't find that in your saved memories.", citations: [], warnings: [] } }));
    render(<MemoryRouter><Ask /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/ask in your own words/i), "capital of Australia");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("I couldn't find that in your saved memories.")).toBeInTheDocument();
  });

  it("never invents an answer when the local model is unavailable, and says how to fix it", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => json({ ...base, supported: true, answer: { status: "ai_unavailable", text: null, message: "Ollama is not running.", citations: [], warnings: [] } }));
    render(<MemoryRouter><Ask /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/ask in your own words/i), "who baked bread");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/Ollama is not running/)).toBeInTheDocument();
    expect(screen.getByText(/no written answer was produced/i)).toBeInTheDocument();
  });

  it("explains an unreachable backend instead of failing silently", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("network"));
    render(<MemoryRouter><Ask /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText(/ask in your own words/i), "anything");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Cannot reach the GHOST backend/));
  });
});
