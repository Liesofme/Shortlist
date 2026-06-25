"""
Scoring functions for Shortlist.

Each function takes a candidate record (dict) and returns a score in [0, 1].
All scoring logic is deterministic, explainable, and traceable to JD requirements.
"""

import math
import re
from datetime import datetime, date
from typing import Dict, List, Tuple, Optional, Any

from config import (
    TITLE_TIERS, TIER_SCORES, CONSULTING_FIRMS, PRESTIGE_COMPANIES,
    SKILL_WEIGHTS, NEGATIVE_SIGNAL_SKILLS, PROFICIENCY_WEIGHTS,
    JD_KEYWORDS, JD_KEYWORD_CATEGORY_WEIGHTS,
    EXPERIENCE_PEAK_YEARS, EXPERIENCE_SIGMA,
    INSTITUTION_TIER_SCORES, RELEVANT_FIELDS, FIELD_DEFAULT_SCORE,
    POSTGRAD_DEGREES, POSTGRAD_BONUS,
    PREFERRED_CITIES, TIER1_INDIA_CITIES,
    RECENCY_THRESHOLDS, RECENCY_DEFAULT,
    OPEN_TO_WORK_TRUE, OPEN_TO_WORK_FALSE_HIGH_RESPONSE, OPEN_TO_WORK_FALSE_DEFAULT,
    RESPONSE_RATE_MIN_SCORE, RESPONSE_RATE_MAX_SCORE, RESPONSE_RATE_MAX_THRESHOLD,
    NOTICE_PERIOD_THRESHOLDS,
    GITHUB_THRESHOLDS, GITHUB_NO_ACCOUNT,
    INTERVIEW_HIGH, INTERVIEW_MID, INTERVIEW_LOW_SCORE,
    VERIFICATION_SCORES,
    BEHAVIORAL_MIN, BEHAVIORAL_MAX,
    PRODUCTION_EVIDENCE_CATEGORIES,
    DISQUALIFIER_PURE_RESEARCH_MULTIPLIER,
    DISQUALIFIER_RECENT_LANGCHAIN_ONLY_MULTIPLIER,
    DISQUALIFIER_NO_CODE_18MO_MULTIPLIER,
    DISQUALIFIER_CV_SPEECH_ONLY_MULTIPLIER,
    DISQUALIFIER_TITLE_CHASER_MULTIPLIER,
    DISQUALIFIER_ALL_CONSULTING_MULTIPLIER,
    DISQUALIFIER_CURRENT_CONSULTING_MULTIPLIER,
    HONEYPOT_SINGLE_JOB_SLACK_MONTHS,
    HONEYPOT_TOTAL_CAREER_MULTIPLIER,
    HONEYPOT_TOTAL_CAREER_SLACK,
    HONEYPOT_EXPERT_NO_EVIDENCE_MIN,
    HONEYPOT_MIN_DESCRIPTION_LENGTH,
    WEIGHTS, REFERENCE_DATE,
)


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse a date string (YYYY-MM-DD) into a date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _days_since(date_str: Optional[str], ref_date: Optional[date] = None) -> int:
    """Return days between date_str and reference date. Returns 999 if unparseable."""
    if ref_date is None:
        ref_date = _parse_date(REFERENCE_DATE)
    d = _parse_date(date_str)
    if d is None or ref_date is None:
        return 999
    return max(0, (ref_date - d).days)


# =============================================================================
# 1. CAREER SCORE (weight: 0.38)
# =============================================================================

def _get_title_tier(title: str) -> int:
    """Get the relevance tier for a title. Returns 5 (irrelevant) if unknown."""
    return TITLE_TIERS.get(title, 5)


def _title_relevance_score(title: str) -> float:
    """Score a title's relevance to the JD. Returns 0.0-1.0."""
    tier = _get_title_tier(title)
    return TIER_SCORES.get(tier, 0.0)


def _is_consulting_firm(company: str) -> bool:
    """Check if a company is a known consulting/services firm."""
    return company in CONSULTING_FIRMS


def _is_prestige_company(company: str) -> bool:
    """Check if a company is a known prestige/AI-forward company."""
    return company in PRESTIGE_COMPANIES


def _compute_consulting_penalty(candidate: Dict) -> float:
    """
    Compute consulting career penalty.

    Bug fix #3: penalty weighted by recency and fraction of total tenure.
    - All-consulting career: 0.22× multiplier
    - Currently at consulting: 0.45× (unless prior product experience)
    - Past consulting (< 30% of career): 0.85× (soft)
    - No consulting: 1.0× (no penalty)
    """
    career = candidate.get("career_history", [])
    if not career:
        return 1.0

    total_months = sum(j.get("duration_months", 0) for j in career)
    if total_months == 0:
        return 1.0

    consulting_months = 0
    has_product_experience = False
    current_is_consulting = False

    for job in career:
        company = job.get("company", "")
        dur = job.get("duration_months", 0)
        is_current = job.get("is_current", False)

        if _is_consulting_firm(company):
            consulting_months += dur
            if is_current:
                current_is_consulting = True
        else:
            has_product_experience = True

    consulting_fraction = consulting_months / total_months if total_months > 0 else 0

    # All consulting, no product experience
    if consulting_fraction >= 0.95 and not has_product_experience:
        return DISQUALIFIER_ALL_CONSULTING_MULTIPLIER  # 0.22

    # Currently at consulting but has product experience
    if current_is_consulting and has_product_experience:
        # Scale by how much of career was at product companies
        product_fraction = 1.0 - consulting_fraction
        # More product experience → less penalty
        return 0.55 + 0.45 * product_fraction  # Range: 0.55 to 1.0

    # Currently at consulting, no product experience
    if current_is_consulting:
        return DISQUALIFIER_CURRENT_CONSULTING_MULTIPLIER  # 0.45

    # Past consulting only (not current)
    if consulting_fraction > 0.3:
        return 0.75 + 0.25 * (1.0 - consulting_fraction)  # Range: 0.75 to 1.0
    elif consulting_fraction > 0:
        return 0.85 + 0.15 * (1.0 - consulting_fraction)  # Range: 0.85 to 1.0

    return 1.0  # No consulting at all


def _compute_production_evidence(candidate: Dict) -> float:
    """
    Score production evidence from career descriptions.

    Returns a weighted score (0.0-1.0) based on keyword density across
    multiple evidence categories (IR/ranking, deployment, scale, etc.).
    """
    career = candidate.get("career_history", [])
    all_text = " ".join(j.get("description", "") for j in career).lower()

    if not all_text.strip():
        return 0.0

    total_score = 0.0
    total_weight = 0.0

    for category, config in PRODUCTION_EVIDENCE_CATEGORIES.items():
        weight = config["weight"]
        keywords = config["keywords"]
        total_weight += weight

        # Count distinct keyword matches (not total occurrences)
        matches = sum(1 for kw in keywords if kw in all_text)
        # Normalize: cap at 6 distinct matches per category for full score
        category_score = min(matches / 6.0, 1.0)
        total_score += weight * category_score

    return total_score / total_weight if total_weight > 0 else 0.0


def _compute_prestige_bonus(candidate: Dict) -> float:
    """Small prestige bonus (0.0-0.05) for known AI-forward companies."""
    career = candidate.get("career_history", [])
    current_company = candidate.get("profile", {}).get("current_company", "")

    # Highest bonus for currently at a prestige company
    if _is_prestige_company(current_company):
        return 0.05

    # Smaller bonus for past prestige experience
    for job in career:
        if _is_prestige_company(job.get("company", "")):
            return 0.03

    return 0.0


def _check_disqualifiers(candidate: Dict) -> float:
    """
    Check for JD-defined disqualifiers. Returns a multiplier (0.3-1.0).
    Multiple disqualifiers compound multiplicatively.
    """
    multiplier = 1.0
    career = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    all_desc = " ".join(j.get("description", "") for j in career).lower()
    skill_names = {s.get("name", "").lower() for s in skills}

    # 1. Pure research/academic with no production deployment
    research_terms = {"research", "paper", "publication", "phd", "thesis", "academic"}
    prod_terms = {"production", "deployed", "shipped", "served", "users", "scale", "pipeline"}
    research_count = sum(1 for t in research_terms if t in all_desc)
    prod_count = sum(1 for t in prod_terms if t in all_desc)
    if research_count >= 3 and prod_count == 0:
        multiplier *= DISQUALIFIER_PURE_RESEARCH_MULTIPLIER

    # 2. Only recent LangChain/API work, no pre-LLM ML experience
    langchain_only_terms = {"langchain", "openai api", "chatgpt", "gpt-4"}
    traditional_ml_terms = {"training", "model", "feature engineering", "sklearn",
                           "xgboost", "tensorflow", "pytorch", "embeddings",
                           "fine-tuning", "gradient", "loss function"}
    has_langchain = any(t in all_desc for t in langchain_only_terms)
    has_traditional_ml = sum(1 for t in traditional_ml_terms if t in all_desc)
    # Also check career history: if only recent roles mention AI
    if has_langchain and has_traditional_ml < 2:
        # Check if earliest AI-related role is recent
        yoe = candidate.get("profile", {}).get("years_of_experience", 0)
        if yoe < 2:
            multiplier *= DISQUALIFIER_RECENT_LANGCHAIN_ONLY_MULTIPLIER

    # 3. CV/speech/robotics without NLP/IR
    cv_speech_skills = {"computer vision", "image classification", "speech recognition",
                        "tts", "object detection", "robotics", "gans"}
    nlp_ir_skills = {"nlp", "information retrieval", "search", "ranking", "recommendation",
                     "embeddings", "bert", "transformers", "semantic search"}
    has_cv_speech = sum(1 for s in skill_names if s in cv_speech_skills)
    has_nlp_ir = sum(1 for s in skill_names if s in nlp_ir_skills)
    if has_cv_speech >= 3 and has_nlp_ir == 0:
        multiplier *= DISQUALIFIER_CV_SPEECH_ONLY_MULTIPLIER

    # 4. Title-chaser: many companies with short tenure and increasing seniority
    if len(career) >= 4:
        tenures = [j.get("duration_months", 0) for j in career]
        avg_tenure = sum(tenures) / len(tenures) if tenures else 0
        if avg_tenure < 18 and len(career) >= 5:
            multiplier *= DISQUALIFIER_TITLE_CHASER_MULTIPLIER

    return multiplier


def career_score(candidate: Dict) -> Tuple[float, Dict]:
    """
    Compute career score (0.0-1.0) based on title relevance, company type,
    production evidence, and disqualifier checks.

    Returns (score, details_dict) for reasoning generation.
    """
    profile = candidate.get("profile", {})
    title = profile.get("current_title", "")

    # Base title relevance
    title_score = _title_relevance_score(title)

    # If title is irrelevant (T5), short-circuit with near-zero score
    if title_score == 0.0:
        return 0.0, {
            "title_tier": 5,
            "title_score": 0.0,
            "consulting_penalty": 1.0,
            "production_evidence": 0.0,
            "prestige_bonus": 0.0,
            "disqualifier_multiplier": 1.0,
            "reason": f"Title '{title}' is irrelevant to Senior AI Engineer role",
        }

    # Also check career history titles for relevance
    career = candidate.get("career_history", [])
    career_title_scores = []
    for job in career:
        job_title = job.get("title", "")
        job_score = _title_relevance_score(job_title)
        dur = job.get("duration_months", 0)
        career_title_scores.append((job_score, dur))

    # Weighted average of career title scores (by duration)
    total_dur = sum(d for _, d in career_title_scores)
    if total_dur > 0:
        weighted_career_title = sum(s * d for s, d in career_title_scores) / total_dur
    else:
        weighted_career_title = title_score

    # Blend current title with career history (current title weighted more)
    blended_title = 0.6 * title_score + 0.4 * weighted_career_title

    # Company type penalty
    consulting_mult = _compute_consulting_penalty(candidate)

    # Production evidence
    prod_evidence = _compute_production_evidence(candidate)

    # Prestige bonus
    prestige = _compute_prestige_bonus(candidate)

    # Disqualifier checks
    disq_mult = _check_disqualifiers(candidate)

    # Combine: title relevance × consulting modifier × (0.5 + 0.5 × production_evidence) × disqualifiers + prestige
    raw_score = blended_title * consulting_mult * (0.45 + 0.55 * prod_evidence) * disq_mult + prestige
    score = min(max(raw_score, 0.0), 1.0)

    details = {
        "title_tier": _get_title_tier(title),
        "title_score": title_score,
        "blended_title": round(blended_title, 3),
        "consulting_penalty": round(consulting_mult, 3),
        "production_evidence": round(prod_evidence, 3),
        "prestige_bonus": round(prestige, 3),
        "disqualifier_multiplier": round(disq_mult, 3),
    }

    return round(score, 4), details


# =============================================================================
# 2. SKILLS SCORE (weight: 0.22)
# =============================================================================

def skills_score(candidate: Dict) -> Tuple[float, Dict]:
    """
    Score skills alignment with JD requirements.

    Uses proficiency × duration × endorsements as a "trust" metric per skill,
    weighted by the skill's importance to the JD.

    Returns (score, details_dict).
    """
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})
    assessments = signals.get("skill_assessment_scores", {})

    if not skills:
        return 0.0, {"matched_skills": [], "negative_skills": [], "total_jd_skills": 0}

    positive_score = 0.0
    negative_score = 0.0
    max_possible_positive = 0.0
    matched_skills = []
    negative_skills = []

    for skill in skills:
        name = skill.get("name", "")
        proficiency = skill.get("proficiency", "beginner")
        endorsements = skill.get("endorsements", 0)
        duration_months = skill.get("duration_months", 0)

        # Check positive JD skills
        if name in SKILL_WEIGHTS:
            importance = SKILL_WEIGHTS[name]
            prof_weight = PROFICIENCY_WEIGHTS.get(proficiency, 0.15)

            # Trust score: combines proficiency, duration, and endorsements
            duration_factor = min(duration_months / 36.0, 1.0) if duration_months > 0 else 0.1
            endorsement_factor = min(endorsements / 10.0, 1.0) if endorsements > 0 else 0.1
            trust = prof_weight * (0.5 * duration_factor + 0.3 * endorsement_factor + 0.2)

            # Assessment bonus: if candidate has a verified assessment score
            assessment_bonus = 0.0
            if name in assessments:
                score_val = assessments[name]
                if score_val >= 60:
                    assessment_bonus = 0.15
                elif score_val >= 40:
                    assessment_bonus = 0.05

            skill_score = importance * (trust + assessment_bonus)
            positive_score += skill_score
            max_possible_positive += importance * 1.15  # max trust + max assessment

            matched_skills.append({
                "name": name,
                "importance": importance,
                "proficiency": proficiency,
                "trust": round(trust, 3),
                "assessment": assessments.get(name),
                "score": round(skill_score, 3),
            })

        # Check negative signal skills
        elif name in NEGATIVE_SIGNAL_SKILLS:
            neg_weight = abs(NEGATIVE_SIGNAL_SKILLS[name])
            prof_weight = PROFICIENCY_WEIGHTS.get(proficiency, 0.15)
            negative_score += neg_weight * prof_weight
            negative_skills.append(name)

    # Normalize positive score
    if max_possible_positive > 0:
        normalized = positive_score / max_possible_positive
    else:
        normalized = 0.0

    # Apply negative signal penalty (but don't go below 0)
    # Negative signals matter more when there aren't many positive signals
    neg_penalty = min(negative_score * 0.1, 0.3)  # Cap negative penalty
    final = max(normalized - neg_penalty, 0.0)
    final = min(final, 1.0)

    # Sort matched skills by score descending for reasoning
    matched_skills.sort(key=lambda x: x["score"], reverse=True)

    details = {
        "matched_skills": matched_skills[:10],  # Top 10 for reasoning
        "negative_skills": negative_skills,
        "total_jd_skills": len(matched_skills),
        "positive_raw": round(positive_score, 3),
        "negative_raw": round(negative_score, 3),
    }

    return round(final, 4), details


# =============================================================================
# 3. KEYWORD COVERAGE (weight: 0.16)
# =============================================================================

def keyword_coverage(candidate: Dict) -> Tuple[float, Dict]:
    """
    Score JD keyword coverage across all candidate text fields.

    Checks headline, summary, career descriptions, and skill names
    for JD-relevant terms grouped by category.

    Returns (score, details_dict).
    """
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    skills = candidate.get("skills", [])

    # Build combined text
    text_parts = [
        profile.get("headline", ""),
        profile.get("summary", ""),
    ]
    for job in career:
        text_parts.append(job.get("description", ""))
        text_parts.append(job.get("title", ""))
    for skill in skills:
        text_parts.append(skill.get("name", ""))

    combined_text = " ".join(text_parts).lower()

    if not combined_text.strip():
        return 0.0, {"categories": {}, "total_matches": 0}

    total_score = 0.0
    total_weight = 0.0
    category_details = {}

    for category, keywords in JD_KEYWORDS.items():
        weight = JD_KEYWORD_CATEGORY_WEIGHTS.get(category, 1.0)
        total_weight += weight

        matches = [kw for kw in keywords if kw.lower() in combined_text]
        # Normalize: cap at 5 distinct matches per category for full score
        coverage = min(len(matches) / 5.0, 1.0)
        total_score += weight * coverage

        category_details[category] = {
            "matches": matches[:5],
            "count": len(matches),
            "coverage": round(coverage, 3),
        }

    final = total_score / total_weight if total_weight > 0 else 0.0
    total_matches = sum(d["count"] for d in category_details.values())

    return round(final, 4), {
        "categories": category_details,
        "total_matches": total_matches,
    }


# =============================================================================
# 4. EXPERIENCE SCORE (weight: 0.12)
# =============================================================================

def experience_score(candidate: Dict) -> Tuple[float, Dict]:
    """
    Score years of experience using a Gaussian curve peaked at 7 years.

    The JD states 5-9 years as a soft range, with ideal around 6-8 years.

    Returns (score, details_dict).
    """
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)

    # Gaussian: exp(-0.5 * ((yoe - peak) / sigma)^2)
    z = (yoe - EXPERIENCE_PEAK_YEARS) / EXPERIENCE_SIGMA
    score = math.exp(-0.5 * z * z)

    details = {
        "years": yoe,
        "peak": EXPERIENCE_PEAK_YEARS,
        "sigma": EXPERIENCE_SIGMA,
    }

    return round(score, 4), details


# =============================================================================
# 5. EDUCATION SCORE (weight: 0.07)
# =============================================================================

def education_score(candidate: Dict) -> Tuple[float, Dict]:
    """
    Score education based on institution tier, field relevance, and degree level.

    Returns (score, details_dict).
    """
    education = candidate.get("education", [])

    if not education:
        return 0.2, {"institutions": [], "has_postgrad": False}

    best_score = 0.0
    has_postgrad = False
    institution_details = []

    for edu in education:
        institution = edu.get("institution", "")
        tier = edu.get("tier", "unknown")
        field = edu.get("field_of_study", "")
        degree = edu.get("degree", "")

        tier_score = INSTITUTION_TIER_SCORES.get(tier, 0.4)
        field_score = RELEVANT_FIELDS.get(field, FIELD_DEFAULT_SCORE)

        # Check for postgrad
        if degree in POSTGRAD_DEGREES:
            has_postgrad = True

        edu_score = tier_score * field_score
        best_score = max(best_score, edu_score)

        institution_details.append({
            "institution": institution,
            "tier": tier,
            "field": field,
            "degree": degree,
            "score": round(edu_score, 3),
        })

    # Apply postgrad bonus
    if has_postgrad:
        best_score = min(best_score + POSTGRAD_BONUS, 1.0)

    details = {
        "institutions": institution_details,
        "has_postgrad": has_postgrad,
        "best_score": round(best_score, 3),
    }

    return round(best_score, 4), details


# =============================================================================
# 6. LOCATION SCORE (weight: 0.05)
# =============================================================================

def location_score(candidate: Dict) -> Tuple[float, Dict]:
    """
    Score location alignment with JD preference (Pune/Noida preferred).

    Returns (score, details_dict).
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})

    location = profile.get("location", "")
    country = profile.get("country", "")
    willing_to_relocate = signals.get("willing_to_relocate", False)
    work_mode = signals.get("preferred_work_mode", "")

    score = 0.25  # Default: international, not relocating

    if country == "India":
        # Check for preferred cities
        loc_lower = location.lower()
        is_preferred = any(city.lower() in loc_lower for city in PREFERRED_CITIES)
        is_tier1 = any(city.lower() in loc_lower for city in TIER1_INDIA_CITIES)

        if is_preferred:
            score = 1.0
        elif is_tier1:
            score = 0.85
        else:
            score = 0.65
    else:
        # International
        if willing_to_relocate:
            score = 0.45
        elif work_mode == "remote":
            score = 0.35
        else:
            score = 0.25

    details = {
        "location": location,
        "country": country,
        "willing_to_relocate": willing_to_relocate,
        "work_mode": work_mode,
    }

    return round(score, 4), details


# =============================================================================
# 7. BEHAVIORAL MULTIPLIER (multiplicative modifier)
# =============================================================================

def behavioral_multiplier(candidate: Dict) -> Tuple[float, Dict]:
    """
    Compute behavioral availability multiplier (0.35-1.35).

    This is applied multiplicatively on top of the base score.
    Philosophy: availability should gate the final score, not just nudge it.

    Returns (multiplier, details_dict).
    """
    signals = candidate.get("redrob_signals", {})

    factors = {}

    # 1. Recency (last_active_date)
    last_active = signals.get("last_active_date", "")
    days = _days_since(last_active)
    recency_factor = RECENCY_DEFAULT
    for threshold, factor in RECENCY_THRESHOLDS:
        if days <= threshold:
            recency_factor = factor
            break
    factors["recency"] = recency_factor

    # 2. Open to work
    open_to_work = signals.get("open_to_work_flag", False)
    response_rate = signals.get("recruiter_response_rate", 0)
    if open_to_work:
        otw_factor = OPEN_TO_WORK_TRUE
    elif response_rate > 0.5:
        otw_factor = OPEN_TO_WORK_FALSE_HIGH_RESPONSE
    else:
        otw_factor = OPEN_TO_WORK_FALSE_DEFAULT
    factors["open_to_work"] = otw_factor

    # 3. Recruiter response rate (linear mapping)
    if response_rate >= RESPONSE_RATE_MAX_THRESHOLD:
        rr_factor = RESPONSE_RATE_MAX_SCORE
    else:
        # Linear interpolation from min to max
        t = response_rate / RESPONSE_RATE_MAX_THRESHOLD
        rr_factor = RESPONSE_RATE_MIN_SCORE + t * (RESPONSE_RATE_MAX_SCORE - RESPONSE_RATE_MIN_SCORE)
    factors["response_rate"] = round(rr_factor, 3)

    # 4. Notice period
    notice_days = signals.get("notice_period_days", 0)
    notice_factor = NOTICE_PERIOD_THRESHOLDS[-1][1]  # Default: last threshold
    for threshold, factor in NOTICE_PERIOD_THRESHOLDS:
        if notice_days <= threshold:
            notice_factor = factor
            break
    factors["notice_period"] = notice_factor

    # 5. GitHub activity
    github = signals.get("github_activity_score", -1)
    if github == -1:
        gh_factor = GITHUB_NO_ACCOUNT
    else:
        gh_factor = GITHUB_THRESHOLDS[-1][1]  # Default: lowest
        for threshold, factor in GITHUB_THRESHOLDS:
            if github >= threshold:
                gh_factor = factor
                break
    factors["github"] = gh_factor

    # 6. Interview completion rate
    icr = signals.get("interview_completion_rate", 0)
    if icr >= INTERVIEW_HIGH[0]:
        icr_factor = INTERVIEW_HIGH[1]
    elif icr >= INTERVIEW_MID[0]:
        icr_factor = INTERVIEW_MID[1]
    else:
        icr_factor = INTERVIEW_LOW_SCORE
    factors["interview_completion"] = icr_factor

    # 7. Verification
    verified_count = sum([
        signals.get("verified_email", False),
        signals.get("verified_phone", False),
        signals.get("linkedin_connected", False),
    ])
    ver_factor = VERIFICATION_SCORES.get(verified_count, 0.85)
    factors["verification"] = ver_factor

    # Combine multiplicatively
    combined = 1.0
    for f in factors.values():
        combined *= f

    # Clamp to range
    combined = max(BEHAVIORAL_MIN, min(BEHAVIORAL_MAX, combined))

    details = {
        "factors": factors,
        "last_active_days": days,
        "notice_period_days": notice_days,
        "github_score": github,
        "response_rate_raw": response_rate,
        "open_to_work_raw": open_to_work,
    }

    return round(combined, 4), details


# =============================================================================
# 8. HONEYPOT DETECTION
# =============================================================================

def is_honeypot(candidate: Dict) -> Tuple[bool, List[str]]:
    """
    Detect honeypot candidates with deliberately impossible profiles.

    Returns (is_flagged, list_of_reasons).

    Conservative checks that generalize to unseen data:
    1. Single job duration exceeds total claimed experience
    2. Total career months grossly exceed claimed years
    3. Many expert/advanced skills with zero evidence
    4. Suspiciously short descriptions for long tenures
    """
    reasons = []
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    skills = candidate.get("skills", [])
    yoe = profile.get("years_of_experience", 0)

    yoe_months = yoe * 12

    # Check 1: Single job duration exceeds total experience
    for job in career:
        dur = job.get("duration_months", 0)
        if dur > yoe_months + HONEYPOT_SINGLE_JOB_SLACK_MONTHS:
            reasons.append(
                f"Job '{job.get('title', '')}' at '{job.get('company', '')}' has "
                f"duration {dur} months but total experience is only {yoe} years "
                f"({yoe_months} months)"
            )

    # Check 2: Total career months grossly exceed claimed years
    total_career_months = sum(j.get("duration_months", 0) for j in career)
    max_allowed = yoe_months * HONEYPOT_TOTAL_CAREER_MULTIPLIER + HONEYPOT_TOTAL_CAREER_SLACK
    if total_career_months > max_allowed:
        reasons.append(
            f"Total career months ({total_career_months}) grossly exceed "
            f"claimed experience ({yoe} years = {yoe_months} months)"
        )

    # Check 3: Many expert/advanced skills with zero evidence
    expert_no_evidence = sum(
        1 for s in skills
        if s.get("proficiency", "") in ("expert", "advanced")
        and s.get("duration_months", 0) == 0
        and s.get("endorsements", 0) == 0
    )
    if expert_no_evidence >= HONEYPOT_EXPERT_NO_EVIDENCE_MIN:
        reasons.append(
            f"{expert_no_evidence} skills marked expert/advanced with zero "
            f"duration and zero endorsements"
        )

    # Check 4: Suspiciously short descriptions for long tenures
    for job in career:
        dur = job.get("duration_months", 0)
        desc = job.get("description", "")
        if dur >= 36 and len(desc.strip()) < HONEYPOT_MIN_DESCRIPTION_LENGTH:
            reasons.append(
                f"Job at '{job.get('company', '')}' lasted {dur} months but "
                f"description is only {len(desc.strip())} characters"
            )

    return len(reasons) > 0, reasons


# =============================================================================
# 9. COMPOSITE SCORE COMPUTATION
# =============================================================================

def compute_all_scores(candidate: Dict) -> Dict:
    """
    Compute all scoring components and the final composite score.

    Returns a dictionary with all scores and details for reasoning generation.
    """
    # Check honeypot first
    hp_flagged, hp_reasons = is_honeypot(candidate)

    # Compute component scores
    c_score, c_details = career_score(candidate)
    s_score, s_details = skills_score(candidate)
    k_score, k_details = keyword_coverage(candidate)
    e_score, e_details = experience_score(candidate)
    ed_score, ed_details = education_score(candidate)
    l_score, l_details = location_score(candidate)
    b_mult, b_details = behavioral_multiplier(candidate)

    # Weighted base score
    base_score = (
        WEIGHTS["career"]     * c_score +
        WEIGHTS["skills"]     * s_score +
        WEIGHTS["keywords"]   * k_score +
        WEIGHTS["experience"] * e_score +
        WEIGHTS["education"]  * ed_score +
        WEIGHTS["location"]   * l_score
    )

    # Final score = base × behavioral multiplier
    final_score = base_score * b_mult

    # Honeypots get zeroed
    if hp_flagged:
        final_score = 0.0

    return {
        "candidate_id": candidate.get("candidate_id", ""),
        "final_score": round(final_score, 6),
        "base_score": round(base_score, 6),
        "behavioral_multiplier": b_mult,
        "is_honeypot": hp_flagged,
        "honeypot_reasons": hp_reasons,
        "components": {
            "career":     {"score": c_score, "weight": WEIGHTS["career"],     "details": c_details},
            "skills":     {"score": s_score, "weight": WEIGHTS["skills"],     "details": s_details},
            "keywords":   {"score": k_score, "weight": WEIGHTS["keywords"],   "details": k_details},
            "experience": {"score": e_score, "weight": WEIGHTS["experience"], "details": e_details},
            "education":  {"score": ed_score,"weight": WEIGHTS["education"],  "details": ed_details},
            "location":   {"score": l_score, "weight": WEIGHTS["location"],   "details": l_details},
        },
        "behavioral": {"multiplier": b_mult, "details": b_details},
    }
