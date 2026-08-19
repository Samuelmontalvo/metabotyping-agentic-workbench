---
name: biospecimen-preanalytics-reviewer
description: Use when assembling specimen, collection-timing, processing, and storage evidence into an advisory review packet.
---

# Purpose
Inventory what a study reports about specimen handling and timing, without inferring metabolite stability or cross-study comparability.

# Inputs
- Schema-valid dataset cards and assay records with resolvable provenance locators.
- Provenance-linked evidence for every required dimension: `specimen_derivative`, `collection_timing_relative_to_exercise`, `food_context`, `circadian_context`, `posture`, `tube_or_additive`, `processing_delay`, `processing_temperature`, `centrifugation`, `aliquoting`, `storage`, `freeze_thaw`, `shipping`, `sop`, `deviations`.
- `schemas/domain_review_packet.schema.json` for the packet contract.

# Steps
1. Collect the source evidence for each required dimension and keep its source locator, record key, and field name.
2. Assign exactly one evidence state per required dimension from `reported`, `documented_absent`, `not_reported`, `not_available`, `conflicting`, `unresolved`, `not_applicable`.
3. Record a `reported`, `documented_absent`, or `conflicting` state only with a linked provenance record; distinguish documented absence from an unreported field.
4. Link each gap or conflict to a limitation or blocker, and write a concrete adjudication question for it.
5. Set `decision_authority` to `advisory_only` and `human_adjudication_status` to `required`, leave `executable_actions` empty, and compute the deterministic `packet_digest`.
6. Run the deterministic validator and resolve every reported error before the packet reaches a reviewer.

# Outputs
- An advisory `DomainReviewPacket` covering biospecimen collection and handling evidence, with linked limitations, blockers, adjudication questions, and a deterministic digest.

# Validation Checks
- `validate_domain_review_packet()` returns no errors.
- Every required dimension appears exactly once with an explicit evidence state.
- Every evidence item requiring provenance carries a resolvable locator and a lowercase SHA-256 source digest.
- Every limitation, blocker, and question identifier referenced by an evidence item resolves inside the packet.
- `packet_digest` recomputes to the stored value.

# Failure Modes
- A dimension is omitted, or silence is recorded as absence rather than as an unreported field.
- The packet smuggles an acceptance, rejection, confidence value, or pooling permission into prose.
- Evidence is summarized without a source locator, so a reviewer cannot check it.
- A shared label such as plasma is not evidence of equivalent preanalytics; unknown handling remains unknown.

# Human-Review Triggers
- Always triggered for this skill: the packet is advisory evidence and a human reviewer makes every decision.
- Any dimension in a `not_reported`, `not_available`, `conflicting`, or `unresolved` state.
- Any conflict between sources for the same dimension.

# Evaluation Gates
- FAIR: every evidence item must preserve source metadata, provenance, and the access status of its source record.
- Reproducibility: the packet digest must be regenerated deterministically from packet content, with no timestamps or absolute paths.
- Critical evidence: never infer stability, prescribe correction or imputation, or decide combinability; do not record an inferred value and do not infer an evidence state from silence.
- Human review: unresolved, conflicting, or missing dimensions must trigger an explicit adjudication question.
- Skill quality rubric: pass only if every required dimension carries an explicit evidence state, every provenance-requiring state carries a resolvable locator, and the deterministic validator reports no errors.

# Core Principles (Non-Negotiable)
1. No fabricated evidence. Never invent a record, locator, identifier, or value.
2. Conservative classification. When uncertain, record the uncertainty and escalate; do not choose a state to make the packet look complete.
3. Read each source record end-to-end before assigning a state.
4. Advisory only. This role narrows confidence and raises questions; it never decides.

# Forbidden Practices
- Do not issue an acceptance, rejection, eligibility verdict, or risk-of-bias score.
- Do not assign a confidence value, authorize a transform or pooling, or return a meta-analytic result.
- Do not emit an executable action, or reuse a readiness heuristic as a validated assessment.

# Implementation
- Deterministic validator: `src/metabotyping_agentic/review/validation.py`.
- Typed packet contract: `src/metabotyping_agentic/review/models.py`.
