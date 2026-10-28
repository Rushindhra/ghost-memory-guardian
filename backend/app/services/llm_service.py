"""Local LLM access through Ollama, plus the grounded-answer prompts.

* Only the local Ollama daemon is contacted; non-loopback hosts are refused
  unless ``GHOST_ALLOW_REMOTE_LLM=true``.
* If Ollama or the model is missing, ``LLMUnavailable`` carries setup advice
  and callers surface it - no answer is ever fabricated.
* Citations are validated after generation: only ``[n]`` markers that point at
  the sources actually supplied survive.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

log = logging.getLogger("ghost.llm")

NOT_FOUND_ANSWER = "I couldn't find that in your saved memories."


class LLMUnavailable(RuntimeError):
    """The local model cannot be used; ``str(exc)`` is user-facing setup guidance."""


class LLM(Protocol):
    def status(self) -> dict[str, Any]: ...
    def chat(self, messages: list[dict[str, str]], json_mode: bool = False, temperature: float | None = None) -> str: ...


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_s: float, temperature: float, allow_remote: bool,
                 loopback: bool) -> None:
        self.base_url, self.model, self.timeout_s, self.temperature = base_url, model, timeout_s, temperature
        self.allow_remote, self.loopback = allow_remote, loopback

    def _guard(self) -> None:
        if not self.loopback and not self.allow_remote:
            raise LLMUnavailable(
                "The configured Ollama address is not on this computer, so GHOST refuses to send memories to it. "
                "Use http://127.0.0.1:11434 or set GHOST_ALLOW_REMOTE_LLM=true if you control that machine."
            )

    def status(self) -> dict[str, Any]:
        info: dict[str, Any] = {"engine": "ollama", "url": self.base_url, "model": self.model,
                                "reachable": False, "model_installed": False, "installed_models": [], "message": ""}
        try:
            self._guard()
            r = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]
            info.update(reachable=True, installed_models=names)
            wanted = self.model if ":" in self.model else f"{self.model}:latest"
            info["model_installed"] = wanted in names
            if not info["model_installed"]:
                info["message"] = f"Ollama is running but model '{self.model}' is not installed. Run: ollama pull {self.model}"
        except LLMUnavailable as exc:
            info["message"] = str(exc)
        except (httpx.HTTPError, ValueError):
            info["message"] = ("Ollama is not running. Install it from https://ollama.com, start it, then run: "
                               f"ollama pull {self.model}. Archive features that do not need AI keep working.")
        return info

    def chat(self, messages: list[dict[str, str]], json_mode: bool = False, temperature: float | None = None) -> str:
        st = self.status()
        if not (st["reachable"] and st["model_installed"]):
            raise LLMUnavailable(st["message"] or "The local language model is unavailable.")
        body: dict[str, Any] = {
            "model": self.model, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": self.temperature if temperature is None else temperature, "num_ctx": 6144},
            "keep_alive": "10m",
        }
        if json_mode:
            body["format"] = "json"
        try:
            r = httpx.post(f"{self.base_url}/api/chat", json=body, timeout=self.timeout_s)
            r.raise_for_status()
            text = r.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.warning("Ollama chat failed: %s", type(exc).__name__)  # never log prompts or content
            raise LLMUnavailable("The local model did not respond in time or returned an error. "
                                 "On CPU a 4B model can take a minute; try again or choose a smaller model in Settings.") from exc
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ---------------------------------------------------------------- prompts --
@dataclass
class Source:
    n: int
    memory_id: str
    title: str
    date: str | None
    people: list[str]
    text: str


def format_sources(sources: list[Source]) -> str:
    blocks = []
    for s in sources:
        meta = ", ".join(x for x in [s.date or "", ("people: " + ", ".join(s.people)) if s.people else ""] if x)
        blocks.append(f"[{s.n}] {s.title}" + (f" ({meta})" if meta else "") + f"\n{s.text}")
    return "\n\n".join(blocks)


ANSWER_SYSTEM = (
    "You answer questions about a person's private memory archive. Use ONLY the numbered sources provided. "
    "Rules: (1) Every sentence of fact must end with the source number in square brackets, like [1] or [2]. "
    "(2) Never add names, dates, places, relationships or events that are not written in the sources. "
    "(3) If the sources do not clearly answer the question, reply exactly: " + NOT_FOUND_ANSWER + " "
    "(4) Answer in the same language as the question. Be concise (at most 5 sentences). "
    "(5) You are summarising written records; never claim to speak for, or as, any person."
)


def build_answer_messages(question: str, sources: list[Source]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": ANSWER_SYSTEM},
        {"role": "user", "content": f"SOURCES:\n{format_sources(sources)}\n\nQUESTION: {question}\n\nANSWER:"},
    ]


SUMMARY_SYSTEM = (
    "You write a short family-history summary using ONLY the numbered records provided, in chronological order. "
    "Cite the record number in square brackets after each fact, like [2]. Do not invent or infer names, dates, "
    "places, motives or relationships. If records conflict, say so. Use warm, plain prose of 2-4 short paragraphs "
    "in the same language as the records."
)


def build_summary_messages(focus: str, sources: list[Source]) -> list[dict[str, str]]:
    focus_line = f"Focus: {focus}\n\n" if focus else ""
    return [{"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": f"{focus_line}RECORDS:\n{format_sources(sources)}\n\nSUMMARY:"}]


GHOST_STYLES = {
    "gentle": "a soft, wistful, bittersweet ghost story: quiet, nostalgic, comforting, with no fear at all",
    "mysterious": "an eerie, atmospheric mystery with creaking houses, candlelight and unanswered questions, but nothing graphic",
    "spooky": "a classic spooky campfire ghost story with suspense and chills, but no gore, no violence and no jump-scare cruelty",
    "remembrance": "a warm, respectful remembrance piece: gentle, loving and honouring, with NO horror elements and no supernatural claims",
}


def build_ghost_messages(sources: list[Source], intensity: str, language: str) -> list[dict[str, str]]:
    lang = f"Write in {language}." if language else "Write in the same language as the records."
    system = (
        f"You are a storyteller writing {GHOST_STYLES[intensity]}. The story is clearly FICTION inspired by the "
        "numbered records. Treat real people with dignity: never make a real person frightening, cruel or "
        "malevolent, never imply that anyone's spirit can be contacted, and never present the invented parts as fact. "
        f"{lang} Return JSON with keys: \"title\" (string), \"story\" (3-5 paragraphs, markdown allowed), "
        "\"invented_elements\" (array of short strings naming every detail you invented that is NOT in the records, "
        "e.g. the ghost, weather, sounds, objects). Facts taken from the records should be marked with their [n]."
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"RECORDS:\n{format_sources(sources)}\n\nJSON:"}]


# ------------------------------------------------------------ validation ---
CITE = re.compile(r"\[(\d{1,2})\]")


def validate_citations(text: str, valid: set[int]) -> tuple[str, list[int], list[int]]:
    """Strip citation markers that do not point at a supplied source.

    Returns (clean_text, cited_valid_numbers_in_order, removed_invalid_numbers).
    """
    cited: list[int] = []
    removed: list[int] = []

    def repl(m: re.Match[str]) -> str:
        n = int(m.group(1))
        if n in valid:
            if n not in cited:
                cited.append(n)
            return m.group(0)
        removed.append(n)
        return ""

    clean = CITE.sub(repl, text)
    clean = re.sub(r"[ \t]+([.,;:!?])", r"\1", re.sub(r"[ \t]{2,}", " ", clean)).strip()
    return clean, cited, removed


_CAP = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-zà-ÿ]{2,})\b")
_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
_COMMON_CAPS = {"The", "And", "But", "She", "His", "Her", "They", "That", "This", "When", "There", "These", "Those",
                "However", "Although", "Because", "After", "Before", "During"}


def ungrounded_terms(answer: str, source_text: str) -> list[str]:
    """Years and capitalised names in the answer that never occur in the sources.

    A heuristic safety net shown to the user as a warning; it does not prove an answer correct.
    """
    haystack = source_text.lower()
    out: list[str] = []
    for y in _YEAR.findall(answer):
        if y not in source_text and y not in out:
            out.append(y)
    for name in _CAP.findall(answer):
        if name not in _COMMON_CAPS and name.lower() not in haystack and name not in out:
            out.append(name)
    return out


def parse_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except ValueError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                return obj if isinstance(obj, dict) else None
            except ValueError:
                return None
    return None
