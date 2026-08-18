# MW studies vs MoTrPAC — exercise, diet, physical activity, combined

Synthesis of three parallel agent retrievals (literature-retrieval) against the
public Metabolomics Workbench REST API. Verified live via `/summary`, `/factors`,
and `/mwtab/txt` endpoints on metabolomicsworkbench.org. Seed pool of 338 human
MW candidates at `data/live/mw_human_candidates.csv`.

## MoTrPAC reference design (for the similarity score)

| Element | Human-precovid-sed-adu (acute) | PASS1A/PASS1B (rat) |
|---|---|---|
| Population | Sedentary adults, sex-balanced | Young adult rats, sex-balanced |
| Exercise | Standardized endurance + resistance arms | Acute bout + 1/2/4/8-wk endurance training |
| Tissues | Plasma, adipose, muscle, PBMC, PAXgene | 19 tissues incl. plasma + gastrocnemius |
| Omics | Metab targeted+untargeted, proteomics, transcriptomics, epigenomics | Same multi-omics |
| Timepoints | Pre, during, +10/+15-45 min, +3.5-4 h, +24 h | Pre / post bout / 1-8 wk |
| Diet phenotyping | Dietary intake questionnaires (gated) | n/a |
| Free-living PA | ActiGraph accelerometry (gated) | n/a |
| Clinical | VO2max, DXA, blood chemistry (gated) | Body comp, performance |

**Tier rules.** Tier 1 = closest MoTrPAC parallel (multi-tissue or multi-omics or
multi-timepoint controlled human exercise/diet intervention). Tier 2 = one strong
parallel dimension. Tier 3 = single-timepoint / single-platform / smaller n.

---

## Table 1 — Exercise-only (MoTrPAC-like exercise, non-MoTrPAC depositions)

| study_id | title (≤70 char) | n | year | matrix | design | tier | rationale |
|---|---|---|---|---|---|---|---|
| **[ST000842](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST000842)** | Muscle and plasma before and after exercise | 62 | 2017 | muscle + plasma | acute | **1** | multi-tissue + multi-visit (V1/V4/V5) — closest tissue/timepoint analog |
| **[ST003686](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003686)** | Transpulmonary metabolome — pulm. vasc. disease & exercise | 468 | 2025 | plasma (pulm + radial artery) | acute CPET | **1** | rest / free-wheel / peak / recovery × 2 sampling sites — CPET-style dense sampling |
| **[ST003807](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003807)** | Lipidomics of HIIT in healthy men after metformin | 217 | 2025 | plasma | acute HIIT | **1** | crossover Session × dense Timepoints 0–13 |
| **[ST003662](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003662)** | Metabolome trajectory of exercise physiology — athletes | 352 | 2025 | plasma + blood | training | **1** | 15+ collection points, sex-balanced, CPET phenotypes (VO2max, VT1/VT2, HRmax) embedded |
| **[ST004303](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST004303)** | Exercise intensity modulates human plasma secretome | 67 | 2025 | plasma | acute | **1** | MIE/SIE arms × 3 timepoints — the volcano anchor we already used |
| **[ST001789](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001789)** | Acute metabolomic changes — endurance exercise | 57 | 2021 | plasma | acute | **1** | Pre / +0 / +60 — exact MoTrPAC-style plasma cadence |
| **[ST000777](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST000777)** | Metabolic adaptations to chronic & acute exercise (ATX) | 10 | 2017 | adipose | acute + training | **1** | adipose is a MoTrPAC tissue; pre/post; small n |
| **[ST001068](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001068)** | Proteomic + metabolomic sweat — graded exercise | 50 | 2018 | sweat | acute | 2 | multi-omics (proteomics companion) but non-MoTrPAC matrix |
| **[ST000387](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST000387)** | Metabolome + lipidome response to exercise training | 276 | 2016 | blood | training | 2 | Pre/Post only — large n, single contrast |
| **[ST000659](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST000659)** | Lipid mediators — supervised exercise training (PAD) | 158 | 2017 | plasma | training | 2 | Visits v2/v3 × Draw A/B, plasma only |
| **[ST001780](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001780)** | CSF metabolomic profiles before & after endurance | 38 | 2021 | CSF | acute | 2 | novel matrix, clean pre/post |
| **[ST001907](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001907)** | Training-induced bioenergetic improvement in muscle | 40 | 2021 | skeletal muscle | training | 2 | muscle biopsies pre/post + mitochondrial proteomics companion |
| **[ST002183](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST002183)** | Individualized exercise intervention — multiple myeloma RCT | 180 | 2022 | plasma | training RCT | 2 | RCT vs waitlist × 4 timepoints |
| [ST001251](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001251) | Cold + breathing training during endotoxemia | 138 | 2019 | plasma | training | 3 | exercise combined with non-exercise stimulus |
| [ST000762](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST000762) | Plasma adenosine in scleroderma by exercise status | 51 | 2017 | plasma | observational | 3 | observational dichotomous, no timecourse |

---

## Table 2 — Diet / DHQ-like (intervention or measured intake)

A = controlled dietary intervention. B = free-living cohort with dietary intake as a measured covariate. **No MW study explicitly named FFQ / DHQ / 24-hr recall in its mwTab — this metadata is systematically stripped from MW filings, so all Tier-1 candidates are downgraded and flagged for human review.**

| study_id | title (≤70 char) | n | year | A/B | matrix | tier | rationale |
|---|---|---|---|---|---|---|---|
| **[ST002337](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST002337)** | Guangzhou Nutrition and Health Study (GNHS) — fecal | 1092 | 2022 | B | fecal | 2 | large free-living cohort; mwTab confirms "diet collected at baseline + follow-up" — instrument **not named** (probably FFQ; flag) |
| **[ST001669](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001669)** | GNHS — serum metabolome companion | 1014 | 2021 | B | serum | 2 | companion to ST002337; instrument silent in mwTab (flag) |
| **[ST000992](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST000992)** | Metabolomic markers of dietary patterns — Costa Rica | 79 | 2018 | B | plasma | 2 | "previously derived dietary patterns" tested vs plasma metabolome; instrument used externally (flag) |
| **[ST001932](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001932)** | PFAS × high-fat diet — SEARCH Diabetes in Youth | 2158 | 2022 | B | plasma | 2 | large youth cohort with diet as covariate; instrument silent (flag) |
| **[ST004275](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST004275)** | Cardiometabolic adaptations to 6-mo intermittent fasting RCT | 60 | 2025 | A | plasma | 2 | RCT, baseline + 6-mo plasma untargeted — closest MoTrPAC-like multi-timepoint |
| **[ST004199](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST004199)** | 1-year ketogenic intervention in adolescents w/ obesity | 100 | 2025 | A | serum | 2 | RCT 3 arms × 3 timepoints (0/3/12 mo), CE-TOF + UHPLC multi-platform |
| **[ST002025](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST002025)–30** | Flaxseed 6-wk dietary intervention (postmenopausal) | 86 subj / 356 samp | 2022 | A | serum + stool | 2 | controlled intervention pre/post; multi-platform (HILIC / GC / bile acids) |
| **[ST001490](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001490)** | Low vs high glycemic load crossover RCT | 80 | 2020 | A | plasma | 2 | RCT crossover, 28-d feeding, lipidomics |
| **[ST000485](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST000485)** | 16-wk caloric restriction in obese — plasma | 20 | 2016 | A | plasma | 2 | pre/post with matched controls; multi-timepoint clamp sampling |
| **[ST003895](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003895) / [ST003894](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003894)** | Postprandial macronutrient challenge (24 healthy) | 24 | 2025 | A | plasma | 2 | 4 isocaloric challenges × 5 timepoints (0/30/60/120/180 min); metab + lipid |
| **[ST003896](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003896) / [ST003897](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003897)** | Postprandial MMTT — 147 individuals by BMI | 147 | 2025 | A | plasma | 2 | standardized MMTT × 5 timepoints, BMI-stratified |
| [ST003012](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003012) / [ST003044](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003044) | High-fat eucaloric diet — normal-weight women | 18 | 2024 | A | plasma | 3 | controlled feeding × 3 timepoints; small n |
| [ST001151](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001151) | 4-d Mediterranean vs fast food crossover | 10 | 2019 | A | plasma HDL | 3 | crossover RCT pre/post; tiny n |
| [ST002250](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST002250) | Ramadan diurnal intermittent fasting prospective cohort | 25 | 2022 | A | plasma | 3 | observational pre/post, single platform |
| [ST000628](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST000628)–636 | DASH2 dietary salt controlled feeding (multi-parts) | 20–60 | 2017 | A | urine | 3 | full controlled feeding within-subject; urine not plasma |
| [ST003474](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003474) | Grass-fed vs conventional beef postprandial crossover | 10 | 2024 | A | serum | 3 | crossover, 0–4 h post-meal, n=10 |

---

## Table 3 — Physical activity / free-living wearable

**Verified hits: 0** across the cached 338 PLUS ~200 additional human studies (extended title sweep + per-study `/mwtab` + `/factors` verification, June 2026). The MW public corpus does not appear to expose any human study with objective free-living PA monitoring (ActiGraph / Actiwatch / Fitbit / accelerometer / MVPA / step-count) alongside released metabolomics.

Closest near-misses (reviewed and rejected with reason):

| study_id | title (≤70 char) | n | year | what was found | why rejected |
|---|---|---|---|---|---|
| [ST003110](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003110) | Lifestyle Factors on Epigenetic / Proteomic Biomarkers | 136 | 2024 | summary mentions "physical activity patterns" (Nieman / Appalachian Human Performance Lab) | no actigraphy/wearable string in mwTab; PA characterization is questionnaire-style |
| [ST003662](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003662) | Metabolome trajectory of exercise physiology — athletes | 352 | 2025 | per-subject CPET: VO2max, VT1/VT2, HRmax, Performance[W], Sports/yr | lab CPET only; no free-living wearable |
| [ST001440](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001440) | Plasma biomarkers of insufficient sleep | 225 | 2019 | controlled in-lab sleep restriction, energy-balanced diet | in-lab protocol; no actigraphy reported |
| [ST001003](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001003) / [ST001002](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001002) | Female urine outpatient circadian phase pilot | 100 / 516 | 2018 | circadian sampling | no PA monitoring |
| [ST002993](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST002993) | Subgroups of childhood obesity by metabotyping | 111 | 2023 | summary phrase "diet, physical activity, culture" | descriptive only; PA not a measured factor |

**Interpretation.** Accelerometry/actigraphy is effectively absent from MW depositions — a missing-modality / availability gap, exactly the "mirage" pattern your workbench is designed to flag. MoTrPAC's free-living PA data exists but lives in the access-controlled human arm, not the public omics release.

---

## Table 4 — Combined exercise + diet (± PA)

**No Tier-1 candidate** (Tier 1 would require explicit factors/mwTab for **all three** of exercise, diet, **and** objective free-living PA in human plasma metabolomics).

| study_id | title (≤70 char) | n | year | exposures (Ex / Diet / PA) | matrix / omics | tier | rationale |
|---|---|---|---|---|---|---|---|
| **[ST003806](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003806)** | Hemp fiber ingestion on post-exercise gut permeability | 464 | 2025 | Ex + Diet | plasma + urine, untargeted | 2 | clear ex + diet crossover, multi-matrix; no PA |
| **[ST003807](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003807)** | HIIT in healthy men after metformin (lipidomics) | 217 | 2025 | Ex + Diet (+ drug) | plasma lipidomics | 2 | both verified in factors (Session × Timepoints) |
| **[ST003110](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003110)** | Lifestyle Factors → Epigenetic / Proteomic Biomarkers | 136 | 2024 | Ex + Diet + PA (all referenced) | plasma metab + proteomics + epigenetic | 2 (borderline) | three exposures referenced narratively but not as separate factors; multi-omic |
| **[ST003662](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003662)** | Exercise physiology metabolome trajectory — athletes | 352 | 2025 | Ex + supplement/food fields per subject | plasma + CPET phenotypes | 2 | rich CPET + diet/supplement; PA = habitual sport days/yr only |
| [ST003012](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003012) / [ST003044](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003044) | High-fat eucaloric diet → reprometabolic syndrome | 50 | 2023–24 | Diet only | plasma metab + lipid | 3 | diet only, no Ex/PA |
| [ST003031](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST003031) | Early time-restricted eating, cardiometabolic markers | 88 | 2024 | Diet | plasma | 3 | diet only; CGM glucose context |
| [ST002250](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST002250) | Ramadan intermittent fasting | 100 | 2022 | Diet | plasma | 3 | diet only |
| [ST002183](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST002183) | Individualized exercise in multiple myeloma RCT | 180 | 2022 | Ex (CRF measured) | plasma metab + lipid | 3 | exercise-only |
| [ST000777](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST000777) | Acute + chronic exercise in overweight adults (ATX) | 10 | 2017 | Ex | plasma | 3 | ex only |
| [ST001440](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?StudyID=ST001440) | Biomarkers of insufficient sleep | 225 | 2019 | Sleep + Diet (energy-balanced) | plasma | 3 | sleep + diet, no Ex/PA |

---

## Top picks if you want to act on this

If the goal is the **closest single MW analog to MoTrPAC human acute exercise** —
**ST003686** (CPET multi-site arterial, n=468, 2025), **ST003807** (HIIT crossover with rich timepoints, n=217), **ST003662** (athlete trajectory, n=352, CPET phenotypes embedded), and **ST000842** (multi-tissue muscle+plasma) are the strongest.

If the goal is **MoTrPAC-style multi-exposure (ex + diet)** — **ST003806** (hemp fiber + cycling bout) and **ST003807** (HIIT + metformin) are the only clear two-exposure candidates with crossover designs.

If the goal is **free-living PA + metabolomics** — MW won't deliver this; the practical path is a companion repository (dbGaP / UK Biobank) or the gated MoTrPAC human phenotypic release under a data-use agreement.

## Caveats / human-review queue

- All "intake-as-covariate" diet flags (ST002337, ST001669, ST000992, ST001932) need
  parent-publication verification of the dietary instrument — MW mwTab does not name it.
- ST003110 (Nieman lifestyle) should be re-reviewed against its companion publication
  for the actual PA assessment instrument.
- The 0/338 accelerometry finding is hardened by the extended +200-study sweep, but
  remains conditional on MW choosing to expose PA covariates in mwTab — true absence
  vs reporting omission cannot be fully disambiguated from the API alone.

Verification basis throughout: live calls (June 2026) to
`https://www.metabolomicsworkbench.org/rest/study/study_id/<ID>/{summary,factors,mwtab/txt}`.
