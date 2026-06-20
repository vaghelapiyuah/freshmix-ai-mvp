"""Skill loader (Phase 5).

Loads the packaged, versioned `freshmix-discovery` Agent Skill (SKILL.md +
schema.json + tools.json + grounding corpus) so the agent runs from the skill
package rather than an inline string. Same instructions whether used inline here
or registered as an Anthropic Agent Skill for Managed Agents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent / "skill" / "freshmix-discovery"

_FALLBACK = (
    "You are FreshMix AI. Turn mood, activity, language and a freshness level into "
    "a fresh-but-familiar queue. Never repeat recent/saved tracks. Explain each pick."
)


@dataclass
class Skill:
    name: str
    version: str
    description: str
    system: str                      # instructions (SKILL.md body)
    tools: list = field(default_factory=list)
    schema: dict = field(default_factory=dict)
    corpus_path: Path | None = None

    @property
    def tool_names(self) -> list[str]:
        return [t.get("name") for t in self.tools]


def _strip_frontmatter(md: str) -> str:
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4:].strip()
    return md.strip()


def load() -> Skill:
    """Load the packaged skill; fall back to a minimal inline skill if missing."""
    try:
        meta = json.loads((SKILL_DIR / "skill.json").read_text(encoding="utf-8"))
        body = _strip_frontmatter(
            (SKILL_DIR / meta["instructions_file"]).read_text(encoding="utf-8"))
        tools = json.loads((SKILL_DIR / meta["tools_file"]).read_text(encoding="utf-8"))
        schema = json.loads((SKILL_DIR / meta["schema_file"]).read_text(encoding="utf-8"))
        corpus = (SKILL_DIR / meta["corpus"]).resolve()
        return Skill(name=meta["name"], version=meta["version"],
                     description=meta["description"], system=body, tools=tools,
                     schema=schema, corpus_path=corpus if corpus.exists() else None)
    except Exception:
        return Skill(name="freshmix-discovery", version="0.0.0",
                     description="(fallback)", system=_FALLBACK)


def manifest() -> dict:
    """Machine-readable summary (for /v1/agent/skill)."""
    s = load()
    rows = 0
    if s.corpus_path and s.corpus_path.exists():
        rows = sum(1 for line in s.corpus_path.read_text(encoding="utf-8").splitlines()
                   if line.strip())
    return {"name": s.name, "version": s.version, "description": s.description,
            "tools": s.tool_names, "corpus_rows": rows,
            "schema_keys": list(s.schema.keys())}
