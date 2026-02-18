"""
Skills loader for PDF Agent.

Loads skill prompt files from the skills directory and provides them
as additional context for the Claude agent's system prompt.
"""

import os
from pathlib import Path
from typing import List


SKILLS_DIR = Path(__file__).parent


def load_skills_from_directory(directory: str = None) -> "SkillSet":
    """Load all skill .md files from the given directory."""
    skills_path = Path(directory) if directory else SKILLS_DIR
    skills = SkillSet()

    if not skills_path.exists():
        return skills

    for filepath in skills_path.glob("*.md"):
        try:
            content = filepath.read_text(encoding="utf-8")
            skills.add(filepath.stem, content)
        except Exception as e:
            print(f"Warning: Failed to load skill {filepath.name}: {e}")

    return skills


class SkillSet:
    """Collection of loaded skills."""

    def __init__(self):
        self._skills: dict[str, str] = {}

    def add(self, name: str, content: str):
        self._skills[name] = content

    def as_prompt(self) -> str:
        """Format all skills as a system prompt section."""
        if not self._skills:
            return ""

        parts = ["# Available Skills\n"]
        for name, content in self._skills.items():
            parts.append(content)
            parts.append("")

        return "\n".join(parts)

    def get(self, name: str) -> str:
        """Get a specific skill's content."""
        return self._skills.get(name, "")

    @property
    def names(self) -> List[str]:
        return list(self._skills.keys())
