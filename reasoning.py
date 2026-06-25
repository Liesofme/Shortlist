"""
Reasoning string generator for Shortlist.

Produces fact-grounded, rank-appropriate reasoning strings that reference
specific data from each candidate's profile. Zero hallucination — every
fact stated is pulled programmatically from the candidate record.
"""

from typing import Dict, List


def _format_skills_list(matched_skills: List[Dict], max_skills: int = 5) -> str:
    """Format top matched skills into a readable string."""
    if not matched_skills:
        return ""
    top = matched_skills[:max_skills]
    parts = []
    for s in top:
        name = s["name"]
        prof = s["proficiency"]
        assessment = s.get("assessment")
        if assessment is not None:
            parts.append(f"{name} ({prof}, assessed {assessment:.0f}/100)")
        else:
            parts.append(f"{name} ({prof})")
    return ", ".join(parts)


def _format_concerns(scores: Dict, candidate: Dict, rank: int) -> str:
    """Generate honest concern statements based on actual gaps."""
    concerns = []
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    behavioral = scores.get("behavioral", {}).get("details", {})

    # Notice period
    notice = signals.get("notice_period_days", 0)
    if notice > 90:
        concerns.append(f"extended notice period ({notice} days)")
    elif notice > 60:
        concerns.append(f"moderate notice period ({notice} days)")

    # Location
    country = profile.get("country", "")
    location = profile.get("location", "")
    loc_score = scores.get("components", {}).get("location", {}).get("score", 0)
    if loc_score < 0.5:
        relocate = signals.get("willing_to_relocate", False)
        if country != "India":
            if relocate:
                concerns.append(f"based in {location} ({country}), willing to relocate")
            else:
                concerns.append(f"based in {location} ({country}), not open to relocation")
        else:
            concerns.append(f"based in {location}, outside preferred Pune/Noida hub")

    # Response rate
    rr = signals.get("recruiter_response_rate", 0)
    if rr < 0.3:
        concerns.append(f"low recruiter response rate ({rr:.0%})")

    # Open to work
    otw = signals.get("open_to_work_flag", False)
    if not otw and rr < 0.5:
        concerns.append("not marked as open to work")

    # Activity recency
    last_active_days = behavioral.get("last_active_days", 999)
    if last_active_days > 90:
        concerns.append(f"last active {last_active_days} days ago")

    # GitHub
    github = signals.get("github_activity_score", -1)
    if github == -1:
        concerns.append("no linked GitHub profile")
    elif github < 10:
        concerns.append(f"limited GitHub activity (score: {github:.0f}/100)")

    # Experience fit
    yoe = profile.get("years_of_experience", 0)
    if yoe < 4:
        concerns.append(f"relatively junior at {yoe:.1f} years of experience")
    elif yoe > 12:
        concerns.append(f"potentially overqualified at {yoe:.1f} years")

    # Consulting background
    consulting_penalty = scores.get("components", {}).get("career", {}).get("details", {}).get("consulting_penalty", 1.0)
    if consulting_penalty < 0.5:
        concerns.append("predominantly consulting/services career background")
    elif consulting_penalty < 0.8:
        concerns.append("some consulting/services tenure in career history")

    # Limit concerns based on rank
    if rank <= 10:
        return concerns[:2] if concerns else []  # Top 10: minor hedges only
    elif rank <= 30:
        return concerns[:3]
    elif rank <= 60:
        return concerns[:4]
    else:
        return concerns[:5]  # Bottom of top 100: more substantive concerns


def _format_strengths(scores: Dict, candidate: Dict) -> List[str]:
    """Generate strength statements grounded in actual data."""
    strengths = []
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    components = scores.get("components", {})
    career_details = components.get("career", {}).get("details", {})
    skills_details = components.get("skills", {}).get("details", {})
    keyword_details = components.get("keywords", {}).get("details", {})

    # Title/career strength
    title = profile.get("current_title", "")
    company = profile.get("current_company", "")
    title_tier = career_details.get("title_tier", 5)
    if title_tier <= 2:
        strengths.append(f"directly relevant role as {title} at {company}")
    elif title_tier == 3:
        strengths.append(f"adjacent technical role ({title}) with potential crossover")

    # Production evidence
    prod = career_details.get("production_evidence", 0)
    if prod >= 0.5:
        strengths.append("strong production deployment evidence in career history")
    elif prod >= 0.3:
        strengths.append("demonstrated production ML experience")

    # Skills alignment
    total_jd = skills_details.get("total_jd_skills", 0)
    if total_jd >= 8:
        strengths.append(f"broad JD skill coverage ({total_jd} relevant skills)")
    elif total_jd >= 5:
        strengths.append(f"solid skill alignment ({total_jd} relevant skills)")

    # Keyword coverage — IR/ranking
    kw_categories = keyword_details.get("categories", {})
    ranking_cov = kw_categories.get("ranking", {}).get("coverage", 0)
    embed_cov = kw_categories.get("embeddings", {}).get("coverage", 0)
    if ranking_cov >= 0.6:
        strengths.append("extensive ranking/retrieval experience evident in career descriptions")
    if embed_cov >= 0.6:
        strengths.append("significant embeddings/vector search experience")

    # Prestige
    prestige = career_details.get("prestige_bonus", 0)
    if prestige > 0:
        strengths.append(f"experience at leading tech company ({company})")

    # Location
    loc_score = components.get("location", {}).get("score", 0)
    location = profile.get("location", "")
    if loc_score >= 0.85:
        strengths.append(f"based in {location}, strong location fit")

    # Experience sweet spot
    yoe = profile.get("years_of_experience", 0)
    exp_score = components.get("experience", {}).get("score", 0)
    if exp_score >= 0.9:
        strengths.append(f"{yoe:.1f} years of experience, ideal for the role's 5-9 year target")

    # Behavioral strengths
    rr = signals.get("recruiter_response_rate", 0)
    if rr >= 0.7:
        strengths.append(f"highly responsive to recruiters ({rr:.0%} response rate)")

    otw = signals.get("open_to_work_flag", False)
    if otw:
        strengths.append("actively open to new opportunities")

    github = signals.get("github_activity_score", -1)
    if github >= 50:
        strengths.append(f"strong open-source/GitHub activity (score: {github:.0f}/100)")

    return strengths


def generate_reasoning(candidate: Dict, scores: Dict, rank: int) -> str:
    """
    Generate a fact-grounded reasoning string for a ranked candidate.

    Requirements met:
    - References specific facts from the candidate's profile
    - Connects to JD requirements
    - Acknowledges real concerns
    - Zero hallucinated claims
    - Genuine variation across candidates
    - Tone matches rank position
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    components = scores.get("components", {})
    skills_details = components.get("skills", {}).get("details", {})

    title = profile.get("current_title", "")
    company = profile.get("current_company", "")
    industry = profile.get("current_industry", "")
    yoe = profile.get("years_of_experience", 0)
    location = profile.get("location", "")
    country = profile.get("country", "")

    # Build reasoning parts
    parts = []

    # Opening: role identification with tone matching rank
    if rank <= 10:
        parts.append(
            f"Rank {rank}: {title} at {company} ({industry}) with {yoe:.1f} years of experience."
        )
    elif rank <= 30:
        parts.append(
            f"{title} at {company} ({industry}), {yoe:.1f} years of experience."
        )
    else:
        parts.append(
            f"{title} at {company}, {yoe:.1f} years of experience."
        )

    # Strengths
    strengths = _format_strengths(scores, candidate)
    if strengths:
        if rank <= 10:
            parts.append("Key strengths: " + "; ".join(strengths[:4]) + ".")
        elif rank <= 50:
            parts.append("Strengths: " + "; ".join(strengths[:3]) + ".")
        else:
            parts.append("Notable: " + "; ".join(strengths[:2]) + ".")

    # Top skills
    matched = skills_details.get("matched_skills", [])
    if matched:
        skills_str = _format_skills_list(matched, max_skills=4 if rank <= 20 else 3)
        parts.append(f"Top JD-aligned skills: {skills_str}.")

    # Behavioral snapshot
    rr = signals.get("recruiter_response_rate", 0)
    notice = signals.get("notice_period_days", 0)
    otw = signals.get("open_to_work_flag", False)
    bm = scores.get("behavioral_multiplier", 1.0)

    if rank <= 30:
        behavioral_parts = []
        if otw:
            behavioral_parts.append("open to work")
        behavioral_parts.append(f"response rate {rr:.0%}")
        behavioral_parts.append(f"notice period {notice}d")
        parts.append("Availability: " + ", ".join(behavioral_parts) + f" (behavioral multiplier: {bm:.2f}).")

    # Concerns (honest acknowledgment)
    concerns = _format_concerns(scores, candidate, rank)
    if concerns:
        if rank <= 10:
            parts.append("Minor considerations: " + "; ".join(concerns) + ".")
        elif rank <= 50:
            parts.append("Concerns: " + "; ".join(concerns) + ".")
        else:
            parts.append("Significant concerns: " + "; ".join(concerns) + ".")

    # Score breakdown for top candidates
    if rank <= 20:
        base = scores.get("base_score", 0)
        final = scores.get("final_score", 0)
        career_s = components.get("career", {}).get("score", 0)
        skills_s = components.get("skills", {}).get("score", 0)
        parts.append(
            f"Score breakdown: career={career_s:.2f}, skills={skills_s:.2f}, "
            f"base={base:.3f}, final={final:.4f}."
        )

    reasoning = " ".join(parts)

    # Ensure reasoning doesn't contain unescaped commas that break CSV
    # (the CSV writer handles this, but sanitize quotes)
    reasoning = reasoning.replace('"', "'")

    return reasoning
