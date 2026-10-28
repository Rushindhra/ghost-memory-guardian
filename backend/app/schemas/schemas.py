"""Pydantic request/response models with strict validation."""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

PARTIAL_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CATEGORIES = ["general", "childhood", "family", "love", "work", "migration", "tradition", "recipe", "letter", "wisdom", "loss"]


def _valid_partial_date(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if not PARTIAL_DATE.match(v):
        raise ValueError("Dates must look like 1984, 1984-06 or 1984-06-15.")
    parts = [int(p) for p in v.split("-")]
    try:
        date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
    except ValueError as exc:
        raise ValueError("That is not a real calendar date.") from exc
    if parts[0] < 1000:
        raise ValueError("Year must be four digits.")
    return v


def _clean_list(values: list[str], max_len: int, max_items: int) -> list[str]:
    seen: dict[str, None] = {}
    for raw in values:
        item = " ".join(raw.split())
        if item:
            if len(item) > max_len:
                raise ValueError(f"Each entry must be at most {max_len} characters.")
            seen.setdefault(item, None)
    if len(seen) > max_items:
        raise ValueError(f"At most {max_items} entries are allowed.")
    return list(seen)


class MemoryIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=200_000)
    memory_date: str | None = None
    category: str = Field(default="general", min_length=1, max_length=40)
    people: list[str] = []
    tags: list[str] = []

    @field_validator("title", "category")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Must not be blank.")
        return v

    @field_validator("memory_date")
    @classmethod
    def _date(cls, v: str | None) -> str | None:
        return _valid_partial_date(v)

    @field_validator("people")
    @classmethod
    def _people(cls, v: list[str]) -> list[str]:
        return _clean_list(v, 80, 40)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return [t.lower() for t in _clean_list(v, 40, 40)]


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)
    ask: bool = True  # also generate a cited answer with the local LLM


class SummaryIn(BaseModel):
    memory_ids: list[str] = Field(min_length=1, max_length=40)
    focus: str = Field(default="", max_length=300)


class GhostIn(BaseModel):
    memory_ids: list[str] = Field(min_length=1, max_length=8)
    intensity: Literal["gentle", "mysterious", "spooky", "remembrance"] = "mysterious"
    language: str = Field(default="", max_length=40)


class TranscriptUpdate(BaseModel):
    text: str = Field(max_length=500_000)
    title: str = Field(default="", max_length=200)
    language: str = Field(default="", max_length=20)


class TranscribeIn(BaseModel):
    language: str = Field(default="", max_length=20)


class ConfirmIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    memory_date: str | None = None
    category: str = Field(default="family", max_length=40)
    people: list[str] = []
    tags: list[str] = []

    @field_validator("memory_date")
    @classmethod
    def _date(cls, v: str | None) -> str | None:
        return _valid_partial_date(v)


class LifeDocIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["document", "warranty", "recipe", "contact", "date", "task", "note"] = "note"
    notes: str = Field(default="", max_length=20_000)
    expiry_date: str | None = None
    remind_date: str | None = None

    @field_validator("expiry_date", "remind_date")
    @classmethod
    def _full_date(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        if not FULL_DATE.match(v):
            raise ValueError("Use the format YYYY-MM-DD.")
        return _valid_partial_date(v)


class PassphraseIn(BaseModel):
    passphrase: str = Field(min_length=1, max_length=256)
    current: str = Field(default="", max_length=256)


class StorageIn(BaseModel):
    data_dir: str = Field(min_length=1, max_length=500)


class RuntimeSettingsIn(BaseModel):
    llm_model: str | None = Field(default=None, min_length=1, max_length=120, pattern=r"^[\w.:\-/]+$")
    whisper_language: str | None = Field(default=None, max_length=10, pattern=r"^[a-zA-Z\-]*$")
