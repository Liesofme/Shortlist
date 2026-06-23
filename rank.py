#!/usr/bin/env python3
"""
Redrob Candidate Ranking Pipeline — Main Entrypoint

Usage:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Produces a CSV with the top 100 candidates ranked for the Senior AI Engineer
role, with reasoning for each selection. Runs on CPU only, no network calls,
target runtime < 60 seconds on 100K candidates.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

from config import TITLE_TIERS, TIER_SCORES, TOP_N
from scoring import compute_all_scores, is_honeypot, _get_title_tier
from reasoning import generate_reasoning


def load_candidates(path: str) -> List[Dict]:
    """Load candidates from a JSONL file."""
    candidates = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                candidates.append(json.loads(line))
    return candidates


def coarse_filter(candidates: List[Dict]) -> List[Dict]:
    """
    Stage 1: Fast coarse filter to eliminate clearly irrelevant candidates.

    Removes:
    - Tier 5 titles (HR, Marketing, Accountant, etc.) — the keyword-stuffer trap
    - Honeypot candidates with impossible profiles

    This reduces the pool from ~100K to ~30K before detailed scoring.
    """
    filtered = []
    stats = {"total": len(candidates), "tier5_removed": 0, "honeypot_removed": 0, "passed": 0}

    for candidate in candidates:
        title = candidate.get("profile", {}).get("current_title", "")
        tier = _get_title_tier(title)

        # Remove T5 (irrelevant) titles
        if tier == 5:
            stats["tier5_removed"] += 1
            continue

        # Check honeypot
        hp_flagged, _ = is_honeypot(candidate)
        if hp_flagged:
            stats["honeypot_removed"] += 1
            continue

        filtered.append(candidate)
        stats["passed"] += 1

    return filtered, stats


def score_candidates(candidates: List[Dict]) -> List[Dict]:
    """
    Stage 2 + 3: Compute detailed scores for all candidates that passed
    the coarse filter.

    Returns a list of score records sorted by final_score descending.
    """
    scored = []
    for candidate in candidates:
        scores = compute_all_scores(candidate)
        scored.append({
            "candidate": candidate,
            "scores": scores,
        })

    # Sort by final_score descending (rounded to 4 decimals to match CSV output),
    # tie-break by candidate_id ascending for determinism
    scored.sort(
        key=lambda x: (-round(x["scores"]["final_score"], 4), x["candidate"]["candidate_id"])
    )

    return scored


def select_top_n(scored: List[Dict], n: int = TOP_N) -> List[Dict]:
    """Select the top N candidates."""
    return scored[:n]


def generate_submission(
    top_candidates: List[Dict],
    output_path: str,
) -> None:
    """
    Generate the submission CSV with ranking, scores, and reasoning.

    Format: candidate_id, rank, score, reasoning
    """
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])

        for rank, entry in enumerate(top_candidates, start=1):
            candidate = entry["candidate"]
            scores = entry["scores"]

            candidate_id = candidate["candidate_id"]
            score = scores["final_score"]
            reasoning = generate_reasoning(candidate, scores, rank)

            writer.writerow([candidate_id, rank, f"{score:.4f}", reasoning])


def print_summary(top_candidates: List[Dict], filter_stats: Dict, elapsed: float) -> None:
    """Print a summary of the ranking results."""
    print(f"\n{'='*70}")
    print(f"REDROB CANDIDATE RANKING — RESULTS SUMMARY")
    print(f"{'='*70}")
    print(f"\nPipeline completed in {elapsed:.2f} seconds")
    print(f"\nFilter stats:")
    print(f"  Total candidates:   {filter_stats['total']:,}")
    print(f"  Tier 5 removed:     {filter_stats['tier5_removed']:,}")
    print(f"  Honeypots removed:  {filter_stats['honeypot_removed']:,}")
    print(f"  Passed to scoring:  {filter_stats['passed']:,}")

    print(f"\nTop 15 ranked candidates:")
    print(f"{'Rank':<6}{'ID':<16}{'Title':<35}{'Company':<20}{'Score':<10}{'YoE':<6}")
    print(f"{'-'*6}{'-'*16}{'-'*35}{'-'*20}{'-'*10}{'-'*6}")

    for rank, entry in enumerate(top_candidates[:15], start=1):
        c = entry["candidate"]
        s = entry["scores"]
        p = c["profile"]
        print(
            f"{rank:<6}{c['candidate_id']:<16}{p['current_title']:<35}"
            f"{p['current_company']:<20}{s['final_score']:<10.4f}{p['years_of_experience']:<6.1f}"
        )

    # Title distribution in top 100
    print(f"\nTitle distribution in top {len(top_candidates)}:")
    from collections import Counter
    title_dist = Counter(
        e["candidate"]["profile"]["current_title"] for e in top_candidates
    )
    for title, count in title_dist.most_common():
        print(f"  {title}: {count}")

    # Country distribution
    print(f"\nCountry distribution in top {len(top_candidates)}:")
    country_dist = Counter(
        e["candidate"]["profile"]["country"] for e in top_candidates
    )
    for country, count in country_dist.most_common():
        print(f"  {country}: {count}")

    # Score distribution
    scores = [e["scores"]["final_score"] for e in top_candidates]
    print(f"\nScore range: {min(scores):.4f} - {max(scores):.4f}")
    print(f"Score mean:  {sum(scores)/len(scores):.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Redrob Candidate Ranking Pipeline"
    )
    parser.add_argument(
        "--candidates", required=True,
        help="Path to candidates.jsonl file"
    )
    parser.add_argument(
        "--out", required=True,
        help="Path to output submission CSV"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print detailed summary"
    )
    args = parser.parse_args()

    start_time = time.time()

    # Stage 0: Load candidates
    print(f"Loading candidates from {args.candidates}...")
    candidates = load_candidates(args.candidates)
    load_time = time.time()
    print(f"  Loaded {len(candidates):,} candidates in {load_time - start_time:.2f}s")

    # Stage 1: Coarse filter
    print("Stage 1: Coarse filtering...")
    filtered, filter_stats = coarse_filter(candidates)
    filter_time = time.time()
    print(f"  {filter_stats['passed']:,} candidates passed filter in {filter_time - load_time:.2f}s")

    # Stage 2+3: Detailed scoring
    print("Stage 2: Scoring candidates...")
    scored = score_candidates(filtered)
    score_time = time.time()
    print(f"  Scored {len(scored):,} candidates in {score_time - filter_time:.2f}s")

    # Select top N
    top = select_top_n(scored, TOP_N)
    print(f"  Selected top {len(top)} candidates")

    # Generate submission CSV
    print(f"Writing submission to {args.out}...")
    generate_submission(top, args.out)

    elapsed = time.time() - start_time
    print(f"\nDone! Total time: {elapsed:.2f} seconds")

    # Print summary
    print_summary(top, filter_stats, elapsed)

    # Warn if over budget
    if elapsed > 300:
        print(f"\n⚠️  WARNING: Runtime {elapsed:.0f}s exceeds 5-minute budget!")
    elif elapsed > 60:
        print(f"\n⚠️  NOTE: Runtime {elapsed:.0f}s — consider optimization")

    return 0


if __name__ == "__main__":
    sys.exit(main())
