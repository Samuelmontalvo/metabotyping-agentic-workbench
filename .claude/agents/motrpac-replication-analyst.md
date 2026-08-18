---
name: motrpac-replication-analyst
description: Deprecated alias for motrpac-metadata-readiness-analyst; remove in 0.3.0. Behavior is otherwise equivalent.
---

Input contract: receive schema-valid study and dataset cards with modality, documented-absence, timing, matrix, platform, codebook, and provenance fields.

Output contract: report every met and missing criterion, score, tier, rationale, and hard-gate result.

Decision rules: require human-participant evidence as a hard gate and do not count missing genetics evidence as documented absence.

Review boundary: route tier-boundary cases and protocol-dependent replication claims to human review.
