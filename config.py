"""
Configuration for the Shortlist candidate ranking system.

All scoring weights, thresholds, title tiers, company lists, keyword sets,
and signal mappings live here. No magic numbers in scoring code.
"""

# =============================================================================
# Scoring Component Weights (must sum to 1.0)
# =============================================================================
WEIGHTS = {
    "career":     0.38,   # Title relevance × company type × production evidence
    "skills":     0.22,   # JD-relevant skills with trust scoring
    "keywords":   0.16,   # JD keyword density across all text
    "experience": 0.12,   # Gaussian peak at 5-9 years
    "education":  0.07,   # Institution tier × field match
    "location":   0.05,   # India preferred, Pune/Noida best
}

# =============================================================================
# Title Relevance Tiers
# Each title maps to a tier, which maps to a base relevance score.
# Derived from data exploration: 47 unique titles in the dataset.
# =============================================================================
TITLE_TIERS = {
    # Tier 1 — Core match: directly relevant to ranking/retrieval/NLP
    "Search Engineer":                    1,
    "Recommendation Systems Engineer":    1,
    "Senior NLP Engineer":                1,
    "NLP Engineer":                       1,
    "Lead AI Engineer":                   1,
    "Senior AI Engineer":                 1,
    "Staff Machine Learning Engineer":    1,
    "Senior Machine Learning Engineer":   1,
    "Senior Applied Scientist":           1,

    # Tier 2 — Strong: ML/AI background, likely transferable
    "ML Engineer":                        2,
    "Machine Learning Engineer":          2,
    "Applied ML Engineer":                2,
    "AI Engineer":                        2,
    "Senior Software Engineer (ML)":      2,
    "Senior Data Scientist":              2,
    "Data Scientist":                     2,
    "AI Research Engineer":               2,

    # Tier 3 — Adjacent: may have relevant experience in descriptions
    "AI Specialist":                      3,
    "Junior ML Engineer":                 3,
    "Senior Software Engineer":           3,
    "Backend Engineer":                   3,
    "Data Engineer":                      3,
    "Senior Data Engineer":               3,
    "Analytics Engineer":                 3,
    "Computer Vision Engineer":           3,  # Disqualifier if no NLP/IR, but some crossover

    # Tier 4 — Weak: only relevant if career descriptions show ML/IR work
    "Software Engineer":                  4,
    "Full Stack Developer":               4,
    "Cloud Engineer":                     4,
    "DevOps Engineer":                    4,
    "Data Analyst":                       4,
    "Java Developer":                     4,
    ".NET Developer":                     4,
    "Frontend Engineer":                  4,
    "Mobile Developer":                   4,
    "QA Engineer":                        4,

    # Tier 5 — Irrelevant: the keyword-stuffer trap
    "HR Manager":                         5,
    "Marketing Manager":                  5,
    "Content Writer":                     5,
    "Sales Executive":                    5,
    "Accountant":                         5,
    "Operations Manager":                 5,
    "Customer Support":                   5,
    "Graphic Designer":                   5,
    "Civil Engineer":                     5,
    "Mechanical Engineer":                5,
    "Business Analyst":                   5,
    "Project Manager":                    5,
}

TIER_SCORES = {
    1: 1.00,
    2: 0.85,
    3: 0.55,
    4: 0.30,
    5: 0.00,
}

# =============================================================================
# Consulting Firms — for career penalty calculation
# =============================================================================
CONSULTING_FIRMS = {
    "TCS", "Infosys", "Wipro", "Accenture", "Cognizant", "Capgemini",
    "Mindtree", "HCL", "Tech Mahindra", "LTIMindtree", "Mphasis",
    "L&T Infotech", "Hexaware", "NIIT", "Persistent Systems",
    "Genpact", "Mu Sigma", "Cyient", "Zensar", "Birlasoft",
}

# Prestige product companies (minor tie-breaking signal)
PRESTIGE_COMPANIES = {
    # Global tech giants
    "Google", "Meta", "Apple", "Microsoft", "Amazon", "Netflix", "OpenAI",
    "DeepMind", "Anthropic", "Salesforce", "LinkedIn", "Uber", "Airbnb",
    "Stripe", "Databricks", "Snowflake", "Palantir",
    # Strong Indian product companies
    "Flipkart", "Razorpay", "CRED", "Zomato", "Swiggy", "Paytm",
    "PhonePe", "Dream11", "Meesho", "Zerodha", "Ola", "Myntra",
    "ShareChat", "Nykaa", "Freshworks", "Zoho", "InMobi", "Cure.fit",
    "Groww", "Jupiter", "Lenskart",
    # AI-focused companies
    "Mad Street Den", "Sarvam AI", "Niramai", "Saarthi.ai",
    "Locobuzz", "Haptik", "Yellow.ai", "Observe.AI",
    "Genpact AI", "Wysa", "Aganitha",
}

# =============================================================================
# JD-Relevant Skill Categories with Importance Weights
# =============================================================================
SKILL_WEIGHTS = {
    # Critical skills — directly match JD requirements (weight 3.0)
    "Python":                    3.0,
    "Embeddings":                3.0,
    "Sentence Transformers":     3.0,
    "FAISS":                     3.0,
    "Vector Database":           3.0,
    "Elasticsearch":             3.0,
    "OpenSearch":                3.0,
    "Information Retrieval":     3.0,
    "Recommendation Systems":    3.0,
    "Semantic Search":           3.0,
    "Pinecone":                  3.0,
    "Weaviate":                  3.0,
    "Qdrant":                    3.0,
    "Milvus":                    3.0,

    # Important skills — strong alignment (weight 2.0)
    "NLP":                       2.0,
    "BERT":                      2.0,
    "Transformers":              2.0,
    "PyTorch":                   2.0,
    "TensorFlow":                2.0,
    "Deep Learning":             2.0,
    "Machine Learning":          2.0,
    "A/B Testing":               2.0,
    "RAG":                       2.0,
    "XGBoost":                   2.0,
    "Neural Networks":           2.0,
    "Scikit-learn":              2.0,
    "Statistical Modeling":      2.0,
    "Keras":                     2.0,

    # Nice-to-have skills (weight 1.0)
    "Fine-tuning LLMs":          1.0,
    "LoRA":                      1.0,
    "LangChain":                 1.0,
    "Docker":                    1.0,
    "Kubernetes":                1.0,
    "MLOps":                     1.0,
    "Hugging Face":              1.0,
    "OpenAI API":                1.0,
    "Feature Engineering":       1.0,
    "Spark":                     1.0,
    "Airflow":                   1.0,
    "AWS":                       1.0,
    "GCP":                       1.0,
    "Azure":                     1.0,
    "Weights & Biases":          1.0,
    "BentoML":                   1.0,
}

# Skills that are negative signals if overrepresented (CV/speech/robotics)
NEGATIVE_SIGNAL_SKILLS = {
    "Computer Vision":           -0.5,
    "Image Classification":      -0.5,
    "Speech Recognition":        -0.5,
    "TTS":                       -0.5,
    "GANs":                      -0.5,
    "Robotics":                  -0.5,
    "Object Detection":          -0.5,
}

PROFICIENCY_WEIGHTS = {
    "expert":       1.00,
    "advanced":     0.75,
    "intermediate": 0.45,
    "beginner":     0.15,
}

# =============================================================================
# JD Keyword Sets for Coverage Scoring
# Checked across headline, summary, career descriptions, skill names
# =============================================================================
JD_KEYWORDS = {
    # Ranking/retrieval — highest relevance (weight 3.0)
    "ranking": [
        "ranking", "retrieval", "search", "recommendation", "re-ranking",
        "reranking", "information retrieval", "dense retrieval", "hybrid search",
        "BM25", "inverted index", "learning to rank", "NDCG", "MRR", "MAP",
        "semantic search", "query understanding", "relevance",
    ],
    # Embeddings/vector — high relevance (weight 2.5)
    "embeddings": [
        "embedding", "sentence-transformer", "sentence transformer",
        "vector database", "vector search", "FAISS", "Pinecone", "Weaviate",
        "Qdrant", "Milvus", "OpenSearch", "Elasticsearch", "BGE", "E5",
        "embedding drift", "index refresh", "ANN", "approximate nearest",
    ],
    # Production ML — high relevance (weight 2.0)
    "production": [
        "production", "deployed", "shipped", "served", "real-time",
        "latency", "throughput", "SLA", "monitoring", "inference",
        "serving", "scaled", "million", "thousands", "scale",
        "pipeline", "end-to-end", "microservice",
    ],
    # Evaluation — medium relevance (weight 1.5)
    "evaluation": [
        "A/B test", "evaluation", "offline evaluation", "online evaluation",
        "precision", "recall", "F1", "NDCG", "MRR", "MAP", "metric",
        "regression test", "quality", "benchmark",
    ],
    # LLM/fine-tuning — medium relevance (weight 1.5)
    "llm": [
        "fine-tuning", "fine-tune", "LoRA", "QLoRA", "PEFT", "adapter",
        "LLM", "large language model", "prompt", "RAG",
        "retrieval augmented", "instruction tuning",
    ],
    # Infrastructure — lower relevance (weight 1.0)
    "infra": [
        "Kubernetes", "Docker", "CI/CD", "MLOps", "Airflow",
        "distributed", "GPU", "optimization", "batch",
        "Kafka", "Redis", "API",
    ],
}

JD_KEYWORD_CATEGORY_WEIGHTS = {
    "ranking":    3.0,
    "embeddings": 2.5,
    "production": 2.0,
    "evaluation": 1.5,
    "llm":        1.5,
    "infra":      1.0,
}

# =============================================================================
# Experience Scoring Parameters
# Gaussian-shaped: peaks at 7 years, sigma 2.5
# =============================================================================
EXPERIENCE_PEAK_YEARS = 7.0
EXPERIENCE_SIGMA = 2.5

# =============================================================================
# Education Scoring
# =============================================================================
INSTITUTION_TIER_SCORES = {
    "tier_1":  1.00,
    "tier_2":  0.75,
    "tier_3":  0.50,
    "tier_4":  0.30,
    "unknown": 0.40,
}

# Field-of-study relevance
RELEVANT_FIELDS = {
    # High relevance
    "Computer Science":          1.00,
    "Computer Engineering":      1.00,
    "Artificial Intelligence":   1.00,
    "Machine Learning":          1.00,
    "Data Science":              1.00,
    "Information Technology":    0.90,
    "Software Engineering":      0.90,
    # Medium relevance
    "Electrical Engineering":    0.70,
    "Electronics":               0.70,
    "Mathematics":               0.70,
    "Statistics":                0.70,
    "Applied Mathematics":       0.70,
    "Physics":                   0.60,
    # Low relevance
    "Mechanical Engineering":    0.30,
    "Civil Engineering":         0.25,
    "Chemical Engineering":      0.25,
    "Commerce":                  0.20,
    "Business Administration":   0.20,
}
FIELD_DEFAULT_SCORE = 0.20  # For unrecognized fields

# Postgrad bonus
POSTGRAD_DEGREES = {"M.Tech", "M.S.", "M.Sc", "M.E.", "Ph.D.", "PhD", "MTech", "MS", "MCA"}
POSTGRAD_BONUS = 0.15

# =============================================================================
# Location Scoring
# =============================================================================
PREFERRED_CITIES = {"Noida", "Pune"}  # Score 1.0

TIER1_INDIA_CITIES = {
    "Bangalore", "Bengaluru", "Mumbai", "Hyderabad", "Chennai",
    "Delhi", "New Delhi", "Gurgaon", "Gurugram", "Kolkata",
    "Ahmedabad", "Jaipur",
}  # Score 0.85

# =============================================================================
# Behavioral Multiplier Parameters
# =============================================================================

# Recency scoring (days since last active)
RECENCY_THRESHOLDS = [
    (30,  1.00),   # Active within 30 days
    (90,  0.85),   # Active within 90 days
    (180, 0.60),   # Active within 180 days
]
RECENCY_DEFAULT = 0.35  # More than 180 days inactive

# Open to work scoring
OPEN_TO_WORK_TRUE = 1.00
OPEN_TO_WORK_FALSE_HIGH_RESPONSE = 0.75  # When response_rate > 0.5
OPEN_TO_WORK_FALSE_DEFAULT = 0.60        # Bug fix #1: was 0.25 in v1

# Recruiter response rate: linear mapping
RESPONSE_RATE_MIN_SCORE = 0.40
RESPONSE_RATE_MAX_SCORE = 1.15
RESPONSE_RATE_MAX_THRESHOLD = 0.80  # Rate at which max score is reached

# Notice period (days)
NOTICE_PERIOD_THRESHOLDS = [
    (60,  1.00),   # 0-60 days: no penalty
    (90,  0.95),   # 60-90 days: minor penalty
    (120, 0.85),   # 90-120 days: moderate penalty (Bug fix #2: was catastrophic)
    (180, 0.70),   # 120-180 days: significant but not fatal
]

# GitHub activity score
GITHUB_THRESHOLDS = [
    (50,  1.10),   # High activity
    (20,  1.05),   # Moderate activity
    (0,   1.00),   # Low activity
]
GITHUB_NO_ACCOUNT = 0.95  # score == -1

# Interview completion rate
INTERVIEW_HIGH = (0.80, 1.05)
INTERVIEW_MID = (0.50, 1.00)
INTERVIEW_LOW_SCORE = 0.90

# Verification scoring
VERIFICATION_SCORES = {
    3: 1.05,   # All 3 verified
    2: 1.00,   # 2 verified
    1: 0.95,   # 1 verified
    0: 0.85,   # None verified
}

# Behavioral multiplier clamp range
BEHAVIORAL_MIN = 0.35
BEHAVIORAL_MAX = 1.35

# =============================================================================
# Production Evidence Keywords (for career description analysis)
# =============================================================================
PRODUCTION_EVIDENCE_CATEGORIES = {
    "ir_ranking": {
        "weight": 0.35,
        "keywords": [
            "search", "ranking", "retrieval", "recommendation",
            "embeddings", "vector", "faiss", "elasticsearch",
            "ndcg", "mrr", "bm25", "semantic search", "re-ranking",
            "reranking", "hybrid search", "inverted index",
            "dense retrieval", "query", "relevance", "recall",
            "candidate generation", "learning to rank",
        ],
    },
    "deployment": {
        "weight": 0.25,
        "keywords": [
            "deployed", "production", "shipped", "served",
            "sla", "latency", "throughput", "real-time",
            "live traffic", "serving", "end-to-end",
            "microservice", "api",
        ],
    },
    "scale": {
        "weight": 0.20,
        "keywords": [
            "million", "billion", "thousands", "100k", "10k",
            "scale", "scaled", "large-scale", "high-throughput",
            "distributed", "petabyte", "terabyte",
        ],
    },
    "finetuning": {
        "weight": 0.10,
        "keywords": [
            "fine-tuned", "fine-tuning", "lora", "qlora", "peft",
            "adapter", "instruction tuning", "rlhf",
            "training loop", "custom model",
        ],
    },
    "infra": {
        "weight": 0.10,
        "keywords": [
            "kubernetes", "docker", "ci/cd", "monitoring",
            "a/b test", "experiment", "mlops", "pipeline",
            "airflow", "orchestrat",
        ],
    },
}

# =============================================================================
# Disqualifier Patterns (strong negative multipliers on career score)
# =============================================================================
DISQUALIFIER_PURE_RESEARCH_MULTIPLIER = 0.30
DISQUALIFIER_RECENT_LANGCHAIN_ONLY_MULTIPLIER = 0.40
DISQUALIFIER_NO_CODE_18MO_MULTIPLIER = 0.50
DISQUALIFIER_CV_SPEECH_ONLY_MULTIPLIER = 0.50
DISQUALIFIER_TITLE_CHASER_MULTIPLIER = 0.60
DISQUALIFIER_ALL_CONSULTING_MULTIPLIER = 0.22
DISQUALIFIER_CURRENT_CONSULTING_MULTIPLIER = 0.45

# =============================================================================
# Honeypot Detection Thresholds
# =============================================================================
HONEYPOT_SINGLE_JOB_SLACK_MONTHS = 6    # Allow this much slack over yoe * 12
HONEYPOT_TOTAL_CAREER_MULTIPLIER = 2.0  # Flag if total months > yoe * 12 * this
HONEYPOT_TOTAL_CAREER_SLACK = 24        # Plus this many months slack
HONEYPOT_EXPERT_NO_EVIDENCE_MIN = 5     # Min expert/advanced skills with 0 dur + 0 endorse
HONEYPOT_MIN_DESCRIPTION_LENGTH = 50    # Suspicious if description < this for 36+ month roles

# =============================================================================
# Submission Constants
# =============================================================================
TOP_N = 100  # Number of candidates to output
REFERENCE_DATE = "2026-06-01"  # Reference date for recency calculations
