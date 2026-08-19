# Agent and Skill Architecture Evaluation

This document evaluates the workbench's agent and skill architecture against published
AI-agent-for-science systems, and derives a staged expansion roadmap. It is a design review, not
validation evidence: nothing here establishes performance on real cohorts, assay platforms, or live
connectors.

Verification markers used below: **[V]** primary source read; **[V-abs]** abstract or landing page only;
**[S]** search snippet or secondary source, treat as unverified detail.

## 1. What this repository already is

Two asset classes, published as contracts for a host runtime (Claude Code or Codex) rather than as an
executable orchestrator:

- **Skills** — `.claude/skills/<name>/SKILL.md` and `.agents/skills/<name>/SKILL.md`, byte-identical
  pairs, each with eight required sections and a named executable implementation.
- **Agents** — `.claude/agents/<name>.md` and `.codex/agents/<name>.toml`, paired under a
  whitespace-normalized contract fingerprint, each declaring input, output, decision, and review-boundary
  clauses.

**Orchestration is entirely declarative.** There is no LLM client, agent dispatcher, or meeting loop
anywhere in `src/`. The deterministic Python is the executor; the host does the routing.

What is machine-enforced today (`scripts/evaluate_skills.py`, `scripts/evaluate_scientific_readiness.py`):
paired byte parity, required sections, scientific-guardrail phrase gates, declared-implementation
existence, canonical-name inventory, one-hop alias resolution with expiry, and nine behavioral risk gates
whose release gate fails on any failure, error, **or skip**.

The strongest existing guarantee is the `DomainReviewPacket` layer: four advisory reviewer roles emit a
typed, schema-validated record where `decision_authority` has exactly one legal value (`advisory_only`),
`human_adjudication_status` exactly one (`required`), `executable_actions` must be empty, and
`review/validation.py` rejects any field or prose pattern that smuggles in an acceptance, confidence
value, pooling permission, risk-of-bias score, or meta-analytic result. That is the repository's central
architectural idea: **an untrusted producer emits a typed record; deterministic Python enforces the safety
boundary at ingest.**

## 2. The comparison

| System | Orchestration | Grounding discipline | Transferable to us |
|---|---|---|---|
| **Virtual Lab** — Swanson, Wu, Bulaong, … Zou, *Nature* (2025), [doi:10.1038/s41586-025-09442-9](https://doi.org/10.1038/s41586-025-09442-9), [repo](https://github.com/zou-group/virtual-lab) **[V repo / V-abs paper]** | PI + domain scientists + mandatory Scientific Critic in structured "meetings"; N parallel high-temperature runs → one provenance-annotated merge; phase DAG passing only merged summaries | One optional PubMed tool; all evidence flows as fenced prose (`[begin paper N]`) | Meeting contract as a skill; critic as a structurally mandatory non-writing seat; parallel-runs-then-merge; dual JSON+Markdown transcripts |
| **Paperclip** — James Zou + Christine Lemke, Generative Expert Labs, [paperclip.gxl.ai](https://paperclip.gxl.ai/), [CLI](https://github.com/GXL-ai/paperclip) **[V]** | Corpus as agent-native virtual filesystem; Unix verbs (`search`, `grep`, read-only `sql`, `map`/`reduce`); git-shaped "Paper Repos" with `commit`/`annotate`/`diff` | Every document is a directory; full text line-numbered `L<n>:` so a citation is a verifiable `file:line-range` | The evidence-store *shape*; `map`→`reduce` over individually inspectable per-document intermediates; versioned evidence sets with human reasoning per commit |
| **Paper2Agent** — Miao, Davis, Zhang, Pritchard, Zou, [arXiv:2509.06917](https://arxiv.org/abs/2509.06917), [repo](https://github.com/jmiao24/Paper2Agent) **[V]** | 11-step driver delegating to markdown subagent manifests (scanner, executor, tool extractor, test-verifier, benchmark quartet) | "No Mock", "never add parameters not in tutorial", test-or-drop after six attempts | Its anti-fabrication clause set, and `Core Principles (Non-Negotiable)` / `Forbidden Practices` as required manifest headings |
| **Biomni** — [snap-stanford/Biomni](https://github.com/snap-stanford/Biomni), [bioRxiv 2025.05.30.656746](https://www.biorxiv.org/content/10.1101/2025.05.30.656746v1) **[V repo]** | LangGraph plan/execute loop with a visible mutating checklist; LLM-as-selector retrieval over tools × data lake × libraries × know-how | Tool *declaration* separated from implementation, schema-validated at registration | The declaration/implementation split for a source registry; markdown know-how docs with per-document license and commercial-use gating |
| **Google AI co-scientist** — [arXiv:2502.18864](https://arxiv.org/abs/2502.18864) **[V]**; *Nature* (2026) [s41586-026-10644-y](https://www.nature.com/articles/s41586-026-10644-y) **[S]** | Supervisor + Generation, Reflection, Ranking (Elo tournament), Evolution, Proximity, Meta-review | Four review modes, incl. **deep verification** — decompose a hypothesis into assumptions, decontextualize each, test independently | Assumption-decomposition verification; proximity/dedup clustering; meta-review as a summarizer for humans |
| **FutureHouse PaperQA2 / Kosmos / BixBench** — [arXiv:2409.13740](https://arxiv.org/abs/2409.13740) **[V-abs]**, [arXiv:2511.02824](https://arxiv.org/abs/2511.02824) **[V-abs]**, [arXiv:2503.00096](https://arxiv.org/abs/2503.00096) **[V]** | Single-agent tool loop over shared state; Kosmos runs parallel literature + analysis agents against a shared structured world model | **Opaque citation keys that must resolve to a retrieved chunk**; Kosmos's rule that every statement cites code *or* primary literature | Citation-key grounding as a parse-time property; expert-authored, second-expert-approved fixtures; abstention scored as a distinct outcome |
| **ChemCrow** — [arXiv:2304.05376](https://arxiv.org/abs/2304.05376), *Nat Mach Intell* 6, 525–535 (2024) **[V]** | ReAct loop over 13–18 expert-designed tools declared as prose contracts | Exact lookups against real databases | The tool-registry-as-prose-contract pattern, and its central failure lesson (below) |
| **Coscientist** — Boiko et al., *Nature* (2023) [s41586-023-06792-0](https://www.nature.com/articles/s41586-023-06792-0) **[S architecture]** | Planner restricted to four typed commands (`GOOGLE`, `PYTHON`, `DOCUMENTATION`, `EXPERIMENT`) | Retrieves actual instrument API docs before generating hardware code | A deliberately tiny, auditable action space |
| **Sakana AI Scientist** — [repo](https://github.com/SakanaAI/AI-Scientist), v2 [arXiv:2504.08066](https://arxiv.org/abs/2504.08066); critique [arXiv:2502.14297](https://arxiv.org/abs/2502.14297) **[V-abs]** | Idea → tree-search experiments → manuscript → automated reviewer | Weakest surveyed: manuscript prose is not constrained by executed artifacts | Anti-pattern (below) |
| **MetaBench** — [arXiv:2510.14944](https://arxiv.org/html/2510.14944v1) **[V]** | Metabolomics-specific LLM evaluation across five capability levels | — | The single most important empirical result for this repository (below) |
| **Pan-ReDU** — *Nat Commun* (2025) [s41467-025-60067-y](https://www.nature.com/articles/s41467-025-60067-y) **[V]** | Deliberately **non-LLM** cross-repository metabolomics metadata harmonization | Hand-built translation sheets; ambiguous file associations **discarded rather than estimated** | Direct precedent for our conservatism; ~12% of GNPS/MassIVE raw data had compatible metadata |
| **Harmonia** — [arXiv:2502.07132](https://arxiv.org/html/2502.07132) **[V]** | LLM agent + UI over composable harmonization primitives; explicitly rejects full autonomy | Emits declarative JSON mapping specs reproducible **without re-running the LLM** | The right output shape for `harmonization-plan`: the model proposes, the artifact is a deterministic spec |
| **L-PRISMA** / multi-agent SLR — [arXiv:2603.19236](https://arxiv.org/html/2603.19236v1) **[V]**, [arXiv:2509.17240](https://arxiv.org/html/2509.17240v1) **[V]** | Tri-band screening with per-band authority; 27 agents in six PRISMA societies | Mandatory disclosure of model version, exact prompts, per-band counts, threshold rationale | Disclosure requirements; and the finding that forced narrow manifests |

Attribution corrections worth recording, since all three are commonly misattributed: **Paperclip** is a
Generative Expert Labs (company) product, not a `zou-group` repository. **Paper2Agent** lives on a personal
account with Zou as co-author. **Biomni** is a `snap-stanford` (Leskovec group) project; we could not verify
Zou authorship and it should not be described as Zou-group work.

## 3. What the literature says we already get right

Four empirical results independently justify guardrails this repository already enforces. They belong in
any design discussion of loosening those guardrails.

1. **Identifier mapping cannot be a model output.** MetaBench measured the best tool-free LLM at **0.87%**
   exact-match on metabolite identifier translation, rising to only **~41%** with web-search tools; asked
   for the KEGG ID of HMDB0004148, eleven different models all answered wrong. The authors attribute this
   to sparse training signal and subword tokenization fragmenting identifiers — **not** to scale. **[V]**
   This is the empirical basis for `metabolite-identity-resolution` refusing name-only merges and for
   requiring deterministic lookup against a versioned reference.
2. **Citation completeness is not correctness.** Kosmos cites every statement to code or primary
   literature, and independent scientists still judged only **79.4%** of statements accurate. **[V-abs]**
   Roughly one statement in five in a fully-cited report is wrong, which is why grounding cannot replace
   the human gate.
3. **LLM verifiers of mappings are unreliable.** Harmonia reports LLMs "occasionally failed" to flag
   incorrect mappings *under identical prompts* **[V]**; ChemCrow reports GPT-4 as evaluator "cannot
   distinguish between clearly wrong GPT-4 completions and ChemCrow's performance" **[V]**. Together:
   never accept LLM-only verification of a crosswalk, and never use an LLM judge on a task class where the
   judge's own unaided accuracy is unmeasured.
4. **Unconstrained generative pipelines fabricate.** An independent critique of Sakana's AI Scientist
   found **42% of experiments failed on coding errors**, manuscripts containing hallucinated numerical
   results, re-invented ideas labelled novel, and a reviewer agent with unmeasured positivity bias.
   **[V-abs]** The structural cause is a writeup stage not constrained by the artifacts of the execution
   stage — exactly what template-generated reports plus provenance validation prevent.

A fifth, structural, lesson: ChemCrow's incorrect price comparison was caused purely by a **missing**
stoichiometry tool. **A registry gap is a fabrication vector** — if no tool covers a request, the model
improvises. This motivated the `source-registry-librarian` role added in this change.

And from the 27-agent PRISMA system: they adopted strict one-agent-per-checklist-item because multi-item
agents became "overloaded, degraded, unpredictable." **[V]** That is a direct argument for keeping agent
manifests narrow rather than merging roles.

## 4. Role-archetype gap analysis

Across the surveyed systems, roughly 23 distinct archetypes appear. Tiered against this repository's
constraints — never fabricate, missing metadata is scientific risk, uncertainty escalates, no ETL from
unapproved mappings:

**Safe and additive** (pure verification or packaging; no new generative authority): assumption-decomposition
verifier; citation/provenance-grounding verifier; cross-field consistency arbitrator; cross-source
contradiction detector; deduplication/proximity clustering; tri-band screener with audit trail;
one-item-per-agent checklist grader; **tool/source-registry librarian**; deterministic replay checker;
precedent/novelty checker (reporting only "no precedent found by this search", never "novel"); benchmark
harness with scored abstention; entity-resolution uncertainty quantifier.

**Safe only with a hard structural boundary**: adversarial reviewer (may block or annotate, never approve,
and its human agreement must be measured before it gates anything); literature evidence extraction (must
emit `extracted` / `inferred` / `absent` as three non-collapsible states, and `absent` must survive as
risk); ranking/tournament judge (acceptable for ordering a reviewer's queue, never as a decision
mechanism — an Elo score has no provenance); meta-reviewer (take the synthesis for humans, refuse the
original's loop where it reprograms the other agents); clarifying-question agent (an unanswered question
must block the artifact, not default); shared world model (append-only with per-entry provenance, or it
becomes a laundering channel where one agent's inference is read by another as fact).

**Withheld — requires generative authority we deliberately do not grant**: hypothesis generator;
hypothesis mutation/evolution; protocol and experiment designer; autonomous manuscript author;
self-improving orchestrator that spawns roles or reallocates grading authority.

Coverage assessment: this repository is **critic-heavy by design** — before this change, 11 of 20
addressable roles were adversarial, scoring, or gate roles. The genuine gaps were structural rather than
conceptual: the four advisory reviewers had no skill-level playbook, several load-bearing modules were
governed by no contract, and three generative roles had no same-domain critic.

## 5. What this change delivered

Contract-only, no new scientific code:

- **Five new skill playbooks** — `study-design-population-context-reviewer`,
  `exercise-phenotype-harmonization-reviewer`, `biospecimen-preanalytics-reviewer`,
  `statistical-estimand-and-synthesis-skeptic` (all declaring `review/validation.py` +
  `review/models.py`), and `harmonization-skeptic` (declaring `harmonization/skeptic.py`). The four
  reviewer playbooks are generated from `ROLE_REVIEW_DIMENSIONS` and `EvidenceState`, so their required
  dimensions cannot drift from the model.
- **Three new agents** — `source-registry-librarian` (registry gaps as blocking escalations),
  `cross-field-consistency-arbitrator` (coherence checking held separate from extraction and
  normalization, per MetaMuse's Curator/Arbitrator/Normalizer split), `metadata-extraction-critic`
  (closing the gap where `metadata-extractor` had no critic).
- **`Core Principles (Non-Negotiable)` and `Forbidden Practices`** sections adopted from Paper2Agent in
  the new assets. Repo-wide adoption is deferred because it requires a simultaneous byte-identical edit
  across all existing skill pairs.
- **The network non-negotiable made true and enforced.** `CLAUDE.md` previously claimed a single networked
  entry point; four modules actually reach the network. The rule now names the real allowlist and
  `tests/test_network_boundary.py` enforces it by AST scan, additionally asserting that offline pilot
  modules stay offline and that the documented allowlist matches the enforced one.

## 6. Roadmap

**Phase 2 — deliberation layer.** A deterministic `deliberation/` package: typed charter, transcript, and
objection ledger, validated but never LLM-calling, keeping the untrusted-producer posture. Key adaptations
away from Virtual Lab: no generic Scientific Critic (the critic seat resolves from decision class to an
existing specialist agent); **closed `decision_options`**, which makes "merge the best components"
impossible by construction — for factual curation there is no best blend of two incompatible metabolite
mappings; objection-ledger fixpoint termination rather than fixed rounds; an unresolved critic objection
escalates to a human instead of being overridden by a lead agent; and disagreement across N independent
runs treated as the uncertainty signal rather than something to merge away. Also adds
`orchestration-handoff-critic` and `benchmark-integrity-critic`.

**Phase 3 — literature evidence lane.** Paperclip host-side only, never called from repository Python and
never on the network allowlist; its skill installs at user scope because a vendor `SKILL.md` inside
`.claude/skills/` would break the inventory and parity gates. Results enter through an offline importer
into a line-addressable store so a citation is a verifiable `file:line-range`, with opaque-but-recomputable
citation keys making a forged key a parse-time failure, and license gating that stores full text only for
a redistributable allowlist and records everything else as an availability gap.

**Phase 4 — repo-wide adoption** of the required-principles headings, and a calibration harness that
measures any critic's agreement with human reviewers before its verdict is allowed to gate anything.

## 7. Interpretation limits

- A passing contract audit measures structure and linkage, not scientific validity.
- The comparison above is a design review of published descriptions; we did not run any of these systems.
- Several primary sources were paywalled or blocked (Nature full texts for Virtual Lab, co-scientist,
  Robin, and Coscientist; bioRxiv for MetaMuse and related metadata-curation systems). Claims drawn from
  them are marked **[S]** and should be re-verified before being cited as method.
- Paperclip's MCP tool names were not publicly enumerated; its CLI verbs were verified, the MCP mapping is
  inference.
