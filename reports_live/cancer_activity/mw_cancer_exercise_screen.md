# Cancer studies in Metabolomics Workbench with exercise, physical-activity, or actigraphy data

<p class="subtitle">Complete corpus re-screen &mdash; 4,503 studies, live REST metadata retrieved 2026-08-26. Every claim below was re-derived independently by six parallel verification agents; their corrections are incorporated and attributed. Every <code>ST</code> identifier links to its Metabolomics Workbench study page.</p>

## Bottom line

> The answer depends on what counts, so here it is in tiers. Deposited factors were screened for all 4,503 studies in the corpus; submitter prose was screened for 798 of the 804 cancer studies (99.3%).
>
> **Exercise as an intervention: 1 study.** [ST002183](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002183), a randomised trial of individualised exercise in multiple myeloma. The only cancer study where exercise appears in deposited metadata at all &mdash; and it appears as a trial-arm value (`Group:exercise`), not as a named exercise variable.
>
> **Objective physical function measured: 2 studies.** [ST004161](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004161) (plasma) and [ST004166](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004166) (muscle) measured handgrip strength, stair-climb power, and CT muscle cross-sectional area in 88 men with gastrointestinal or genitourinary cancer. Those measurements are described in the study prose but are **not deposited** &mdash; the factor table carries only weight-loss group.
>
> **Rodent voluntary activity measured: 1 study.** [ST002163](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002163) recorded voluntary wheel-running activity in cancer-bearing mice. Again described in prose, not deposited.
>
> **Actigraphy, accelerometry, or any wearable-derived measure: 0 studies.** Zero in the deposited factors of all 4,503 studies, and zero in the prose of 798 cancer studies.
>
> **Lung cancer specifically: 0 studies**, at both layers, under all four defensible constructions of the lung set (56, 62, 70, or 75 studies). For lung cancer, exercise-metabolomics is an availability gap in this repository.
>
> The pattern across all of these is the same: where activity or function data exists, it was measured but not deposited. Read every zero as a statement about **what Metabolomics Workbench holds**, not about what the parent studies measured.

## Corrections to the first pass

| | First pass | Verified | What was wrong |
|---|---|---|---|
| Corpus size | 4,499 (snapshot) | **4,503 unique studies** (4,504 returned rows) | The listing endpoint emits one row per species, so [ST002097](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002097) appears twice. A corpus size of 4,504 is a row count, not a study count. The +4 versus the snapshot ([ST004154](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004154), [ST004298](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004298), [ST004823](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004823), [ST004824](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004824)) are newly *released* older submissions, not new accessions &mdash; the maximum accession, ST005132, is unchanged. |
| Cancer studies | 478 | **790** (see range below) | MW publishes a curated `Disease` field. It labels 770 studies oncologic, of which **312 have no oncology word in their title** and were invisible to the first screen &mdash; e.g. [ST000494](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000494) (palmitate isotopomers in LNCaP cells), [ST001049](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001049) (P4HA1 knockdown in MDA-231), [ST000821](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000821) (IDH1 mutation profiling). The 478 figure reproduces exactly; it is a recall failure, not an arithmetic one. |
| Lung-cancer studies | 57 (38 human, 19 mouse) | **56 to 75**, construction-dependent | The 57 reproduces, but includes a confirmed false positive: [ST002058](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002058) "Muscle/Lung/Tumor metabolomics" is a 4T1 **breast** cancer cachexia model. Adding MW's `Disease` label and cell-line curation raises the set. |
| Exposure detector | sample factors only | factors (4,503/4,503) + titles + reverse keyword search + prose | Calibration: of the 149 studies with "exercise" in the title, only 14 encode an exercise term in their factors &mdash; **~9% sensitivity**. The first pass rested on a detector that misses nine exercise studies in ten. |
| Search layers | factors + titles | + reverse keyword search + **submitter prose, 798 of 804 cancer studies** | The prose sweep found three studies with real activity or physical-function measurements that the factor screen could not see, because the measurements were never deposited as variables. The first pass would have reported those studies as having no activity data. |
| Wording | "has no exercise variable" | "deposits no exercise variable in MW structured metadata" | MW's factor field is an arm-and-timepoint slot, not a covariate inventory. The original wording would license a claim the evidence does not support &mdash; and which is contradicted for at least one study (below). |

**The headline changed in one direction only.** No second exercise *intervention* exists &mdash; four search directions converge on ST002183 for that. But the prose sweep added three studies that measured physical function or voluntary activity without depositing it, which the structured screen alone reported as nothing.

## The cancer denominator is a range, and it does not matter

MW's oncology vocabulary is coarse: the only cancer values in its 258-term `Disease` field are `Cancer` (765 studies), `Lung cancer` (14), and `Multiple myeloma` (1), plus `Cachexia` (28). There is no NSCLC, no lung adenocarcinoma, no mesothelioma, no per-site term at all. So the cancer set has to be assembled, and the total depends on documented judgment calls:

| Construction | Studies |
|---|---|
| Oncology title regex alone | 473&ndash;478 (regex-dependent) |
| MW curated `Disease` field alone, cachexia excluded | 770 |
| **Union of the two &mdash; the figure used throughout** | **790** |
| Union including the 16 cachexia-only studies | 806 |
| Union including cancer-derived cell lines used as generic in-vitro models | 827 |

A hard recall ceiling sits under all of these: **1,775 studies (39.4%) have no `Disease` annotation at all**, and 1,737 of them have no cancer word in the title either. The true cancer count is bounded below by 790 and is not determinable from these endpoints.

**This ambiguity does not affect the answer.** The exposure screen was run over the sample factors of **all 4,503 studies in the corpus**, not over a cancer subset. Whichever way the cancer set is drawn, the exercise result is the same, because every candidate was screened.

## How the screen was run

**1. Structured metadata, whole corpus.** Sample-level factors were fetched for all 4,503 studies. Every distinct factor string and sample-source value was matched against an exercise vocabulary: exercise, actigraphy, accelerometer, physical activity, treadmill, wheel running, VO<sub>2</sub>max, cardiorespiratory, MVPA, sedentary, step count, pedometer, activity monitor, wearable, aerobic/endurance/resistance/strength training, detraining, bed rest, immobilisation, HIIT, sprint interval, cycle ergometer, walk test, fitness test, athlete, trained/untrained. Thirty-five studies matched corpus-wide; every match was adjudicated by hand.

**2. Reverse keyword search.** MW's keyword endpoint was queried for 20 exercise terms and the returned IDs intersected with the cancer set, to catch any study naming an exercise exposure in its title but not its factors.

| Term | Hits | | Term | Hits | | Term | Hits |
|---|---|---|---|---|---|---|---|
| exercise | 149 | | endurance | 117 | | prehabilitation | 0 |
| training | 122 | | fitness | 2 | | rehabilitation | 0 |
| physical activity | 0 | | VO2 | 0 | | running | 3 |
| actigraphy | 0 | | sedentary | 1 | | resistance training | 0 |
| accelerometer | 0 | | walking | 0 | | cardiorespiratory | 0 |
| aerobic | 8 | | athlete | 2 | | wheel running | 0 |
| treadmill | 0 | | cachexia | 27 | |  |  |

All 20 queries were reachable, so each zero is a true zero-hit result rather than an unreachable index. The exercise side unions to **193** studies.

**3. Submitter prose.** Free text is reachable only by an indirect route: the study-level `mwtab` endpoint returns several concatenated JSON documents (one per analysis) and cannot be parsed as one document, so prose must be pulled per analysis via `/rest/study/analysis_id/<AN id>/mwtab`. The design description lives in `STUDY_SUMMARY`, `PROJECT_SUMMARY`, and &mdash; where an intervention arm is described &mdash; `TREATMENT_SUMMARY`. A verification agent read the prose of 122 cancer studies this way and found exactly one genuine exercise study, ST002183; seven of its eight regex hits were false positives on "training set" and "trained interviewer".

That blind spot has since been closed. Prose was retrieved and screened for **798 of the 804 cancer studies (99.3%)**, including **74 of the 75 lung studies**. Six studies could not be parsed because of the concatenated-JSON defect described below and are recorded as unavailable, not as negative: [ST001269](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001269), [ST002967](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002967), [ST003617](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003617), [ST003921](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003921), [ST004438](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004438), [ST004470](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004470). Seven studies tripped the exercise/function vocabulary; all seven were adjudicated by hand and are set out in the next section.

## Result 1 &mdash; the one cancer exercise study

**[ST002183](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002183) &mdash; Individualized exercise intervention for people with multiple myeloma improves quality of life in a randomized controlled trial**

| Field | Value |
|---|---|
| MW `Disease` | Multiple myeloma |
| Species | Homo sapiens |
| Sample source | Blood (plasma) |
| Institute | QIMR Berghofer Medical Research Institute |
| Platform | LC-MS |
| Rows in factors table | 180 |
| Released | 2024-02-05 |
| Licence | CC BY 4.0 |
| Factor keys | `Group`, `Time_point` &mdash; two keys only |
| `Group` values | waitlist 75 &middot; exercise 51 &middot; MS2 32 &middot; QC 16 &middot; Blank 6 |

This is the only exercise signal in MW oncology, and it is thinner than a first read suggests. Five things a human must settle before anyone computes a pre/post contrast from it:

1. **The exposure is an arm label, not a variable.** The factor keys are the generic `Group` and `Time_point`; the word "exercise" appears only as a value. No dose, modality, session adherence, or objective activity measure is deposited. A trial that coded its arms `A/B` or `INT/CON` would be invisible to this screen entirely.
2. **The waitlist arm crosses over to the same exercise programme.** It is therefore not an unexposed control at later timepoints, and cannot be treated as one.
3. **Timepoint coding is asymmetric between arms** &mdash; exercise carries `-`, `1`, `3`; waitlist carries `-`, `1`, `2`, `4`. `Time_point:-` is baseline, not a missing value.
4. **`Group:MS2` and `Group:QC` are analytical injections, not study arms** (54 of the 180 rows), and the factor vocabulary does not mark them as such.
5. **There is no subject identifier field.** Participant identity is recoverable only by string-parsing sample IDs, and the two analyses' sample-factor blocks are byte-identical and carry only HILIC-negative filenames, which contradicts the factors endpoint. Quantitative values are not retrievable from the standard named-metabolite REST outputs.

## Result 2 &mdash; what the prose found that the factors could not

Seven of 798 cancer studies mention an activity, exercise, or physical-function term in their submitter prose. Four are genuine measurements, and none of the four deposits the measurement as a variable.

| Study | Species, n | What was measured | Deposited? |
|---|---|---|---|
| [ST002183](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002183) | human, 180 rows | Randomised exercise vs waitlist; prose adds that cardiorespiratory fitness improved | Arm label only (`Group:exercise`) |
| [ST004161](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004161) | human, 88 plasma | Handgrip strength, stair-climb power, CT lumbar muscle cross-sectional area, >5% weight loss | **No** &mdash; factors carry only `Group:WeightLoss/WeightStable` |
| [ST004166](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004166) | human, 79 muscle | Same three function measures, rectus abdominis biopsy at surgery | **No** &mdash; same two-value factor table |
| [ST002163](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002163) | mouse, 37 liver | Voluntary wheel-running activity in 4T1 tumour-bearing and sham mice, with and without Nnmt deletion | **No** &mdash; factors carry genotype, tumour group, sex, treatment |

The remaining three are not activity data:

- [ST002167](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002167) is the AML12 cell-culture companion to ST002163 and shares its abstract; the wheel-running sentence describes the mouse study, not this one.
- [ST003315](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003315) (neoadjuvant breast cancer trial) used ECOG performance status &le;2 as an *eligibility criterion*. An entry filter is not a measured variable.
- [ST001237](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001237) (PD-1 blockade, 1,221 samples) deposits `CRF_MSKCC_Risk_Group`, a composite prognostic score that *incorporates* performance status. Functional status is embedded in a risk category, not deposited separately and not recoverable from it.

### Why this matters more than the headline count

[ST004161](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004161) and [ST004166](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004166) are a paired plasma-and-muscle study in 88 men with cancer, with objective physical-function phenotyping (handgrip strength, stair-climb power) and CT muscularity, explicitly designed to ask which metabolic signals track poor physical function. That is the closest existing analogue in MW oncology to an exercise-metabolomics design. The function measurements exist; they are simply not in the repository. Obtaining them is a data request to the submitting group (VA Puget Sound Health Care System), not a new study.

Note the distinction that has to be kept: handgrip strength and stair-climb power are measures of physical **capacity**, and voluntary wheel running is a measure of **activity**. Neither is an exercise intervention, and neither can be relabelled as one.

## Result 3 &mdash; no wearable or actigraphy data, anywhere

Across all 4,503 studies, **zero** deposit an actigraphy, accelerometer, wearable, pedometer, step-count, MVPA, IPAQ, or GPAQ variable. The prose sweep reproduces the zero at the second layer: no such term appears in the submitter prose of any of the 798 cancer studies screened, and a verification agent found the same zero independently over its own 122-study prose sample.

This is not a schema limitation. MW can carry a physical-activity variable: [ST001749](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001749) (REACH Metabolomics Study, Alzheimer's disease) deposits an explicit `physical activity` factor. No oncology study does.

## Result 4 &mdash; what cancer studies *do* deposit about lifestyle

The most informative finding of the verification pass is a selective-deposition pattern. Scanning factor **keys** across the 789-study cancer set:

| Subject-level covariate | Cancer studies depositing it |
|---|---|
| Smoking (`Smoker`, `Smoking Status`, pack-years) | 11 of 789 (1.4%) &mdash; and **8 of 42 human lung studies (19%)** |
| Diet | 15 of 789 (1.9%), of which 14 are mouse dietary-intervention arms |
| BMI or anthropometry | **0 of 789 (0.0%)** |
| Physical activity or fitness | **0 of 789 (0.0%)** |

Human lung-cancer studies routinely deposit smoking status &mdash; the covariate their analysis needs. They deposit no activity and no BMI. That is a pattern of *selective deposition*, and it is the reason the absence of activity data in MW cannot be read as absence of measurement upstream.

## Lung cancer in detail

The lung set has four defensible constructions. **All four screen to zero.**

| Construction | Studies | Exercise/activity variables |
|---|---|---|
| Lung title regex within the title-cancer set (first pass, minus the [ST002058](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002058) false positive) | 56 (38 human, 18 mouse) | 0 |
| Union with MW `Disease` = `Lung cancer` | 62&ndash;64 (42&ndash;44 human, 19&ndash;20 mouse) | 0 |
| Plus cell-line curation (A549, H1299, PC9, 393P) | 70 (51 human, 19 mouse) | 0 |
| Plus a `Lung` sample-source annotation within the cancer set | 75 (53 human, 22 mouse) | 0 |

Three further facts sharpen the picture:

- **The lung factor vocabulary contains no activity construct at all.** Across the whole set there are 58 distinct factor keys and not one is an activity, fitness, or functional-capacity measure &mdash; no ECOG, no Karnofsky, no 6-minute walk. An over-inclusive 44-alternative screen returned only homonyms (`meth` inside `methylation_rank` and `methionine_condition`), and its positive control fired correctly on ST002183.
- **Study count overstates the evidence base.** [ST003883](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003883)&ndash;[ST003893](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003893) is eleven studies from one paper, and accounts for 10 of the 14 studies MW labels `Lung cancer`. The 75 studies represent roughly 8 independent mouse investigations plus the human sets.
- **MW records zero mesothelioma studies corpus-wide**, so that branch of any lung screen is dead.

The lung result is now checked at both layers: 0 of 75 in deposited factors, and 0 of the 74 lung studies whose submitter prose could be parsed. Only [ST001269](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001269) (exosomal lipids in NSCLC staging) remains unscreened in prose, and it is recorded as unavailable.

### Why the data is not there

| Design archetype | Studies (curated set of 70) |
|---|---|
| In-vitro / cell line | 31 |
| Mouse or rodent in-vivo tumour model | 13 |
| Human diagnostic / biomarker discovery | 18 |
| Human treatment-response | 6 |
| Human prospective / cohort | 2 |

Forty-four of 70 (63%) are cell culture or mouse &mdash; designs that cannot host an activity exposure. Of the 26 human studies, 24 are cross-sectional case-control diagnostic or treatment-response designs. Only two are prospective. The lung set's problem is not a missing field; it is that the designs cannot carry one.

### The two lung studies that are worth a data request

**[ST002773](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002773) &mdash; the strong case.** A nested case-control of untargeted plasma metabolomics and lung cancer among never-smoking women, inside the prospective Shanghai Women's Health Study. Primary publication: [PMID 38651675](https://pubmed.ncbi.nlm.nih.gov/38651675/), [10.1002/ijc.34929](https://doi.org/10.1002/ijc.34929), *International Journal of Cancer*, 2024, peer-reviewed, accession-verified.

MW deposits two factor keys for it &mdash; `Subject_ID` and `LungCancer` &mdash; across 1,152 rows. But MW's own `COLLECTION_SUMMARY` states that the SWHS parent cohort followed 74,942 women "through multiple in-person interviews and self-administered questionnaires to obtain information on demographics, occupational and environmental exposures, lifestyle, dietary, and other factors, including environmental tobacco smoke and body mass index." The SWHS physical-activity questionnaire is separately published and validated ([PMID 14630608](https://pubmed.ncbi.nlm.nih.gov/14630608/)), with MET-hour analyses in the literature ([PMID 17478434](https://pubmed.ncbi.nlm.nih.gov/17478434/)).

> For this study, the missing activity variable is a **deposition gap, not a measurement gap**. Whether physical activity is available for these specific 790 women is an open data-request question. It must not be scored as a cohort that did not measure activity.

**[ST002082](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002082) &mdash; the weaker case.** A prospective study of metabolic change in the dying process in lung cancer patients. Primary publication: [PMID 40016594](https://pubmed.ncbi.nlm.nih.gov/40016594/), [10.1038/s43856-025-00764-3](https://doi.org/10.1038/s43856-025-00764-3), *Communications Medicine*, 2025, peer-reviewed. MW deposits a single factor key, `Time before death (weeks)`, over 112 urine samples. Its `COLLECTION_SUMMARY` notes that "an anonymised record of the medication administered was collected" &mdash; a covariate collected but not deposited, which by itself proves the deposited factor set is a subset of what was recorded. Verdict: **unresolved**, with no positive evidence either way.

Abstract-text scans of both primary publications and two companion papers found no physical-activity, actigraphy, accelerometry, or fitness term (an initial substring scan reported "ECOG" in both; on inspection both were the letters inside "Recognizing", and were discarded). Abstract silence is not evidence of non-collection, and this is labelled publication-text inference throughout.

## What this means for an exercise-oncology aim

1. **A lung-cancer exercise-metabolomics question cannot be answered from Metabolomics Workbench.** No study deposits the exposure, under any construction of the lung set. Represent this as an availability gap; do not approximate it with a nearby cohort.
2. **[ST002183](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002183) is the only cancer exercise study, and it is multiple myeloma** with a crossover control arm and no quantified exposure. It can support a hypothesis-generating group contrast after the five issues above are adjudicated. It cannot support a lung-cancer claim.
3. **Three data requests, not a dead end.** [ST002773](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002773) (Shanghai Women's Health Study &mdash; validated physical-activity questionnaire upstream, plasma metabolomics deposited) and the paired [ST004161](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004161)/[ST004166](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004166) (objective handgrip and stair-climb power in 88 men with cancer, plasma and muscle metabolomics deposited) are the highest-value follow-ups in the whole screen. In all three the phenotype was measured and is simply not in the repository.
4. **Do not write the sentence "lung-cancer cohorts do not measure physical activity."** It is unsupported by this evidence and directly contradicted for ST002773. The defensible sentence is that no lung-cancer study *deposits* an activity variable in Metabolomics Workbench.
5. **For a rodent arm, [ST002163](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002163) is the only cancer study in MW that measured voluntary activity** (wheel running in 4T1 tumour-bearing mice, with an Nnmt-knockout rescue). The activity data is not deposited, and MW holds only 4 rat cancer studies in total, which limits any MoTrPAC rat-side alignment.
6. **The cachexia cluster is the realistic adjacent resource** for muscle-metabolism questions in cancer &mdash; 28 studies under MW's `Cachexia` label, including a 12-part human muscle-and-serum series ([ST001005](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001005)&ndash;[ST001018](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001018)) and a 10-tissue mouse series ([ST002881](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002881)&ndash;[ST002904](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002904)). Cachexia is a wasting phenotype, not an activity exposure, and must be labelled as such.

## Limits, and what a reader may not conclude

| Limit | Consequence |
|---|---|
| 1,775 studies (39.4%) carry no `Disease` annotation; 1,737 have no cancer word in the title either | The 790-study cancer set is a floor. An unannotated oncology study with a mechanistic title sits outside it. |
| Factor-only exposure detection is ~9% sensitive | Structured metadata alone cannot close this question, which is why titles, keyword search, and prose were added. |
| "Human" in the species field does not mean human subjects | 389 of 790 cancer studies (49.2%) have in-vitro titles, and MW labels a HeLa or LNCaP study *Homo sapiens*. No count of "human cancer studies" here should be read as a count of human cohorts. This is text inference. |
| Prose unavailable for 6 of 804 cancer studies | [ST001269](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001269), [ST002967](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002967), [ST003617](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003617), [ST003921](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003921), [ST004438](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004438), [ST004470](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004470) could not be parsed. They are an **unscreened** residue, not a negative result. |
| Prose is a submitter-written abstract of variable depth | A study that measured activity and described it in neither its factors nor its abstract is still invisible. The three studies found here were found *because* their abstracts happened to name the measure. |
| MW prose is a submitter-written abstract | It is not a data-availability statement. Nothing here resolves what any parent study collected. |
| Absence is deposition-level throughout | Every zero in this report means "not deposited in Metabolomics Workbench". For at least one study the parent cohort demonstrably did measure more than it deposited. |

### Repository defects found along the way

These are FAIR findings in their own right and were reported by the verification agents:

- The study-level `mwtab` endpoint returns **concatenated JSON documents** (one per analysis) with no array wrapper, so it cannot be parsed as one document. Use `/rest/study/analysis_id/<AN id>/mwtab`.
- `/rest/study/study_id/<ST id>/untarg_studies` **ignores the study ID** and returns a corpus-wide listing of 2,395 analyses; two different study IDs return byte-identical payloads. Any per-study fact read from it is a mirage.
- [ST003117](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003117) is indexed in the disease table (`Malaria`) but its summary endpoint returns `[]`. [ST003478](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003478) returns `[]` for both species and disease &mdash; unavailable, not absent.
- MW `Disease` curation is internally inconsistent within a single submission series: of four studies from one lab's NCI-H1299 MAT2A experiment ([ST004220](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004220), [ST004221](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004221), [ST004225](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004225), [ST004253](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004253)), three are labelled `Lung cancer` and one `Cancer`.
- Europe PMC's fielded `FULL_TEXT:"ST002773"` query returns zero hits while the unfielded query returns two. A fielded zero there is an index-coverage artefact, not an absence.

## Verification

Six independent agents re-derived these claims in parallel, each instructed to refute rather than confirm: on the cancer denominator, an adversarial hunt for a second cancer exercise study, the field-level facts of ST002183, the lung slice, free-text reachability, and the two deposition questions. Outcome: the three headline counts were corrected, the headline answer survived all four search directions, and eight new findings were added &mdash; the crossover control arm, the selective-deposition pattern, the SWHS deposition gap, and the repository defects above. All network access ran through the two allowlisted clients; no synthetic record was substituted for any unavailable one.

## Provenance

| Item | Value |
|---|---|
| Corpus listing | `/rest/study/study_id/ST/summary` &mdash; 4,504 rows, 4,503 unique studies, 2026-08-26 |
| Disease vocabulary | `/rest/study/study_id/ST/disease` &mdash; 2,864 rows, 2,729 studies, 258 distinct values |
| Species, sample source | `/rest/study/study_id/ST/species` (4,777 rows), `/rest/study/study_id/ST/source` (4,891 rows) |
| Per-study factors | `/rest/study/study_id/<ST id>/factors` &mdash; 4,503 of 4,503 retrieved |
| Keyword search | `/rest/study/study_title/<term>/summary` &mdash; 20 terms, all reachable |
| Free text | `/rest/study/analysis_id/<AN id>/mwtab`, prose blocks only |
| Literature | Europe PMC REST via the allowlisted literature client |
| Prior snapshot | `data/live/mw_corpus_snapshot/manifest.json`, 2026-08-24T04:29:22Z |

<hr>

## Appendix A &mdash; the lung-cancer set (75 studies, source-inclusive construction)

Exercise or physical-activity variable in deposited factors: **none**, every row.

| Study | Species | Source | n | Platform | Released | Title |
|---|---|---|---|---|---|---|
| [ST000010](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000010) | human | Lung | 39 | LC-MS | 2013-05-03 | Lung Cancer Cells 4 |
| [ST000104](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000104) | human | Blood | 68 | NMR | 2016-06-18 | Factors for Epigenetic Silencing of Lung Cancer Genes |
| [ST000142](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000142) | human | Lung | 4 | LC-MS | 2015-03-12 | H1299 13C-labeled Cell Study |
| [ST000220](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000220) | human | Lung | 21 | LC-MS | 2016-07-08 | Small cell lung cancer metabolome (part II) |
| [ST000367](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000367) | human | Lung | 12 | LC-MS | 2016-03-21 | Distinctly perturbed metabolic networks underlie differential tumor t… |
| [ST000368](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000368) | human | Blood | 192 | GC-MS | 2016-04-08 | Investigation of metabolomic blood biomarkers for detection of adenoc… |
| [ST000369](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000369) | human | Blood | 181 | GC-MS | 2016-04-03 | Investigation of metabolomic blood biomarkers for detection of adenoc… |
| [ST000385](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000385) | human | Blood | 192 | GC-MS | 2016-04-30 | Investigation of metabolomic blood biomarkers for detection of adenoc… |
| [ST000386](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000386) | human | Blood | 180 | GC-MS | 2016-04-25 | Investigation of metabolomic blood biomarkers for detection of adenoc… |
| [ST000388](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000388) | human | Blood | 95 | LC-MS | 2016-05-01 | Serum phosphatidylethanolamine levels distinguish benign from maligna… |
| [ST000389](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000389) | human | Blood | 95 | GC-MS | 2016-05-01 | Serum phosphatidylethanolamine levels distinguish benign from maligna… |
| [ST000390](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000390) | human | Lung | 87 | GC-MS | 2016-06-18 | Metabolomic markers of altered nucleotide metabolism in early stage a… |
| [ST000391](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000391) | human | Lung | 87 | LC-MS | 2016-06-18 | Metabolomic markers of altered nucleotide metabolism in early stage a… |
| [ST000392](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000392) | human | Blood | 183 | GC-MS | 2016-06-18 | Systemic Metabolomic Changes in Blood Samples of Lung Cancer Patients… |
| [ST000396](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000396) | human | Blood | 299 | GC-MS | 2016-06-18 | Lung Cancer Plasma Discovery |
| [ST001269](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001269) | human | Blood | 95 | MS(Dir. Inf.) | 2019-10-11 | Exosomal lipids for classifying early and late stage non-small cell l… |
| [ST001527](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001527) | human | Tumor cells | 72 | LC-MS | 2022-08-01 | Lung cancer metabolomics analysis |
| [ST001610](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001610) | human | Lung | 18 | LC-MS | 2020-12-09 | Control (DMSO 0.1%; v/v) and 10 µM DRB18 treated A549 lung cancer cel… |
| [ST001779](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001779) | human | Lung | 36 | LC-MS | 2021-05-21 | Untargeted Metabolomics analysis of A549 treated with 0.5 mM extracel… |
| [ST001937](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001937) | human | Blood | 1160 | GC-MS/LC-MS | 2023-09-11 | Comprehensive plasma metabolomics and lipidomics based management of … |
| [ST002058](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002058) | mouse | Lung/Muscle | 32 | LC-MS | 2022-02-14 | Muscle/Lung/Tumor metabolomics |
| [ST002066](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002066) | mouse | Lung | 31 | LC-MS | 2022-05-02 | Glutaminase inhibition impairs CD8 T cell activation in STK11/Lkb1 de… |
| [ST002082](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002082) | human | Urine | 112 | LC-MS | 2022-02-24 | Predicting dying: a study of the metabolic changes and the dying proc… |
| [ST002120](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002120) | human | Lung | 229 | LC-MS | 2022-07-20 | Feasibility of detecting AC and SCC using UPLC-HRMS based tissue meta… |
| [ST002223](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002223) | mouse | Heart/Kidney/Liver/Lung | 63 | LC-MS | 2022-08-03 | Metabolic profiling of mouse tissues and tissue interstitial fluids |
| [ST002703](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002703) | human | Lung | 12 | LC-MS | 2023-11-30 | Multi-Omics Analysis Revealed a Significant Molecular Changes in Doxo… |
| [ST002719](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002719) | human | Lung | 6 | LC-MS | 2023-06-21 | Comparison of metabolic of A549 cells before and after Gossypol aceta… |
| [ST002755](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002755) | human | Lung | 24 | LC-MS | 2023-07-18 | Metabolomics Profiling of the Antiproliferative, Anti-migratory and A… |
| [ST002773](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002773) | human | Blood | 1152 | LC-MS | 2024-02-28 | A nested case-control study of untargeted plasma metabolomics and lun… |
| [ST002851](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002851) | mouse | Liver/Lung | 30 | LC-MS | 2023-10-02 | Metabolic caracterization of liver metastasis organotropism |
| [ST002962](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002962) | mouse | Lung Tumors | 33 | LC-MS | 2024-01-16 | LC/MS detection for NADPH and NADP+ levels in KRAS-driven lung tumors… |
| [ST002963](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002963) | mouse | Lung Tumors | 33 | LC-MS | 2024-01-16 | LC/MS detection for GSH and GSSG levels in KRAS-driven lung tumors wi… |
| [ST002996](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002996) | human | Lung | 230 | LC-MS | 2023-12-27 | Tissue Lipidomic Profiling for Detection of Non-Small Cell Lung Cancer |
| [ST002999](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002999) | mouse | Cultured cells | 56 | LC-MS | 2023-12-08 | Metabolomics and glucose and glutamine labeled isotope tracing analys… |
| [ST003193](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003193) | human | Liver/Lung/Lymph node/Peritoneal fluid/Spinal cord | 26 | LC-MS | 2024-05-29 | Metabolomics study on frozen tissue derived from the tumor and adjace… |
| [ST003286](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003286) | human | Cultured cells | 81 | NMR | 2024-07-03 | Interaction between NSCLC cells, CD8+ T cells and immune checkpoint i… |
| [ST003287](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003287) | human | Cultured cells | 22 | NMR | 2024-07-22 | Metabolic profiling and synergistic therapeutic strategies unveil the… |
| [ST003322](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003322) | human | Breath | 108 | LC-MS | 2024-08-01 | EBC metabolomics in non-small cell lung cancer patients and control i… |
| [ST003370](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003370) | human | Cultured cells | 72 | LC-MS | 2024-08-20 | An untargeted metabolomic analysis of acute AFB1 treatment in liver, … |
| [ST003578](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003578) | human | Cultured cells | 24 | FIA-MS | 2025-03-31 | NRF2 supports non-small cell lung cancer growth independently of CBP/… |
| [ST003581](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003581) | human | Saliva | 1043 | MS(Dir. Inf.) | 2026-02-01 | Rapid and non-invasive early detection of lung cancer by integration … |
| [ST003599](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003599) | human | Lung | 73 | LC-MS | 2025-07-25 | Multi-omic profiling of squamous cell lung cancer identifies metaboli… |
| [ST003623](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003623) | human | Cultured cells | 32 | LC-MS | 2025-01-02 | NRF2 supports non-small cell lung cancer growth independently of CBP/… |
| [ST003624](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003624) | human | Cultured cells | 16 | LC-MS | 2025-01-02 | NRF2 supports non-small cell lung cancer growth independently of CBP/… |
| [ST003625](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003625) | human | Cultured cells | 60 | LC-MS | 2025-01-02 | NRF2 supports non-small cell lung cancer growth independently of CBP/… |
| [ST003740](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003740) | human | Blood | 115 | LC-MS | 2026-01-02 | Distinct metabolic signatures in non-small cell lung cancer subtype: … |
| [ST003883](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003883) | mouse | Blood/Lung/Tumor tissue | 219 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003884](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003884) | mouse | Tumor cells | 108 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003885](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003885) | mouse | Culture media | 34 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003886](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003886) | mouse | Cultured cells | 48 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003887](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003887) | mouse | Culture media | 148 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003888](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003888) | mouse | Muscle | 51 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003889](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003889) | mouse | Lung | 49 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003890](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003890) | mouse | Liver | 51 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003891](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003891) | mouse | Blood | 51 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003893](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003893) | mouse | Tumor tissue | 47 | LC-MS | 2025-05-06 | Respiration defects limit serine synthesis required for lung cancer g… |
| [ST003950](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003950) | human | Blood | 78 | LC-MS | 2025-07-07 | Plasma Phospholipids Analysis in Thai EGFR-mutated Non-Small Cell Lun… |
| [ST003989](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003989) | human | Blood | 78 | GC-MS | 2025-07-07 | Plasma Amino Acids Analysis in Thai EGFR-mutated Non-Small Cell Lung … |
| [ST004109](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004109) | mouse | Blood | 11 | LC-MS | 2025-09-01 | Early adipose tissue wasting in a preclinical model of human lung can… |
| [ST004177](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004177) | human | Blood | 78 | GC-MS | 2025-09-16 | Plasma Organic acids Analysis in Thai EGFR-mutated Non-Small Cell Lun… |
| [ST004182](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004182) | mouse | Cultured cells | 20 | LC-MS | 2025-09-28 | Metabolomics of ASCL1-high and ASCL1-low SCLC cells in mouse models |
| [ST004184](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004184) | human | Blood | 78 | GC-MS | 2025-10-06 | Plasma Sugar and Sugar Alcohols Analysis in Thai EGFR-mutated Non-Sma… |
| [ST004203](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004203) | mouse | Tumor cells | 6 | LC-MS | 2025-10-10 | Cell state-specific metabolic networks govern ferroptosis versus apop… |
| [ST004220](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004220) | human | Lung Tumors | 12 | LC-MS | 2026-03-23 | Untargeted Metabolomics of NCI-H1299 Cells Transfected with siRNA Tar… |
| [ST004221](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004221) | human | Lung Tumors | 13 | LC-MS | 2026-03-23 | Targeted Detection of Cystathionine in NCI-H1299 Cells Transfected wi… |
| [ST004225](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004225) | human | Lung Tumors | 13 | LC-MS | 2026-03-23 | Targeted Detection of Cholesterol, Lanosterol, 7-Dehydrocholesterol a… |
| [ST004253](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004253) | human | Lung Tumors | 13 | LC-MS | 2026-03-23 | Targeted Detection of S-Adenosylmethionine and S-Adenosylhomocysteine… |
| [ST004375](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004375) | human | Cultured cells | 20 | LC-MS | 2026-03-02 | Dihydroorotate dehydrogenase (DHODH) promotes radioresistance in Lung… |
| [ST004447](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004447) | human | Cultured cells | 18 | LC-MS | 2025-12-22 | Determine the impact of serum modulation to lipid homeostasis in a no… |
| [ST004449](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004449) | human | Cultured cells | 12 | LC-MS | 2025-12-22 | Compare lipid homeostasis in two distinct non-small cell lung cancer … |
| [ST004457](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004457) | mouse | Lung Tumors | 48 | LC-MS | 2025-12-22 | Compare lipid metabolism in lung tumors from mice harboring Kras G12D… |
| [ST004458](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004458) | human | Cultured cells | 12 | LC-MS | 2025-12-22 | Determine the effect of a moderate dose of fumonisin B1 to the lipido… |
| [ST004818](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004818) | human | Blood | 84 | LC-MS | 2026-05-11 | Whole Blood Metabolomics Reveals Coordinated Redox-One-Carbon Axis Di… |
| [ST004975](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004975) | human | Blood | 2268 | MS(Dir. Inf.) | 2026-07-01 | A high-resolution circulating metabolic atlas of lung adenocarcinoma … |
| [ST005097](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST005097) | mouse | Tumor cells | 16 | LC-MS | 2026-08-16 | Dietary α‑Ketoglutarate Modulates Lung Adenocarcinoma Growth and Epig… |

## Appendix B &mdash; every cancer study matching an exercise-side keyword, adjudicated

| Study | MW disease | Matched term | Verdict |
|---|---|---|---|
| [ST000385](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000385) | Cancer | training | Homonym &mdash; "training set" is a machine-learning split |
| [ST001005](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001005) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001006](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001006) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001009](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001009) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001010](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001010) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001011](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001011) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001012](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001012) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001013](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001013) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001014](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001014) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001015](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001015) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001016](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001016) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001017](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001017) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001018](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001018) | Cachexia/Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST001467](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001467) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002183](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002183) | Multiple myeloma | exercise | **Genuine** &mdash; randomised exercise vs waitlist arms |
| [ST002824](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002824) | Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002842](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002842) | Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002843](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002843) | Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002881](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002881) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002882](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002882) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002883](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002883) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002884](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002884) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002885](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002885) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002886](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002886) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002887](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002887) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002888](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002888) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002889](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002889) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST002904](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002904) | Cachexia | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST003919](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003919) | Cancer/Colitis | aerobic | Homonym &mdash; keyword match on unrelated text |
| [ST004109](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004109) | Cancer | cachexia | Cachexia &mdash; wasting phenotype, not an activity exposure |
| [ST004582](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004582) | Cancer | fitness | Homonym &mdash; "fitness" means cellular fitness under hypoxia |

False positives found independently by a verification agent over the same set and confirmed here: [ST002010](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002010) (`Chemoresistance Status:Resistant`), [ST004922](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004922) (`Palbociclib resistance:Sensitive`), [ST000248](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000248) (`Cell population:Fast-cycling cells`).

## Appendix C &mdash; every prose hit in the 798-study cancer prose sweep, adjudicated

| Study | MW disease | Term | Verdict |
|---|---|---|---|
| [ST002183](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002183) | Multiple myeloma | exercise, cardiorespiratory | **Genuine** &mdash; randomised exercise intervention |
| [ST004161](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004161) | Cancer | physical function | **Genuine** &mdash; handgrip strength, stair-climb power, CT muscle CSA; not deposited |
| [ST004166](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004166) | Cancer | physical function | **Genuine** &mdash; same measures, muscle biopsy arm; not deposited |
| [ST002163](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002163) | Cancer | wheel-running | **Genuine** &mdash; voluntary wheel-running activity in tumour-bearing mice; not deposited |
| [ST002167](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002167) | Cancer | wheel-running | Shared abstract &mdash; this arm is AML12 cell culture, not the mouse study |
| [ST003315](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003315) | Cancer | ECOG | Eligibility criterion (ECOG PS &le;2), not a measured variable |
| [ST001237](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001237) | Cancer | performance status | Embedded in the composite `CRF_MSKCC_Risk_Group`, not deposited separately |

## Appendix D &mdash; all 35 corpus-wide exercise-factor studies

Context for the headline: these are every study in MW, in any disease area, whose deposited factors mention an exercise term. Exactly one is a cancer study.

| Study | MW disease | Matched term | Title |
|---|---|---|---|
| [ST000161](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000161) | not annotated | exercis | Plasma Nucleotide/adenosine concentrations (Human AxP Batch 3) |
| [ST000283](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000283) | not annotated | exercis | Plasma Nucleotide/adenosine concentrations (Human AxP Batch 4) |
| [ST000315](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000315) | Obesity | exercis | Metabolomics and Childhood Obesity: A Pilot and Feasibility Stu… |
| [ST000387](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000387) | not annotated | exercis | Changes in the metabalome and lipidome in response to exercise … |
| [ST000640](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000640) | Diabetes | exercis | Targeted NEFA in American Indian Adolescents (part I) |
| [ST000641](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000641) | Diabetes | exercis | Targeted Amino Acids in American Indian Adolescents (part II) |
| [ST000645](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000645) | Muscular dystrophy | sedentary | Effects of Exercise on Dystrophic Mouse Muscle Amino Acids (par… |
| [ST000646](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000646) | Muscular dystrophy | sedentary | Effects of Exercise on Dystrophic Mouse Muscle TCA Cycle (part … |
| [ST000647](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000647) | Muscular dystrophy | sedentary | Effects of Exercise on Dystrophic Mouse Muscle Non-Esterified F… |
| [ST000648](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000648) | Muscular dystrophy | sedentary | Effects of NO Donor Therapy on the Dystrophic Mouse Muscle Amin… |
| [ST000649](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000649) | Muscular dystrophy | sedentary | Effects of NO Donor Therapy on the Dystrophic Mouse Muscle Non-… |
| [ST000650](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000650) | Muscular dystrophy | sedentary | Effects of NO Donor Therapy on the Dystrophic Mouse Muscle TCA … |
| [ST000671](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000671) | not annotated | exercis | LCR/HCR rat mitochondrial study |
| [ST000710](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000710) | not annotated | sedentary | Influence of excercise and antiobitic on fecal SCFA |
| [ST000762](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000762) | Scleroderma | exercis | Plasma Nucleotide/adenosine concentrations in patiens with scle… |
| [ST000763](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000763) | Scleroderma | exercis | Untargeted metabolomics and lipidomics of scleroderma PAH disco… |
| [ST000777](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000777) | Obesity | exercis | Metabolic Adaptations to Chronic and Acute Exercise in Overweig… |
| [ST000897](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST000897) | Heart injury | exercis, sedentary | Untargeted metabolomics analysis of ischemia-reperfusion injure… |
| [ST001068](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001068) | not annotated | treadmill | The proteomic and metabolomic characterization of exercise-indu… |
| [ST001070](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001070) | not annotated | treadmill | The global proteomic characterization of exercise-induced sweat… |
| [ST001251](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001251) | Endotoxemia | trained | The effects of a training program encompassing cold exposure, b… |
| [ST001492](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001492) | not annotated | immobiliz | Global metabolomics of IFNy cued neurogenic NSCs seeded on hydr… |
| [ST001745](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001745) | not annotated | trained | Metabolomic profiling of the rat hippocampus across development… |
| [ST001749](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST001749) | Alzheimers disease | physical activity | REACH Metabolomics Study |
| [ST002081](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002081) | not annotated | exercis | Dynamic Lipidome Alterations Associated with Human Health, Dise… |
| [ST002183](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002183) | Multiple myeloma | exercis | Individualized exercise intervention for people with multiple m… **&larr; the cancer study** |
| [ST002931](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002931) | not annotated | sedentary | Analyzing Metabolic Alterations in the Gut, Blood, and Brain of… |
| [ST002938](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST002938) | Atrial fibrillation | athlet | Role of PI3K in Atrial Myopathy: Insights from Transgenic Mouse… |
| [ST003686](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003686) | Cardiovascular disease | exercis | Characterization of the transpulmonary metabolome at the inters… |
| [ST003721](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003721) | not annotated | immobiliz | Metabolomic analysis of skeletal muscle from control, immobiliz… |
| [ST003722](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003722) | Muscle atrophy | immobiliz | Metabolomic analysis of plasma from control, immobilized and Fo… |
| [ST003724](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003724) | Muscle atrophy | immobiliz | Metabolomic analysis of skeletal muscle from control WT, immobi… |
| [ST003807](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST003807) | Diabetes | exercis | A lipidomic exploration of the effects of high-intensity interv… |
| [ST004061](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004061) | not annotated | trained | In Vitro Method Demonstrating Trained Immunity as a Distinctive… |
| [ST004721](https://www.metabolomicsworkbench.org/data/DRCCMetadata.php?Mode=Study&StudyID=ST004721) | not annotated | exercis | High relevance of fatty acid oxidation in a migrating mammal, t… |

