"""
Unit tests for career scoring logic.

Tests that:
- Senior ML Engineers at product companies score high
- Keyword-stuffer trap candidates (irrelevant titles) score near zero
- Consulting-only careers score lower than product careers
- Mixed consulting+product careers are penalized proportionally
"""

import json
import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring import career_score, _compute_consulting_penalty, _compute_production_evidence, _title_relevance_score


def load_fixtures():
    """Load handcrafted test candidates."""
    fixtures_path = os.path.join(os.path.dirname(__file__), "fixtures", "handcrafted_candidates.json")
    with open(fixtures_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {entry["id"]: entry["candidate"] for entry in data}


FIXTURES = load_fixtures()


class TestTitleRelevance:
    """Test that title relevance scoring matches JD requirements."""

    def test_senior_ml_engineer_is_tier1(self):
        score = _title_relevance_score("Senior Machine Learning Engineer")
        assert score == 1.0, f"Senior ML Engineer should be Tier 1 (1.0), got {score}"

    def test_search_engineer_is_tier1(self):
        score = _title_relevance_score("Search Engineer")
        assert score == 1.0

    def test_ml_engineer_is_tier2(self):
        score = _title_relevance_score("ML Engineer")
        assert score == 0.85

    def test_hr_manager_is_tier5(self):
        score = _title_relevance_score("HR Manager")
        assert score == 0.0, "HR Manager should score 0.0 (Tier 5)"

    def test_marketing_manager_is_tier5(self):
        score = _title_relevance_score("Marketing Manager")
        assert score == 0.0

    def test_software_engineer_is_tier4(self):
        score = _title_relevance_score("Software Engineer")
        assert score == 0.30


class TestCareerScoring:
    """Test career scoring for handcrafted candidates."""

    def test_ideal_candidate_scores_high(self):
        """Senior ML Engineer at Flipkart with strong production evidence should score high."""
        candidate = FIXTURES["ideal_senior_ml"]
        score, details = career_score(candidate)
        assert score >= 0.65, (
            f"Ideal candidate (Senior ML Engineer at Flipkart) should score >= 0.65, "
            f"got {score}. Details: {details}"
        )

    def test_keyword_stuffer_scores_near_zero(self):
        """HR Manager with AI skills should score near zero on career."""
        candidate = FIXTURES["keyword_stuffer_hr"]
        score, details = career_score(candidate)
        assert score <= 0.05, (
            f"Keyword stuffer (HR Manager) should score <= 0.05, got {score}. "
            f"Title tier: {details['title_tier']}"
        )

    def test_consulting_only_lower_than_product(self):
        """All-consulting career should score lower than product career."""
        consulting = FIXTURES["consulting_only"]
        product = FIXTURES["ideal_senior_ml"]
        
        c_score, _ = career_score(consulting)
        p_score, _ = career_score(product)
        
        assert p_score > c_score, (
            f"Product career ({p_score}) should outscore consulting-only ({c_score})"
        )

    def test_mixed_career_not_heavily_penalized(self):
        """Candidate who started at consulting but moved to product should not be crushed."""
        candidate = FIXTURES["product_after_consulting"]
        score, details = career_score(candidate)
        
        # Should still score reasonably well (above 0.4) since current role is product
        assert score >= 0.40, (
            f"Mixed career (Wipro → Swiggy) should score >= 0.40, got {score}. "
            f"Consulting penalty: {details['consulting_penalty']}"
        )

    def test_mixed_career_scores_between_pure_types(self):
        """Mixed career should score between consulting-only and pure product."""
        consulting = FIXTURES["consulting_only"]
        mixed = FIXTURES["product_after_consulting"]
        product = FIXTURES["ideal_senior_ml"]
        
        c_score, _ = career_score(consulting)
        m_score, _ = career_score(mixed)
        p_score, _ = career_score(product)
        
        assert c_score < m_score < p_score, (
            f"Expected consulting ({c_score:.3f}) < mixed ({m_score:.3f}) < product ({p_score:.3f})"
        )


class TestConsultingPenalty:
    """Test the consulting penalty calculation directly."""

    def test_no_consulting_no_penalty(self):
        candidate = FIXTURES["ideal_senior_ml"]
        penalty = _compute_consulting_penalty(candidate)
        assert penalty == 1.0, f"No consulting should mean no penalty, got {penalty}"

    def test_all_consulting_heavy_penalty(self):
        candidate = FIXTURES["consulting_only"]
        penalty = _compute_consulting_penalty(candidate)
        assert penalty <= 0.30, f"All-consulting career should be heavily penalized, got {penalty}"

    def test_past_consulting_soft_penalty(self):
        """Past consulting with current product role should get soft penalty."""
        candidate = FIXTURES["product_after_consulting"]
        penalty = _compute_consulting_penalty(candidate)
        assert 0.55 <= penalty <= 1.0, (
            f"Past consulting + current product should get soft penalty (0.55-1.0), got {penalty}"
        )


class TestProductionEvidence:
    """Test production evidence scoring from career descriptions."""

    def test_strong_production_evidence(self):
        candidate = FIXTURES["ideal_senior_ml"]
        score = _compute_production_evidence(candidate)
        assert score >= 0.4, f"Ideal candidate should have strong production evidence, got {score}"

    def test_keyword_stuffer_low_production(self):
        candidate = FIXTURES["keyword_stuffer_hr"]
        score = _compute_production_evidence(candidate)
        assert score <= 0.2, f"HR Manager should have low production evidence, got {score}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
