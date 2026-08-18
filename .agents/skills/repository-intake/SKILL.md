---
name: repository-intake
description: Use when converting repository records into structured dataset cards with provenance and mirage checks.
---

# Purpose
Normalize repository metadata from public, restricted, or local CSV sources into reviewable dataset cards.

# Inputs
- Repository CSV records
- Optional publication records for study context

# Steps
1. Parse accessions, public status, metadata/codebook/data flags, platforms, matrices, timing, sample size, and modalities.
2. Attach provenance to each dataset card.
3. Flag missing or restricted repository assets.
4. Write per-study and combined card JSON.

# Outputs
- `data/extracted/metadata_cards/dataset_*.json`
- `data/extracted/dataset_cards.json`

# Validation Checks
- Each card has accession, availability, modality list, and provenance.
- Unknown values are explicit, not blank.

# Failure Modes
- Repository rows lack stable study identifiers.
- Modalities are ambiguous or unsupported.

# Human-Review Triggers
- Restricted data may still be usable with metadata-only analyses.
- Repository metadata conflicts with publication metadata.

# Evaluation Gates
- FAIR: dataset cards must assess findability, accessibility, interoperability, reusability, metadata richness, and source provenance.
- Reproducibility: cards must be regenerated from declared repository rows with explicit unknown values.
- Critical evidence: distinguish unavailable data from restricted metadata-only access; do not infer data files from accessions alone.
- Skill quality rubric: pass only if accession, access status, codebook, data files, platform, timing, and sample size checks are complete.

# Implementation
- Deterministic implementation: `src/metabotyping_agentic/discovery/repositories.py`.
