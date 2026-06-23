"""
Redrob Candidate Ranking — Streamlit Sandbox App

Accepts a small candidate JSONL/JSON file upload (≤100 candidates),
runs the ranking pipeline, and returns a downloadable CSV.
"""

import streamlit as st
import json
import csv
import io
import time
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from scoring import compute_all_scores, is_honeypot, _get_title_tier
from reasoning import generate_reasoning
from config import TOP_N


def rank_candidates(candidates):
    """Run the ranking pipeline on a list of candidates."""
    # Stage 1: Coarse filter
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

    # Stage 2: Score
    scored = []
    for candidate in filtered:
        scores = compute_all_scores(candidate)
        scored.append({"candidate": candidate, "scores": scores})

    # Sort
    scored.sort(key=lambda x: (-x["scores"]["final_score"], x["candidate"]["candidate_id"]))

    # Select top N (or all if fewer)
    n = min(TOP_N, len(scored))
    top = scored[:n]

    # Generate reasoning
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
        page_title="Redrob Candidate Ranker",
        page_icon="🎯",
        layout="wide",
    )

    st.title("🎯 Redrob Intelligent Candidate Ranker")
    st.markdown("""
    **Senior AI Engineer — Ranking & Retrieval Systems**

    Upload a candidate file (JSONL or JSON array, ≤100 candidates) to rank them
    against the job description. The pipeline uses a deterministic, explainable
    scoring system — no LLM calls, no network access.
    """)

    st.divider()

    # File upload
    uploaded = st.file_uploader(
        "Upload candidates file",
        type=["jsonl", "json"],
        help="JSONL (one JSON object per line) or JSON array format"
    )

    if uploaded is not None:
        # Parse file
        try:
            content = uploaded.read().decode("utf-8")
            if uploaded.name.endswith(".jsonl"):
                candidates = [json.loads(line) for line in content.strip().split("\n") if line.strip()]
            else:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    candidates = parsed
                else:
                    candidates = [parsed]
        except Exception as e:
            st.error(f"Failed to parse file: {e}")
            return

        st.success(f"Loaded **{len(candidates)}** candidates")

        if len(candidates) > 100:
            st.warning("File contains more than 100 candidates. Only the first 100 will be processed.")
            candidates = candidates[:100]

        # Run ranking
        if st.button("🚀 Run Ranking Pipeline", type="primary"):
            with st.spinner("Scoring candidates..."):
                start = time.time()
                results, tier5, honeypots = rank_candidates(candidates)
                elapsed = time.time() - start

            st.success(f"Ranking complete in **{elapsed:.2f}s**")

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Candidates Ranked", len(results))
            col2.metric("Tier 5 Filtered", len(tier5))
            col3.metric("Honeypots Detected", len(honeypots))
            col4.metric("Runtime", f"{elapsed:.1f}s")

            st.divider()

            # Results table
            st.subheader("📊 Ranked Candidates")

            if results:
                # Display as a clean table
                display_data = []
                for r in results:
                    display_data.append({
                        "Rank": r["rank"],
                        "ID": r["candidate_id"],
                        "Title": r["title"],
                        "Company": r["company"],
                        "YoE": r["yoe"],
                        "Score": f"{r['score']:.4f}",
                    })

                st.dataframe(display_data, use_container_width=True, hide_index=True)

                # Expandable reasoning
                st.subheader("📝 Detailed Reasoning")
                for r in results[:20]:  # Show first 20
                    with st.expander(f"Rank {r['rank']}: {r['candidate_id']} — {r['title']} @ {r['company']} (Score: {r['score']:.4f})"):
                        st.write(r["reasoning"])

                # Download CSV
                csv_content = results_to_csv(results)
                st.download_button(
                    label="📥 Download Submission CSV",
                    data=csv_content,
                    file_name="submission.csv",
                    mime="text/csv",
                    type="primary",
                )
            else:
                st.warning("No candidates passed the filters. All candidates were either "
                          "irrelevant titles (Tier 5) or honeypots.")

            # Filter details
            if tier5 or honeypots:
                st.divider()
                st.subheader("🔍 Filter Details")

                if tier5:
                    with st.expander(f"Tier 5 Filtered ({len(tier5)} candidates)"):
                        st.write("These candidates have irrelevant titles (HR, Marketing, etc.) "
                                "and were removed before scoring:")
                        st.code(", ".join(tier5[:20]) + ("..." if len(tier5) > 20 else ""))

                if honeypots:
                    with st.expander(f"Honeypots Detected ({len(honeypots)} candidates)"):
                        for cid, reasons in honeypots:
                            st.write(f"**{cid}**: {'; '.join(reasons)}")


if __name__ == "__main__":
    main()
