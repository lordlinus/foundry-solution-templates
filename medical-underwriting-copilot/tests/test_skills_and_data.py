"""The skills load through Agent Framework, and the synthetic data is what the README promises."""

from pathlib import Path

import seed_guidelines
import yaml
from agent_framework import SkillsProvider

ROOT = Path(__file__).resolve().parents[1]


def test_skills_have_valid_frontmatter_and_load():
    skills = sorted((ROOT / "src" / "agent" / "skills").glob("*/SKILL.md"))
    assert {p.parent.name for p in skills} == {"underwriting-report-format", "underwriting-decision"}
    for path in skills:
        front = yaml.safe_load(path.read_text().split("---")[1])
        assert front["name"] == path.parent.name and len(front["description"]) > 40
    SkillsProvider.from_paths(ROOT / "src" / "agent" / "skills")  # Constructs without error.


def test_guidelines_split_into_titled_sections():
    docs = [d for f in sorted(seed_guidelines.GUIDELINES.glob("*.md")) for d in seed_guidelines.sections(f)]
    assert len(docs) >= 10
    assert len({d["id"] for d in docs}) == len(docs)
    outcomes = ("Standard", "Rated", "Postpone", "Decline", "Refer to underwriter")
    assert all(d["title"] and any(o in d["content"] for o in outcomes) for d in docs)


def test_sample_records_are_generated_pdfs():
    samples = sorted((ROOT / "data" / "sample-records").glob("*.pdf"))
    assert len(samples) == 3
    assert all(p.read_bytes().startswith(b"%PDF") for p in samples)
