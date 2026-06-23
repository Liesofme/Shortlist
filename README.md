# Redrob Intelligent Candidate Discovery & Ranking

A deterministic, CPU-only, network-free candidate ranking pipeline for the
**Senior AI Engineer** role at Redrob AI. Processes 100,000 candidate profiles
and selects the top 100 best-fit candidates with detailed reasoning.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the ranking pipeline
python rank.py --candidates ./candidates.jsonl --out ./submission.csv

# Validate the output
python validate_submission.py submission.csv

# Run unit tests
python -m pytest tests/ -v

# Launch the demo sandbox
streamlit run app.py
```

## Architecture

### Three-Stage Pipeline

```
Stage 1: COARSE FILTER (~95% elimination)
  ├── Remove Tier 5 titles (HR, Marketing, Accountant, etc.)
  ├── Remove honeypot candidates (impossible timelines)
  └── ~5,000 candidates → Stage 2

Stage 2: WEIGHTED COMPOSITE SCORING
  ├── career_score      (38%) — title relevance × company type × production evidence
  ├── skills_score      (22%) — JD-relevant skills × proficiency × duration × endorsements
  ├── keyword_coverage  (16%) — JD keyword density across all text fields
  ├── experience_score  (12%) — Gaussian peak at 5-9 years
  ├── education_score   ( 7%) — institution tier × field match × postgrad bonus
  └── location_score    ( 5%) — India preferred, Pune/Noida best

Stage 3: BEHAVIORAL MODULATION
  └── final_score = base_score × behavioral_multiplier (0.35-1.35×)
```

### Scoring Weight Rationale

| Component | Weight | Rationale (traced to JD) |
|---|---|---|
| **Career** | 0.38 | Title + company + production evidence is the hardest signal to fake. The JD explicitly states this is "not a keyword-matching exercise" and warns about candidates with AI keyword lists but irrelevant career histories. Career is the decisive signal against the ~4,000 keyword-stuffer trap candidates in the pool. |
| **Skills** | 0.22 | JD specifies concrete must-have skills (embeddings, vector DBs, Python, evaluation frameworks). Trust-weighted scoring (proficiency × duration × endorsements) ensures skill claims are substantiated, not just listed. |
| **Keywords** | 0.16 | Catches "implicit fit" — candidates whose career descriptions mention ranking/retrieval/production ML work even when their title doesn't immediately suggest it. The JD says "a candidate who built a recommendation system without using trendy vocabulary" is a fit. |
| **Experience** | 0.12 | JD states 5-9 years as a soft range. Gaussian curve centered at 7 years reflects the "ideal candidate sketch" of 6-8 years total. |
| **Education** | 0.07 | Tier-1 CS/EE education is a positive signal but not a hard requirement. Lower weight ensures strong candidates from tier-2/3 institutions are not unfairly penalized. |
| **Location** | 0.05 | JD prefers Pune/Noida with Tier-1 India cities also welcome. International candidates are case-by-case. Minor weight since location is the most negotiable attribute. |

### Behavioral Multiplier Rationale

Applied multiplicatively (not additively) per the signals doc's guidance that
availability should "gate the final score, not just nudge it."

| Signal | Effect | Rationale |
|---|---|---|
| Recency | 0.35-1.0× | A candidate inactive for 6+ months is effectively unreachable |
| Open to work | 0.60-1.0× | Not toggling the badge isn't disqualifying if response rate is high (Bug fix #1) |
| Response rate | 0.40-1.15× | Direct measure of actual reachability |
| Notice period | 0.70-1.0× | 90-120 days common at strong Indian product companies (Bug fix #2) |
| GitHub | 0.95-1.10× | Open-source activity is a nice-to-have |
| Interview completion | 0.90-1.05× | Low completion suggests flakiness |
| Verification | 0.85-1.05× | Verified contacts enable actual outreach |

### Bug Fixes from v1

1. **`open_to_work_flag=False` penalty softened** from 0.25× to 0.60×, overridden to 0.75× if `recruiter_response_rate > 0.5`. Many strong candidates don't toggle badges.
2. **Notice period cliff removed** at 90 days. 90-120 day notice periods are standard at CRED, Razorpay, Dream11-type employers and are negotiable.
3. **Consulting penalty weighted by recency + fraction**. Early-career consulting followed by product-company work gets soft penalty (0.55-1.0×), not the flat 0.45× that v1 applied uniformly.

### Honeypot Detection

Conservative, generalizable checks (no hard-coded IDs):

1. Single job `duration_months` exceeds `years_of_experience × 12 + 6`
2. Total career months exceed `years_of_experience × 12 × 2 + 24`
3. 5+ skills at expert/advanced with both `duration_months=0` and `endorsements=0`
4. Job descriptions < 50 characters for 36+ month tenures

## Project Structure

```
├── rank.py                          # Main pipeline: single command → CSV
├── scoring.py                       # All scoring functions (testable module)
├── reasoning.py                     # Fact-grounded reasoning generator
├── config.py                        # All weights, thresholds, keyword sets
├── app.py                           # Streamlit sandbox demo
├── validate_submission.py           # Official submission validator
├── requirements.txt                 # Dependencies (pytest, streamlit)
├── submission_metadata.yaml         # Submission metadata
├── README.md                        # This file
├── tests/
│   ├── test_career_scoring.py       # Career score unit tests
│   ├── test_skills_scoring.py       # Skills score unit tests
│   ├── test_honeypot.py             # Honeypot detection unit tests
│   └── fixtures/
│       └── handcrafted_candidates.json  # Synthetic edge-case test data
└── candidates.jsonl                 # Input data (100K candidates)
```

## Reproduce Command

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

Runtime: ~30 seconds on CPU, 16 GB RAM, no network access.

## Testing

```bash
# Run all 34 unit tests
python -m pytest tests/ -v

# Test coverage includes:
# - Ideal candidate scores high on career
# - Keyword-stuffer trap (HR Manager with AI skills) scores near zero
# - Consulting-only career penalized vs product career
# - Mixed consulting+product career handled proportionally
# - Honeypot timeline impossibility detected
# - Honeypot skill stuffing detected
# - Legitimate postgrad NOT falsely flagged
# - Skills trust scoring rewards duration/endorsements
# - Assessment scores provide verified bonus
```

## Sandbox Demo

```bash
streamlit run app.py
```

Upload a small candidate file (JSONL or JSON, ≤100 candidates) to see the
ranking pipeline in action with downloadable CSV output.
