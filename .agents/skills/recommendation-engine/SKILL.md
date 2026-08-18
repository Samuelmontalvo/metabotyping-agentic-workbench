---
name: recommendation-engine
description: Use when converting discovery, metadata, mirage, and quality evidence into prioritized dataset recommendations.
---

# Purpose
Prioritize direct matches, complementary studies, enrichment candidates, mirages, and exclusions for scientific review.

# Inputs
- Recommendations
- Metadata cards
- Quality scores
- MoTrPAC alignment scores

# Steps
1. Keep excluded and mirage records visible.
2. Rank direct matches by modality and repository usability.
3. Promote enrichment candidates when genetics, body composition, or diet metadata is strong.
4. Attach rationale and missing metadata.

# Outputs
- Ranked recommendation tables in Markdown and JSON

# Validation Checks
- Recommendation class matches the evidence.
- Mirage flags are not hidden by high modality overlap.

# Failure Modes
- Ranking overweights a modality and ignores repository usability.
- Complementary datasets are treated as direct matches.

# Human-Review Triggers
- A top-ranked dataset has access restrictions.
- User wants grant-specific prioritization.

# Evaluation Gates
- FAIR: recommendations must expose repository access, metadata/codebook evidence, modality coverage, and provenance.
- Reproducibility: priority ordering must be regenerated from declared recommendation scores and review rules.
- Critical evidence: distinguish direct matches from enrichment candidates; do not let high scores suppress mirage warnings.
- Skill quality rubric: pass only if each recommendation includes class, score, rationale, missing evidence, and review triggers.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/discovery/recommender.py`.
