---
name: literature-retrieval
description: Screens publication-like records for human metabolomics and relevant phenotypes, and reports which literature indexes were actually reachable.
---

Input contract: receive structured publication records or a retrieved bibliographic record set with its per-source retrieval provenance, plus explicit inclusion criteria.

Output contract: report required-term eligibility, observed exercise, actigraphy, genetics, CPET, body-composition, diet, and accession evidence, and the retrieval status of every queried index including reported hit count, retrieved count, and pagination completeness.

Decision rules: use structured fields before title inference, do not include animal-only or no-metabolomics records when those are exclusions, and never record an unreachable index as zero matching publications.

Review boundary: route conflicting species, modality, or repository evidence to human review, label inference explicitly, and escalate any record that cannot be screened from the retrieved text instead of excluding it.
