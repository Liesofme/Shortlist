"""
Unit tests for honeypot detection.

Tests that:
- Impossible timeline (single job > total experience) is caught
- Skill stuffing (many expert skills with zero evidence) is caught
- Legitimate postgrad candidates are NOT falsely flagged
- Normal candidates are NOT flagged
"""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring import is_honeypot


def load_fixtures():
    fixtures_path = os.path.join(os.path.dirname(__file__), "fixtures", "handcrafted_candidates.json")
    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {entry["id"]: entry["candidate"] for entry in data}


FIXTURES = load_fixtures()


class TestHoneypotDetection:
    """Test honeypot detection catches deliberate impossibilities."""

    def test_timeline_honeypot_flagged(self):
        """Job duration (120 months) exceeding total experience (5 years) should be flagged."""
        candidate = FIXTURES["honeypot_timeline"]
        flagged, reasons = is_honeypot(candidate)
        assert flagged is True, (
            f"Timeline honeypot should be flagged. "
            f"Job duration=120mo, YoE=5.0y=60mo. Reasons: {reasons}"
        )
        assert any("duration" in r.lower() or "months" in r.lower() for r in reasons), (
            f"Should mention timeline issue. Reasons: {reasons}"
        )

    def test_skill_stuffing_honeypot_flagged(self):
        """8 expert skills with 0 duration and 0 endorsements should be flagged."""
        candidate = FIXTURES["honeypot_skill_stuffing"]
        flagged, reasons = is_honeypot(candidate)
        assert flagged is True, (
            f"Skill stuffing honeypot should be flagged. Reasons: {reasons}"
        )
        assert any("expert" in r.lower() or "skills" in r.lower() for r in reasons), (
            f"Should mention skill stuffing. Reasons: {reasons}"
        )

    def test_legitimate_postgrad_not_flagged(self):
        """Legitimate candidate with M.Tech should NOT be falsely flagged."""
        candidate = FIXTURES["legitimate_postgrad"]
        flagged, reasons = is_honeypot(candidate)
        assert flagged is False, (
            f"Legitimate postgrad candidate should NOT be flagged as honeypot. "
            f"Reasons given: {reasons}"
        )

    def test_ideal_candidate_not_flagged(self):
        """Ideal candidate should never be flagged."""
        candidate = FIXTURES["ideal_senior_ml"]
        flagged, reasons = is_honeypot(candidate)
        assert flagged is False, (
            f"Ideal candidate should NOT be flagged. Reasons: {reasons}"
        )

    def test_consulting_only_not_flagged(self):
        """Consulting-only career is penalized but not a honeypot."""
        candidate = FIXTURES["consulting_only"]
        flagged, reasons = is_honeypot(candidate)
        assert flagged is False, (
            f"Consulting career is a scoring penalty, not a honeypot. Reasons: {reasons}"
        )

    def test_keyword_stuffer_not_flagged_as_honeypot(self):
        """Keyword stuffers are handled by scoring, not honeypot detection."""
        candidate = FIXTURES["keyword_stuffer_hr"]
        flagged, reasons = is_honeypot(candidate)
        assert flagged is False, (
            f"Keyword stuffers should be handled by career_score, not honeypot. "
            f"Reasons: {reasons}"
        )

    def test_inactive_candidate_not_flagged(self):
        """Inactive but legitimate candidate should not be flagged."""
        candidate = FIXTURES["inactive_strong_candidate"]
        flagged, reasons = is_honeypot(candidate)
        assert flagged is False, (
            f"Inactive but real candidate should not be a honeypot. Reasons: {reasons}"
        )


class TestHoneypotEdgeCases:
    """Test edge cases in honeypot detection."""

    def test_borderline_timeline_not_flagged(self):
        """Job duration within slack tolerance should not be flagged."""
        candidate = {
            "candidate_id": "CAND_9999001",
            "profile": {"years_of_experience": 5.0, "current_title": "Software Engineer"},
            "career_history": [
                {
                    "company": "TestCo",
                    "title": "Software Engineer",
                    "start_date": "2021-01-01",
                    "end_date": None,
                    "duration_months": 64,  # 60 months + 4 slack (within 6-month tolerance)
                    "is_current": True,
                    "industry": "Software",
                    "company_size": "51-200",
                    "description": "Built production ML systems for search ranking. Led the development of hybrid retrieval pipelines combining dense and sparse methods for product search."
                }
            ],
            "skills": [],
        }
        flagged, reasons = is_honeypot(candidate)
        assert flagged is False, (
            f"64 months with 5yr experience is within slack tolerance. Reasons: {reasons}"
        )

    def test_just_over_threshold_flagged(self):
        """Job duration clearly over threshold should be flagged."""
        candidate = {
            "candidate_id": "CAND_9999002",
            "profile": {"years_of_experience": 3.0, "current_title": "ML Engineer"},
            "career_history": [
                {
                    "company": "TestCo",
                    "title": "ML Engineer",
                    "start_date": "2018-01-01",
                    "end_date": None,
                    "duration_months": 80,  # 3yr = 36mo, threshold 42mo, clearly over
                    "is_current": True,
                    "industry": "Software",
                    "company_size": "51-200",
                    "description": "ML work."
                }
            ],
            "skills": [],
        }
        flagged, reasons = is_honeypot(candidate)
        assert flagged is True, (
            f"80 months with 3yr experience should be flagged. Reasons: {reasons}"
        )

    def test_multiple_overlapping_jobs_not_flagged(self):
        """Multiple concurrent jobs (consulting moonlighting) should not trigger total-career check
        if individual jobs are within bounds."""
        candidate = {
            "candidate_id": "CAND_9999003",
            "profile": {"years_of_experience": 8.0, "current_title": "Data Scientist"},
            "career_history": [
                {
                    "company": "CompanyA", "title": "Data Scientist",
                    "start_date": "2020-01-01", "end_date": None,
                    "duration_months": 72, "is_current": True,
                    "industry": "Software", "company_size": "201-500",
                    "description": "Built ML models for production use including recommendation engines and search ranking systems with real-time serving infrastructure."
                },
                {
                    "company": "CompanyB", "title": "ML Consultant",
                    "start_date": "2018-01-01", "end_date": "2020-01-01",
                    "duration_months": 24, "is_current": False,
                    "industry": "Consulting", "company_size": "51-200",
                    "description": "Consulted on NLP projects."
                }
            ],
            "skills": [],
        }
        flagged, reasons = is_honeypot(candidate)
        # Total: 96 months, claimed 8yr=96mo, well within 2x+24 = 216 threshold
        assert flagged is False, (
            f"Normal multi-job career should not be flagged. Reasons: {reasons}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
