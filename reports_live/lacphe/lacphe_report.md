# Lac-Phe (N-lactoyl phenylalanine): study discovery, exercise effect, and MoTrPAC rat alignment

Live-mode report. Every row below comes from a public released record fetched through the declared
network boundary; no synthetic stand-ins are used, and unavailable data is reported as a coverage gap.

## Headline

- **Human exercise effect is present and large.** In MW `ST003662` (healthy male and female athletes,
  whole blood, post- vs pre-exercise), Lac-Phe rises **log2FC +1.16** (95% CI +0.91 to +1.41; ~2.2-fold), paired t p=2.73e-15, BH FDR=2.50e-14, n=116 pairs.
- **Rat MoTrPAC alignment is blocked by feature coverage, not by effect size.** Lac-Phe does not appear
  anywhere in pass1b-06 metabolomics: 0 matches across 2459 unique features, 99,236 timewise rows, 19 tissues, 4 training-week groups.
- **No N-lactoyl amino-acid conjugate of any kind is in the rat feature space**, so this is a panel-coverage
  gap for the whole conjugate class rather than a missing single annotation.
- Alignment therefore stops at **precursor-level** evidence (lactic acid, phenylalanine) plus a documented
  availability gap. It is not a cross-species replication and must not be reported as one.

## Chemical identity of the query

| field | value |
| --- | --- |
| query as typed | Lac-Phe |
| resolved RefMet name | N-Lactoyl phenylalanine |
| RefMet ID | RM0131640 |
| formula / exact mass | C12H15NO4 / 237.100109 |
| InChIKey | IIRJJZHHNGABMQ-WPRPVWTQSA-N |
| PubChem CID | 11075454 |
| RefMet class path | Organic acids > Amino acids and peptides > Amino acids |
| resolution source | `https://www.metabolomicsworkbench.org/rest/refmet/name/N-Lactoyl%20phenylalanine/all` |

Identity is resolved at the **RefMet-name and structure-annotation level**. It is not MSI level-1
confirmation in any of the assays below; every effect row stays `requires_human_review` for assay identity.

## Aim 1 — Study discovery

Metabolomics Workbench `metstat` was queried for the resolved RefMet name across all species, sources and
platforms. **57 studies / 60 analyses** report Lac-Phe.

| species | analyses |
| --- | --- |
| Human | 24 |
| Mouse | 20 |
| Cow | 2 |
| Rat | 2 |
| not_reported | 1 |
| Akkermansia muciniphila | 1 |
| Escherichia coli | 1 |
| Gardenerella vaginalis | 1 |
| Gemella morbillorum | 1 |
| Horse; Yak; Donkey; Camel | 1 |
| Lacticaseibacillus rhamnosus | 1 |
| Macaque monkey | 1 |
| Pig | 1 |
| Sheep | 1 |
| Staphylococcus aureus | 1 |
| Wheat | 1 |

- Human blood analyses: **11** across 9 studies.
- Of those, exactly **one** is an exercise-physiology design: `ST003662`. The rest are disease or
  case-control cohorts (cancer, ALS, MS, ARDS, pancreatitis). They report Lac-Phe but carry no exercise
  exposure, so they cannot answer an exercise question.
- Rat MW analyses exist (2) but are oxycodone-exposure plasma and
  post-colectomy feces designs — neither is an exercise design.
- **Discovery verdict:** the exercise-relevant human Lac-Phe evidence base in MW is a single study.
  Treat every conclusion below as single-study evidence pending independent replication.

Full table: `data/live/metabolite_search_lacphe/metstat_metabolite_study_hits.csv`

## Aim 2 — Human exercise effect (MW ST003662)

- Study: [Metabolome trajectory of exercise physiology- a comprehensive study of healthy male and female athletes](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003662)
- Species: Homo sapiens; license CC BY 4.0
- Matrix: whole blood, μmol/L (analyses AN006015 HILIC + AN006016 reversed phase)
- Contrast: post-exercise vs pre-exercise (Collectionpoint After vs Before); orientation: positive log2fc = higher post-exercise
- Statistic: paired t-test on log2 abundance, BH-adjusted within stratum
- Features with usable paired data: 178

| stratum | log2FC | 95% CI | fold-change | p | BH FDR | pairs | mean pre | mean post |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| All athletes | +1.16 | +0.91 to +1.41 | 2.23x | 2.73e-15 | 2.50e-14 | 116 | 0.539 | 0.755 |
| Male | +1.37 | +1.01 to +1.73 | 2.59x | 2.49e-10 | 2.41e-09 | 63 | 0.562 | 0.764 |
| Female | +0.91 | +0.57 to +1.25 | 1.87x | 2.07e-06 | 1.53e-05 | 53 | 0.512 | 0.744 |

Reading: Lac-Phe is one of the strongest post-exercise increases in this blood metabolome, and it is
significant in both sexes. The male point estimate is larger than the female one, but the sex strata are
nested inside the all-athlete stratum, share the platform and batch, and their CIs overlap — this is
**not** evidence of a sex-by-exercise interaction. A formal interaction test on the sample-level matrix
is required before any sex-difference claim.

- Figure: `figures/human_ST003662_lacphe_volcano.png`
- Figure: `figures/human_ST003662_lacphe_effect_by_sex.png`
- Table: `data/live/metabolite_scan/n_lactoyl_phenylalanine/mw_queried_metabolite_effects.csv`

## Aim 3 — MoTrPAC rat alignment

### What was searched

- Endpoint: `https://search.motrpac-data.org/api/search_public`, query `{"study": "pass1b06", "omics": "metabolomics", "size": 200000}`
- Block: `metabolomics_timewise` (trained vs sedentary control, timewise differential rows)
- Rows returned: 99,236; unique features: 2459
- Tissues: adrenal, brown adipose, colon, cortex, gastrocnemius, heart, hippocampus, hypothalamus, kidney, liver, lung, ovaries, plasma, small intestine, spleen, testes, vastus lateralis, vena cava, white adipose
- Training-week groups: 1w, 2w, 4w, 8w
- Name columns scanned: refmet_name, metabolite, feature_id

### Result: coverage gap

**0 rows matched Lac-Phe.** Name matching was normalization-insensitive
(punctuation and spacing stripped, so `N-Lactoyl phenylalanine`, `N-lactoylphenylalanine` and
`lactoylphenylalanine` all collapse to one key). A direct substring sweep of all three name columns
(`refmet_name` 2459 unique, `metabolite` 2651 unique, `feature_id` 2739 unique) returns **zero rows
containing `lactoyl`** — no N-lactoyl-phenylalanine, -leucine, -valine, or any other conjugate.

This is an **availability gap in the rat metabolomics panel**, and it is the correct scientific finding to
report. It is emphatically *not*: (a) evidence that Lac-Phe is unchanged by training in rats, (b) grounds
for substituting a synthetic or imputed rat Lac-Phe row, or (c) a reason to swap in a nearby analyte and
call it Lac-Phe.

### Closest available rat evidence — precursors only

The two substrates of the Lac-Phe conjugation reaction *are* measured in rat:

| metabolite | tissues in focus set | timewise rows | rows adj_p<0.05 | rows nominal p<0.05 |
| --- | --- | --- | --- | --- |
| lactic acid | gastrocnemius, heart, liver, plasma | 32 | 0 | 9 |
| phenylalanine | gastrocnemius, heart, liver, plasma, vastus lateralis | 40 | 0 | 3 |


No precursor cell in the focus tissues reaches adj_p<0.05 (every reported adj_p is 1.0); only nominal
p<0.05 rows exist. So the rat side offers neither the conjugate nor an FDR-significant precursor signal.

- Figure: `figures/rat_pass1b06_lacphe_precursors.png`
- Precursor abundance changes constrain **substrate availability**, not conjugate formation. CNDP2-mediated
  Lac-Phe synthesis is a separate step, and neither substrate is a validated proxy for the conjugate.

### Barriers to alignment

| barrier | human ST003662 | rat pass1b-06 | consequence |
| --- | --- | --- | --- |
| feature coverage | Lac-Phe measured | Lac-Phe absent | no shared analyte: crosswalk impossible |
| estimand | acute post- vs pre-bout, paired within participant | chronic 1-8w training vs sedentary, between-group | different biological question even if the analyte existed |
| matrix | whole blood, μmol/L | plasma and 18 solid tissues, platform-scaled | units and matrix not exchangeable |
| statistic | paired t on log2 μmol/L, computed here | consortium timewise model logFC | effect scales not directly comparable |

Even a future rat panel that adds Lac-Phe would still face the estimand and matrix barriers. Alignment
would then require an effect-level synthesis with study-specific effects, not a pooled analysis.

- Figure: `figures/lacphe_cross_species_alignment.png`

## Human MoTrPAC arm

The human MoTrPAC arm was **not** fetched for this report. The DataHub human arm is access-controlled, and
this workbench does not fabricate records for embargoed data. Whether MoTrPAC's human plasma targeted and
untargeted panels carry Lac-Phe is an open availability question and is recorded as a mirage risk, not as
a negative result. The public human-precovid-sed-adu acute plasma DA tables already cached under
`data/live/volcano_motrpac_human_plasma_endur_post.csv` also contain no lactoyl-conjugate feature.

## Human-review escalations

| # | item | why a human must decide |
| --- | --- | --- |
| 1 | Assay identity of `Lactoyl Phenylalanine` in ST003662 | RefMet name match only. Level-1 confirmation (RT + MS/MS against an authentic standard) is not documented in the public record. The reported μmol/L values imply calibration that must be verified before quantitative claims. |
| 2 | Sex-difference claim | Male vs female point estimates differ but strata are nested with overlapping CIs; needs an interaction model on sample-level data. |
| 3 | Exercise protocol | ST003662 `Collectionpoint:Before/After` does not encode modality, intensity, duration, or post-exercise sampling delay. Lac-Phe kinetics are minute-scale, so the effect size is not interpretable without the timing. |
| 4 | Rat panel gap | Confirm against MoTrPAC panel documentation whether Lac-Phe was targeted and lost at QC, or never targeted. The two have different implications for a future request. |
| 5 | Any pooling or meta-analysis | Blocked. No shared analyte, different estimands, different matrices. |
| 6 | Whole blood vs plasma | ST003662 is whole blood; MoTrPAC is plasma. Lac-Phe partitioning between erythrocytes and plasma is not established here. |

## Missing evidence

- Exercise modality, intensity, duration, and post-exercise sampling delay for ST003662.
- MS/MS-level identity confirmation and calibration provenance for the ST003662 Lac-Phe feature.
- Whether rat pass1b-06 panels ever targeted N-lactoyl conjugates.
- Lac-Phe availability in the access-controlled human MoTrPAC arm.
- Independent human exercise studies measuring Lac-Phe in MW (none found).

## Reproduction

```bash
PYTHONPATH=src python3 -m metabotyping_agentic.cli live-search-metabolite-studies \
  --query "N-Lactoyl phenylalanine" \
  --name-variants "Lac-Phe;N-lactoylphenylalanine" \
  --out data/live/metabolite_search_lacphe

PYTHONPATH=src python3 scripts/volcano_compare.py --metabolite-scan "N-Lactoyl phenylalanine" \
  --name-variants "Lac-Phe;N-lactoylphenylalanine;lactoylphenylalanine" \
  --mw-studies ST003662

python3 scripts/render_lacphe_report.py
```

Live fetch provenance: `data/live/metabolite_scan/n_lactoyl_phenylalanine/provenance.json`, `data/live/metabolite_search_lacphe/metstat_metabolite_study_provenance.json`

| gate | status |
| --- | --- |
| FAIR provenance | pass — accession, analysis id, source URL, license, matrix, contrast, statistic recorded |
| reproducibility | pass — regenerated from declared queries and deterministic matching rules |
| critical evidence | pass — exact vs precursor vs missing evidence kept distinct |
| human review | pass — 6 escalations raised, harmonization blocked |
| mirage detection | pass — rat gap and embargoed human arm reported as availability findings |
