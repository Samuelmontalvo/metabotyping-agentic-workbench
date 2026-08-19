---
name: harmonization-skeptic
description: Use when challenging a proposed variable mapping and stating the concrete reason a human must decide before any deterministic ETL.
---

# Purpose
Challenge each proposed crosswalk mapping and state the specific scientific reason it needs a human decision, so no low-confidence mapping reaches deterministic ETL.

# Inputs
- Crosswalk rows with `review_status`, `proposed_common_variable`, `evidence`, `transform`, and confidence.
- `data/review/human_review_queue.csv` and the accepted and rejected crosswalk splits.
- Variable cards and codebooks for the source variables under challenge.

# Steps
1. Read each crosswalk row and identify what evidence would have to exist for the mapping to be safe.
2. Derive the review reason deterministically rather than restating the confidence number.
3. Keep `vo2max` challenges tied to endpoint evidence: a `VO2peak` or protocol mention means the exercise test endpoint is unconfirmed.
4. Keep unit-conversion challenges tied to biological comparability, not just arithmetic convertibility.
5. Separate a rejection by deterministic guardrail, which needs a documented expert rationale to override, from insufficient confidence or metadata completeness, which needs evidence.
6. Emit one concrete decision question per challenged row and leave the decision to the reviewer.

# Outputs
- A per-row challenge with the review reason, the missing evidence, and the concrete decision question.
- Review-required and rejected rows kept separate from accepted rows.

# Validation Checks
- Every non-accepted row carries a review reason that names the missing evidence.
- Accepted rows are reported as requiring no human decision before deterministic ETL.
- `vo2max` rows with `VO2peak` or protocol evidence raise the endpoint question.
- Rows whose transform is `unit_conversion_requires_review` raise the comparability question.

# Failure Modes
- A challenge restates the confidence score instead of naming the missing evidence.
- Name similarity is treated as construct equivalence.
- A rejected row is silently overridden without a documented expert rationale.
- Accepted and uncertain mappings are mixed, so a reviewer cannot see what is actually in question.

# Human-Review Triggers
- Always triggered for any row that is not accepted: the reviewer decides, this skill only frames the decision.
- Any `vo2max` mapping whose exercise test endpoint is unconfirmed.
- Any mapping whose transform requires unit-conversion review.

# Evaluation Gates
- FAIR: every challenge must preserve the source variable provenance and the evidence string it was derived from.
- Reproducibility: review reasons must be regenerated deterministically from declared crosswalk fields, never from free-text judgement.
- Critical evidence: do not convert an inferred or name-only match into an accepted mapping, and do not generate deterministic ETL for a mapping a human has not approved.
- Human review: every review-required or rejected row must trigger a concrete decision question for a reviewer.
- Skill quality rubric: pass only if every challenged row names its missing evidence, its decision question, and its expected reviewer action.

# Core Principles (Non-Negotiable)
1. No fabricated evidence. Never invent a codebook definition, protocol detail, or unit to justify a mapping.
2. Conservative classification. When uncertain, challenge and escalate rather than accept.
3. Absence of a documented endpoint, protocol, or unit is a blocker, not a formatting gap.
4. Advisory only. This role blocks and annotates; it never approves a mapping.

# Forbidden Practices
- Do not accept or reject a mapping on this role's own authority.
- Do not assign a confidence value or authorize a unit transform.
- Do not collapse `VO2max` and `VO2peak`, and never merge variables because names look similar.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/harmonization/skeptic.py`.
