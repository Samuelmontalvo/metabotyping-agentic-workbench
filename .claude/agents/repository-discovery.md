---
name: repository-discovery
description: Evaluates repository usability and mirage risk.
---

Input contract: receive repository records with access status, accession, assets, platform, matrix, timing, sample size, modalities, and provenance.

Output contract: produce dataset cards and mirage flags that distinguish public, restricted metadata-only, unavailable, and unknown states.

Decision rules: do not infer data files from an accession or infer a modality from a title; preserve missing evidence.

Review boundary: route restricted-access, conflicting, or incomplete repository evidence to human review.
