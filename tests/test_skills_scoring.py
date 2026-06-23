"""
Unit tests for skills scoring logic.

Tests that:
- JD-relevant skills are weighted correctly
- Trust scoring (proficiency × duration × endorsements) works as expected
- Keyword-stuffers don't get high skills scores despite having AI skill names
- Negative signal skills (CV/speech) are properly penalized
"""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring import skills_score


def load_fixtures():
    fixtures_path = os.path.join(os.path.dirname(__file__), "fixtures", "handcrafted_candidates.json")
    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {entry["id"]: entry["candidate"] for entry in data}


FIXTURES = load_fixtures()


class TestSkillsScoring:
    """Test skills scoring against JD requirements."""

    def test_ideal_candidate_high_skills(self):
        """Ideal candidate with genuine AI/ML skills should score high."""
        candidate = FIXTURES["ideal_senior_ml"]
        score, details = skills_score(candidate)
        assert score >= 0.4, (
            f"Ideal candidate should have skills score >= 0.4, got {score}. "
            f"Matched: {details['total_jd_skills']} skills"
        )

    def test_keyword_stuffer_lower_skills(self):
        """HR Manager's AI skills should score lower due to low trust (short duration, few endorsements)."""
        stuffer = FIXTURES["keyword_stuffer_hr"]
        ideal = FIXTURES["ideal_senior_ml"]
        
        s_score, s_details = skills_score(stuffer)
        i_score, i_details = skills_score(ideal)
        
        assert i_score > s_score, (
            f"Ideal candidate skills ({i_score}) should beat keyword stuffer ({s_score}). "
            f"Stuffer has {s_details['total_jd_skills']} JD skills but lower trust."
        )

    def test_trust_scoring_rewards_duration(self):
        """Skills with longer duration should score higher than short duration."""
        # Create minimal candidates to test trust scoring directly
        long_duration = {
            "skills": [
                {"name": "Python", "proficiency": "advanced", "endorsements": 10, "duration_months": 60}
            ],
            "redrob_signals": {"skill_assessment_scores": {}}
        }
        short_duration = {
            "skills": [
                {"name": "Python", "proficiency": "advanced", "endorsements": 10, "duration_months": 3}
            ],
            "redrob_signals": {"skill_assessment_scores": {}}
        }
        
        long_score, _ = skills_score(long_duration)
        short_score, _ = skills_score(short_duration)
        
        assert long_score > short_score, (
            f"Longer duration ({long_score}) should beat shorter ({short_score})"
        )

    def test_trust_scoring_rewards_endorsements(self):
        """Skills with more endorsements should score higher."""
        many_endorse = {
            "skills": [
                {"name": "Python", "proficiency": "advanced", "endorsements": 50, "duration_months": 36}
            ],
            "redrob_signals": {"skill_assessment_scores": {}}
        }
        no_endorse = {
            "skills": [
                {"name": "Python", "proficiency": "advanced", "endorsements": 0, "duration_months": 36}
            ],
            "redrob_signals": {"skill_assessment_scores": {}}
        }
        
        many_score, _ = skills_score(many_endorse)
        no_score, _ = skills_score(no_endorse)
        
        assert many_score > no_score, (
            f"Many endorsements ({many_score}) should beat none ({no_score})"
        )

    def test_assessment_bonus(self):
        """Skill assessment scores should provide a bonus."""
        with_assessment = {
            "skills": [
                {"name": "Python", "proficiency": "advanced", "endorsements": 10, "duration_months": 36}
            ],
            "redrob_signals": {"skill_assessment_scores": {"Python": 85.0}}
        }
        without_assessment = {
            "skills": [
                {"name": "Python", "proficiency": "advanced", "endorsements": 10, "duration_months": 36}
            ],
            "redrob_signals": {"skill_assessment_scores": {}}
        }
        
        with_score, _ = skills_score(with_assessment)
        without_score, _ = skills_score(without_assessment)
        
        assert with_score > without_score, (
            f"Assessment ({with_score}) should beat no assessment ({without_score})"
        )

    def test_no_skills_scores_zero(self):
        """Candidate with no skills should score zero."""
        candidate = {
            "skills": [],
            "redrob_signals": {"skill_assessment_scores": {}}
        }
        score, _ = skills_score(candidate)
        assert score == 0.0

    def test_irrelevant_skills_score_low(self):
        """Candidate with only non-JD skills should score near zero."""
        candidate = {
            "skills": [
                {"name": "Photoshop", "proficiency": "expert", "endorsements": 50, "duration_months": 60},
                {"name": "Illustrator", "proficiency": "expert", "endorsements": 40, "duration_months": 48},
                {"name": "Figma", "proficiency": "advanced", "endorsements": 30, "duration_months": 36},
            ],
            "redrob_signals": {"skill_assessment_scores": {}}
        }
        score, details = skills_score(candidate)
        assert score <= 0.05, f"Irrelevant skills should score near 0, got {score}"

    def test_honeypot_skills_low_trust(self):
        """Honeypot with expert skills but 0 duration/endorsements should have low trust."""
        candidate = FIXTURES["honeypot_skill_stuffing"]
        score, details = skills_score(candidate)
        ideal_score, _ = skills_score(FIXTURES["ideal_senior_ml"])
        
        assert score < ideal_score * 0.5, (
            f"Honeypot skills ({score}) should be well below ideal ({ideal_score}). "
            f"Zero-evidence expert skills should have low trust."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
