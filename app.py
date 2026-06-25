"""
Shortlist - Candidate Ranking Sandbox App

Premium UI for the hackathon demo. Upload candidates, rank them,
download results.
"""

import streamlit as st
import json
import csv
import io
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from scoring import compute_all_scores, is_honeypot, _get_title_tier
from reasoning import generate_reasoning
from config import TOP_N


# =========================================================================
# Custom CSS for premium look
# =========================================================================
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

/* Global */
html, body, [class*="css"] {
    font-family: 'Outfit', sans-serif;
}

/* Hero header */
.hero-title {
    font-size: 2.8rem;
    font-weight: 800;
    color: #eab308; /* Lemon yellow */
    margin-bottom: 0.2rem;
    letter-spacing: -0.02em;
}

.hero-subtitle {
    font-size: 1.15rem;
    color: #475569;
    font-weight: 400;
    margin-bottom: 1.5rem;
}

/* Stat cards */
.stat-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 1.2rem 1.5rem;
    text-align: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}
.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
}
.stat-number {
    font-size: 2rem;
    font-weight: 700;
    color: #eab308; /* Lemon yellow */
}
.stat-label {
    font-size: 0.8rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.3rem;
}

/* Feature pills */
.feature-row {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin: 1rem 0 1.5rem 0;
}
.feature-pill {
    background: #fef08a; /* Light lemon */
    border: 1px solid #fde047;
    border-radius: 100px;
    padding: 0.35rem 0.9rem;
    font-size: 0.78rem;
    color: #854d0e;
    font-weight: 600;
}

/* Section headers */
.section-header {
    font-size: 1.3rem;
    font-weight: 700;
    color: #334155;
    margin: 2rem 0 1rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Result cards */
.result-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 0.8rem;
    transition: border-color 0.2s ease;
    box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
}
.result-card:hover {
    border-color: #facc15;
}
.result-rank {
    font-size: 0.75rem;
    font-weight: 700;
    color: #ca8a04;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
.result-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #1e293b;
    margin: 0.2rem 0;
}
.result-meta {
    font-size: 0.82rem;
    color: #64748b;
}
.result-score {
    font-size: 1.4rem;
    font-weight: 700;
    color: #22c55e;
}

/* Upload area */
[data-testid="stFileUploader"] {
    border: 2px dashed #facc15 !important;
    border-radius: 16px !important;
    padding: 1rem !important;
    background-color: #fefce8;
}

/* Buttons */
.stButton > button[kind="primary"] {
    background: #facc15 !important; /* Lemon */
    color: #422006 !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.6rem 2rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 15px rgba(250, 204, 21, 0.4) !important;
    transform: translateY(-1px) !important;
}

/* Divider */
.gradient-divider {
    height: 2px;
    background: linear-gradient(90deg, transparent, #fde047, transparent);
    margin: 1.5rem 0;
    border: none;
}

/* How it works steps */
.step-container {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
    margin-bottom: 1rem;
}
.step-number {
    background: #facc15; /* Lemon */
    color: #422006;
    font-weight: 700;
    font-size: 0.85rem;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.step-text {
    color: #475569;
    font-size: 0.9rem;
    line-height: 1.5;
}
.step-text strong {
    color: #1e293b;
}
</style>
"""


def rank_candidates(candidates):
    """Run the ranking pipeline on a list of candidates."""
    filtered = []
    honeypots = []
    tier5_removed = []

    for candidate in candidates:
        title = candidate.get("profile", {}).get("current_title", "")
        tier = _get_title_tier(title)

        if tier == 5:
            tier5_removed.append(candidate["candidate_id"])
            continue

        hp_flagged, hp_reasons = is_honeypot(candidate)
        if hp_flagged:
            honeypots.append((candidate["candidate_id"], hp_reasons))
            continue

        filtered.append(candidate)

    scored = []
    for candidate in filtered:
        scores = compute_all_scores(candidate)
        scored.append({"candidate": candidate, "scores": scores})

    scored.sort(key=lambda x: (-round(x["scores"]["final_score"], 4), x["candidate"]["candidate_id"]))

    n = min(TOP_N, len(scored))
    top = scored[:n]

    results = []
    for rank, entry in enumerate(top, start=1):
        candidate = entry["candidate"]
        scores = entry["scores"]
        reasoning = generate_reasoning(candidate, scores, rank)
        results.append({
            "candidate_id": candidate["candidate_id"],
            "rank": rank,
            "score": round(scores["final_score"], 4),
            "reasoning": reasoning,
            "title": candidate["profile"]["current_title"],
            "company": candidate["profile"]["current_company"],
            "yoe": candidate["profile"]["years_of_experience"],
            "location": candidate["profile"].get("location", ""),
        })

    return results, tier5_removed, honeypots


def results_to_csv(results):
    """Convert results to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])
    for r in results:
        writer.writerow([r["candidate_id"], r["rank"], f"{r['score']:.4f}", r["reasoning"]])
    return output.getvalue()


def main():
    st.set_page_config(
        page_title="Shortlist Ranker",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Inject custom CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # =====================================================================
    # Sidebar - How It Works
    # =====================================================================
    with st.sidebar:
        st.markdown('<div class="hero-title" style="font-size:1.6rem;">⚡ How It Works</div>', unsafe_allow_html=True)
        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="step-container">
            <div class="step-number">1</div>
            <div class="step-text"><strong>Upload</strong> your candidate pool (JSONL or JSON)</div>
        </div>
        <div class="step-container">
            <div class="step-number">2</div>
            <div class="step-text"><strong>Filter</strong> - removes irrelevant titles & fake profiles instantly</div>
        </div>
        <div class="step-container">
            <div class="step-number">3</div>
            <div class="step-text"><strong>Score</strong> - 6 weighted components evaluate career fit, skills trust, and production evidence</div>
        </div>
        <div class="step-container">
            <div class="step-number">4</div>
            <div class="step-text"><strong>Modulate</strong> - behavioral signals (availability, response rate) gate the final score</div>
        </div>
        <div class="step-container">
            <div class="step-number">5</div>
            <div class="step-text"><strong>Rank & Explain</strong> - top candidates with fact-grounded reasoning</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

        st.markdown("""
        <div style="margin-top:1rem;">
            <div class="stat-label" style="margin-bottom:0.8rem;">SCORING WEIGHTS</div>
            <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:0.82rem;margin-bottom:0.3rem;">
                <span>Career Relevance</span><span style="color:#a78bfa;font-weight:600;">38%</span>
            </div>
            <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:0.82rem;margin-bottom:0.3rem;">
                <span>Skills Alignment</span><span style="color:#a78bfa;font-weight:600;">22%</span>
            </div>
            <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:0.82rem;margin-bottom:0.3rem;">
                <span>Keyword Coverage</span><span style="color:#a78bfa;font-weight:600;">16%</span>
            </div>
            <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:0.82rem;margin-bottom:0.3rem;">
                <span>Experience Fit</span><span style="color:#a78bfa;font-weight:600;">12%</span>
            </div>
            <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:0.82rem;margin-bottom:0.3rem;">
                <span>Education</span><span style="color:#a78bfa;font-weight:600;">7%</span>
            </div>
            <div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:0.82rem;">
                <span>Location</span><span style="color:#a78bfa;font-weight:600;">5%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

        st.markdown("""
        <div style="color:#64748b;font-size:0.75rem;line-height:1.6;">
            Deterministic · CPU-only · No LLM calls<br>
            No network access during ranking<br>
            100K candidates in ~20 seconds
        </div>
        """, unsafe_allow_html=True)

    # =====================================================================
    # Main Content
    # =====================================================================

    # Hero
    st.markdown('<div class="hero-title">Intelligent Candidate Discovery</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">AI-powered ranking for Senior AI Engineer - Ranking & Retrieval Systems</div>', unsafe_allow_html=True)

    # Feature pills
    st.markdown("""
    <div class="feature-row">
        <span class="feature-pill">🧠 Context-Aware Scoring</span>
        <span class="feature-pill">🛡️ Honeypot Detection</span>
        <span class="feature-pill">⚡ 20s for 100K Candidates</span>
        <span class="feature-pill">📊 Explainable Rankings</span>
        <span class="feature-pill">🚫 Zero Hallucinations</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

    # Upload section
    st.markdown('<div class="section-header">📂 Upload Candidate Pool</div>', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Drop your candidates file here",
        type=["jsonl", "json"],
        help="JSONL (one JSON object per line) or JSON array. Max 100 candidates for the sandbox demo.",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        try:
            content = uploaded.read().decode("utf-8")
            if uploaded.name.endswith(".jsonl"):
                candidates = [json.loads(line) for line in content.strip().split("\n") if line.strip()]
            else:
                parsed = json.loads(content)
                candidates = parsed if isinstance(parsed, list) else [parsed]
        except Exception as e:
            st.error(f"❌ Failed to parse file: {e}")
            return

        if len(candidates) > 100:
            st.warning(f"⚠️ File has {len(candidates):,} candidates. Sandbox processes the first 100.")
            candidates = candidates[:100]

        st.success(f"✅ Loaded **{len(candidates)}** candidates from `{uploaded.name}`")

        st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

        # Run button
        if st.button("⚡ Run Ranking Pipeline", type="primary", use_container_width=True):
            with st.spinner("Analyzing candidates..."):
                start = time.time()
                results, tier5, honeypots = rank_candidates(candidates)
                elapsed = time.time() - start

            # Stats row
            st.markdown('<div class="section-header">📊 Pipeline Results</div>', unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-number">{len(results)}</div>
                    <div class="stat-label">Ranked</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-number">{len(tier5)}</div>
                    <div class="stat-label">Filtered (Irrelevant)</div>
                </div>""", unsafe_allow_html=True)
            with c3:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-number">{len(honeypots)}</div>
                    <div class="stat-label">Honeypots Caught</div>
                </div>""", unsafe_allow_html=True)
            with c4:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-number">{elapsed:.1f}s</div>
                    <div class="stat-label">Runtime</div>
                </div>""", unsafe_allow_html=True)

            st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)

            if results:
                # Top candidates as cards
                st.markdown('<div class="section-header">🏆 Top Ranked Candidates</div>', unsafe_allow_html=True)

                for r in results[:10]:
                    col_info, col_score = st.columns([5, 1])
                    with col_info:
                        st.markdown(f"""
                        <div class="result-card">
                            <div class="result-rank">Rank #{r['rank']}</div>
                            <div class="result-title">{r['title']} at {r['company']}</div>
                            <div class="result-meta">{r['candidate_id']} · {r['yoe']:.1f} years · {r['location']}</div>
                        </div>""", unsafe_allow_html=True)
                    with col_score:
                        st.markdown(f"""
                        <div style="text-align:center;padding-top:1.2rem;">
                            <div class="result-score">{r['score']:.4f}</div>
                        </div>""", unsafe_allow_html=True)

                # Full table
                st.markdown('<div class="section-header">📋 Complete Rankings</div>', unsafe_allow_html=True)

                display_data = [{
                    "Rank": r["rank"],
                    "ID": r["candidate_id"],
                    "Title": r["title"],
                    "Company": r["company"],
                    "Experience": f"{r['yoe']:.1f}y",
                    "Location": r["location"],
                    "Score": f"{r['score']:.4f}",
                } for r in results]

                st.dataframe(display_data, use_container_width=True, hide_index=True)

                # Reasoning
                st.markdown('<div class="section-header">💬 Detailed Reasoning</div>', unsafe_allow_html=True)

                for r in results[:20]:
                    with st.expander(f"#{r['rank']} - {r['title']} @ {r['company']} ({r['score']:.4f})"):
                        st.write(r["reasoning"])

                # Download
                st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
                csv_content = results_to_csv(results)
                st.download_button(
                    label="📥 Download Submission CSV",
                    data=csv_content,
                    file_name="submission.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                )
            else:
                st.warning("No candidates passed the filters.")

            # Filter details
            if tier5 or honeypots:
                st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
                st.markdown('<div class="section-header">🔍 Filter Details</div>', unsafe_allow_html=True)

                if tier5:
                    with st.expander(f"Irrelevant Titles Removed ({len(tier5)})"):
                        st.caption("These candidates have non-engineering titles (HR, Marketing, etc.) and were filtered before scoring.")
                        st.code(", ".join(tier5[:20]) + ("..." if len(tier5) > 20 else ""))

                if honeypots:
                    with st.expander(f"Honeypots Detected ({len(honeypots)})"):
                        for cid, reasons in honeypots:
                            st.markdown(f"**{cid}**: {'; '.join(reasons)}")


if __name__ == "__main__":
    main()
