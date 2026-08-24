# Literature Evidence Report — N-Lactoyl phenylalanine

Screening and appraisal of retrieved bibliographic records. Retrieval provenance is preserved per
source; screening flags state whether they came from a structured field or from title/abstract text.
No relevance, quality, or replication claim is made from a bibliographic hit alone.

## Query

- Query: `N-Lactoyl phenylalanine`
- Name variants searched: Lac-Phe, N-lactoylphenylalanine, lactoylphenylalanine, N-lactoyl-phenylalanine
- Context terms: none
- Records after cross-source deduplication: 375
- Records requiring human review: 325

## Retrieval provenance

| source | status | reported hits | retrieved | complete sweep | detail |
| --- | --- | --- | --- | --- | --- |
| europe_pmc | ok | 306 | 304 | yes | index reported 306 hits but returned 304 records across all pages; the difference is unexplained by the index and the shortfall is not a screening decision |
| pubmed | unavailable | unknown | 0 | no | literature request returned non-JSON content: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=%28%22N-Lactoyl+phenylalanine%22%5BAll+Fields%5D+OR+%22Lac-Phe%22%5BAll+Fields%… |
| crossref | ok | 47,194 | 160 | no | query.bibliographic is a ranked relevance query: reported_hit_count is the summed size of the candidate pools Crossref scored across the variant queries, not a count of publications about the subject… |
| biorxiv_medrxiv | ok | 6 | 6 | yes |  |


### Retrieval gaps

- **pubmed was unreachable.** Its coverage for this query is unknown. This is an availability gap, not a finding that no matching publication exists.
- **crossref returned a ranked sample, not a complete sweep.** Absence of a paper from the table below is not evidence that it does not exist.

## Screening classes

| screen class | records |
| --- | --- |
| animal_or_invitro_mechanistic | 39 |
| direct_human_exercise | 30 |
| human_non_exercise_context | 66 |
| not_primary_evidence | 4 |
| screening_uncertain_insufficient_text | 142 |
| secondary_synthesis | 94 |


## Evidence tiers

| evidence tier | records |
| --- | --- |
| editorial_or_commentary | 2 |
| peer_reviewed_primary | 221 |
| peer_reviewed_secondary_synthesis | 109 |
| preprint_not_peer_reviewed | 9 |
| retracted_or_retraction_notice | 2 |
| unknown_publication_type | 32 |


## Species scope of the retrieved evidence

| species scope | records |
| --- | --- |
| human | 110 |
| human_and_animal | 29 |
| in_vitro_or_enzymatic | 7 |
| not_stated_in_retrieved_text | 196 |
| other_animal | 2 |
| rodent | 31 |


Species scope is inferred from retrieved title and abstract text unless the basis column says
`structured_field`. `not_stated_in_retrieved_text` means the text carried no species term; it does not
mean the study had no species.

## Subject-name evidence and homonym risk

Declared subject terms: N-Lactoyl phenylalanine, Lac-Phe, N-lactoylphenylalanine, lactoylphenylalanine, N-lactoyl-phenylalanine

| subject-name evidence | records |
| --- | --- |
| subject_name_absent_from_title_and_abstract | 220 |
| subject_name_in_abstract | 39 |
| subject_name_in_title | 61 |
| unknown_no_abstract_retrieved | 55 |

| homonym risk | records |
| --- | --- |
| mixed_material_and_biological_context | 5 |
| no_homonym_signal | 95 |
| not_assessed_subject_name_not_located | 275 |


A record matched by a full-text index whose retrieved title and abstract never name the queried subject
cannot be confirmed as subject evidence from the record alone. Where the name appears only alongside
materials-science context terms, the string may denote a different chemical entity that shares the
abbreviation; those records are escalated rather than counted as subject evidence.

| homonym risk | year | title | journal | url |
| --- | --- | --- | --- | --- |
| mixed_material_and_biological_context | 2023 | Distinct microRNA and protein profiles of extracellular vesicles secreted from myotubes from morbidly obese donors with type 2 diabetes in response to electrical pulse stimulation | Frontiers in physiology | https://europepmc.org/article/MED/37064893 |
| mixed_material_and_biological_context | 2025 | Exercise-induced Metabolite N-lactoyl-phenylalanine Ameliorates Colitis by Inhibiting M1 Macrophage Polarization via the Suppression of the NF-κB Signaling Pathway | Cellular and molecular gastroenterology and hepatology | https://europepmc.org/article/MED/40562095 |
| mixed_material_and_biological_context | 2026 | Lac-Phe: An Exercise Induced Metabolite with Immunomodulatory Potential in Inflammatory Diseases | International Journal of Immunology and Immunotherapy | https://doi.org/10.23937/2378-3672/1410077 |
| mixed_material_and_biological_context | 2025 | Bilayer Scaffolds Synergize Immunomodulation and Rejuvenation via Layer-Specific Release of CK2.1 and the "Exercise Hormone" Lac-Phe for Enhanced Osteochondral Regeneration | Advanced healthcare materials | https://europepmc.org/article/MED/39529517 |
| mixed_material_and_biological_context | 2026 | Practical Synthesis of N-Lactoyl-Phenylalanine and Its Isotopically Deuterated Variant Lac-Phe-d5 | Letters in Organic Chemistry | https://doi.org/10.2174/0115701786492436260617164313 |


## Direct human exercise records

| year | title | journal | tier | species | design | accessions | review | url |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | An exercise-inducible metabolite that suppresses feeding and obesity | Nature | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/35705806 |
| 2015 | N-lactoyl-amino acids are ubiquitous metabolites that originate from CNDP2-mediated reverse proteolysis of lactate and amino acids | Proceedings of the National Academy of Sciences of the United States of America | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/25964343 |
| 2022 | Exercise-Induced N-Lactoylphenylalanine Predicts Adipose Tissue Loss during Endurance Training in Overweight and Obese Humans | Metabolites | peer_reviewed_primary | human_and_animal | interventional_exercise_bout_or_program | none in retrieved text | requires_human_review | https://doi.org/10.3390/metabo13010015 |
| 2025 | Exercise intensity determines circulating levels of Lac-Phe and other exerkines: a randomized crossover trial | Metabolomics | peer_reviewed_primary | human | randomized_controlled_trial | none in retrieved text | requires_human_review | https://doi.org/10.1007/s11306-025-02260-0 |
| 2023 | Plasma Proteomic Kinetics in Response to Acute Exercise | Molecular & cellular proteomics : MCP | peer_reviewed_primary | human | interventional_exercise_bout_or_program | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37343698 |
| 2023 | Distinct microRNA and protein profiles of extracellular vesicles secreted from myotubes from morbidly obese donors with type 2 diabetes in response to electrical pulse stimulation | Frontiers in physiology | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37064893 |
| 2023 | The effect of blood flow restriction exercise on N-lactoylphenylalanine and appetite regulation in obese adults: a cross-design study | Frontiers in Endocrinology | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://doi.org/10.3389/fendo.2023.1289574 |
| 2024 | SLC17A1/3 transporters mediate renal excretion of Lac-Phe in mice and humans | Nature communications | peer_reviewed_primary | human_and_animal | preclinical_experiment | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/39134528 |
| 2025 | Exercise-induced Metabolite N-lactoyl-phenylalanine Ameliorates Colitis by Inhibiting M1 Macrophage Polarization via the Suppression of the NF-κB Signaling Pathway | Cellular and molecular gastroenterology and hepatology | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/40562095 |
| 2023 | Trans-10, cis-12 conjugated linoleic acid- and caloric restriction-mediated upregulation of CNDP2 expression in white adipose tissue in rodents, with implications in feeding and obesity | The Journal of nutritional biochemistry | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/36641073 |
| 2025 | Lac-Phe induces hypophagia by inhibiting AgRP neurons in mice | Nature metabolism | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/40957996 |
| 2025 | N-Lactoyl amino acids as metabolic biomarkers differentiating low and high exercise response | Biology of sport | peer_reviewed_primary | human | interventional_exercise_bout_or_program | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/40182705 |
| 2025 | Association between physical activity, trouble sleeping, and obesity among older Americans: a cross-sectional study based on NHANES data from 2007 to 2018 | BMC geriatrics | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/40069615 |
| 2025 | Sexual dimorphism in the serum metabolome following acute exhaustive exercise | Biology of sex differences | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/41199406 |
| 2025 | Maternal Physical Activity and Its Relationship to the Human Milk Metabolome and Infant Body Composition | The Journal of clinical endocrinology and metabolism | peer_reviewed_primary | human | interventional_exercise_bout_or_program | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/40417941 |
| 2025 | Gut lactate increases circulating l-Lac-Phe and key metabolites linked to GLP-1 and human health | American journal of physiology. Endocrinology and metabolism | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/40418349 |
| 2025 | Proof-of-concept of a prior validated LC-MS/MS method for detection of N-lactoyl-phenylalanine in dried blood spots before, during and after a performance diagnostic test of junior squad triathletes | Frontiers in Sports and Active Living | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://doi.org/10.3389/fspor.2025.1600714 |
| 2025 | Dynamic Metabolic Changes Driven by Exercise Intensity in Acute Swimming | Medicine and science in sports and exercise | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/40601479 |
| 2023 | Responsiveness to endurance training can be partly explained by the number of favorable single nucleotide polymorphisms an individual possesses | PloS one | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37471354 |
| 2026 | The anti-obesogenic metabolite, Lac-Phe, is elevated by metformin treatment in prostate cancer patients | EMBO molecular medicine | peer_reviewed_primary | human | randomized_controlled_trial | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/41942753 |
| 2026 | The effect of blood flow restriction training on abdominal visceral fat and plasma N-lactoylphenylalanine among adults with obesity | BMC Endocrine Disorders | peer_reviewed_primary | human | interventional_exercise_bout_or_program | none in retrieved text | requires_human_review | https://doi.org/10.1186/s12902-026-02441-5 |
| 2026 | Characterizing Human Oxidative, Anabolic and Glycolytic Metabolism in Athletes with Extreme Physiologies | Sports medicine - open | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/41801539 |
| 2026 | Lac-Phe: An Exercise Induced Metabolite with Immunomodulatory Potential in Inflammatory Diseases | International Journal of Immunology and Immunotherapy | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://doi.org/10.23937/2378-3672/1410077 |
| 2026 | The Emerging Role of N-Lactoyl-Phenylalanine (Lac-Phe) in Metabolic Regulation and Disease: From Exercise-Induced Metabolite to Therapeutic Candidate | Antioxidants | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://doi.org/10.3390/antiox15040441 |
| 2026 | Exercise-induced N-lactoyl-phenylalanine and its potential role in appetite regulation and obesity | Archiv Euromedica | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | requires_human_review | https://doi.org/10.35630/2026/16/iss.1.003 |


## Human, non-exercise context

| year | title | journal | tier | species | design | accessions | review | url |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2021 | Circulating markers of NADH-reductive stress correlate with mitochondrial disease severity | The Journal of clinical investigation | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/33463549 |
| 1985 | Two modes of control of pilA, the gene encoding type 1 pilin in Escherichia coli | Journal of bacteriology | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/3930469 |
| 2024 | Metformin and feeding increase levels of the appetite-suppressing metabolite Lac-Phe in humans | Nature Metabolism | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | advisory_only | https://doi.org/10.1038/s42255-024-01018-7 |
| 2007 | Inflammatory multiple-sclerosis plaques generate characteristic metabolic profiles in cerebrospinal fluid | PloS one | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/17611627 |
| 2024 | Lac-Phe mediates the effects of metformin on food intake and body weight | Nature metabolism | peer_reviewed_primary | human_and_animal | observational_cohort_or_cross_sectional | none in retrieved text | advisory_only | https://europepmc.org/article/MED/38499766 |
| 2025 | A β-hydroxybutyrate shunt pathway generates anti-obesity ketone metabolites | Cell | peer_reviewed_primary | human_and_animal | preclinical_experiment | none in retrieved text | advisory_only | https://europepmc.org/article/MED/39536746 |
| 2015 | ATP-binding Cassette Subfamily C Member 5 (ABCC5) Functions as an Efflux Transporter of Glutamate Conjugates and Analogs | The Journal of biological chemistry | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/26515061 |
| 2021 | Metabolomic Profiling of Aqueous Humor and Plasma in Primary Open Angle Glaucoma Patients Points Towards Novel Diagnostic and Therapeutic Strategy | Frontiers in pharmacology | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/33935712 |
| 2023 | Precise Metabolomics Defines Systemic Metabolic Dysregulation Distinct to Acute Myocardial Infarction Associated With Diabetes | Arteriosclerosis, thrombosis, and vascular biology | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/36727520 |
| 2023 | Metabolites as Risk Factors for Diabetic Retinopathy in Patients With Type 2 Diabetes: A 12-Year Follow-up Study | The Journal of clinical endocrinology and metabolism | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | advisory_only | https://europepmc.org/article/MED/37560996 |
| 2019 | Untargeted Metabolomics-Based Screening Method for Inborn Errors of Metabolism using Semi-Automatic Sample Preparation with an UHPLC- Orbitrap-MS Platform | Metabolites | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/31779119 |
| 2024 | Circulating N-lactoyl-amino acids and N-formyl-methionine reflect mitochondrial dysfunction and predict mortality in septic shock | Metabolomics : Official journal of the Metabolomic Society | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/38446263 |
| 2019 | Metabolomic Studies of Tissue Injury in Nonhuman Primates Exposed to Gamma-Radiation | International journal of molecular sciences | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/31323921 |
| 2024 | Role of human plasma metabolites in prediabetes and type 2 diabetes from the IMI-DIRECT study | Diabetologia | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/39349772 |
| 2024 | Metformin improves HPRT1-targeted purine metabolism and repairs NR4A1-mediated autophagic flux by modulating FoxO1 nucleocytoplasmic shuttling to treat postmenopausal osteoporosis | Cell death & disease | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/39500875 |
| 2023 | Genomic and metabonomic methods reveal the probiotic functions of swine-derived Ligilactobacillus salivarius | BMC microbiology | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/37648978 |
| 2022 | Targeted Metabolomics Shows That the Level of Glutamine, Kynurenine, Acyl-Carnitines and Lysophosphatidylcholines Is Significantly Increased in the Aqueous Humor of Glaucoma Patients | Frontiers in medicine | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/35935793 |
| 2019 | Neural State Monitoring in the Treatment of Epilepsy: Seizure Prediction-Conceptualization to First-In-Man Study | Brain sciences | peer_reviewed_primary | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/31266223 |
| 2024 | The clinical relevance of novel biomarkers as outcome parameter in adults with phenylketonuria | Journal of inherited metabolic disease | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | advisory_only | https://europepmc.org/article/MED/38556470 |
| 2023 | Altered plasma metabolite levels can be detected years before a glioma diagnosis | JCI insight | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37651185 |
| 2021 | Metabolomic Analysis Uncovers Energy Supply Disturbance as an Underlying Mechanism of the Development of Alcohol-Associated Liver Cirrhosis | Hepatology communications | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/34141983 |
| 2024 | Ten metabolites-based algorithm predicts the future development of type 2 diabetes in Chinese | Journal of advanced research | peer_reviewed_primary | human | observational_cohort_or_cross_sectional | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/38030128 |
| 2022 | Untargeted plasma metabolomic fingerprinting highlights several biomarkers for the diagnosis and prognosis of coronavirus disease 19 | Frontiers in medicine | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/36250098 |
| 2020 | Using Out-of-Batch Reference Populations to Improve Untargeted Metabolomics for Screening Inborn Errors of Metabolism | Metabolites | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/33375624 |
| 2024 | Enhanced interactions among gut mycobiomes with the deterioration of glycemic control | Med (New York, N.Y.) | peer_reviewed_primary | human | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/38670112 |


## Animal or in-vitro mechanistic background

Retained as mechanistic background. These records never satisfy a human required term.

| year | title | journal | tier | species | design | accessions | review | url |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1980 | In vitro gene fusions that join an enzymatically active beta-galactosidase segment to amino-terminal fragments of exogenous proteins: Escherichia coli plasmid vectors for the detection and cloning of translational initiation signals | Journal of bacteriology | peer_reviewed_primary | in_vitro_or_enzymatic | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/6162838 |
| 1981 | Cloning and analysis of strong promoters is made possible by the downstream placement of a RNA termination signal | Proceedings of the National Academy of Sciences of the United States of America | peer_reviewed_primary | in_vitro_or_enzymatic | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/6946440 |
| 2023 | Organism-wide, cell-type-specific secretome mapping of exercise training in mice | Cell metabolism | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37141889 |
| 1991 | Isolation and characterization of Escherichia coli mutants with altered rates of deletion formation | Genetics | peer_reviewed_primary | in_vitro_or_enzymatic | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/2016043 |
| 2024 | Metformin targets mitochondrial complex I to lower blood glucose levels | Science advances | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/39693440 |
| 2023 | High-intensity interval training induces lactylation of fatty acid synthase to inhibit lipid synthesis | BMC biology | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37726733 |
| 2022 | Phyllanthus emblica aqueous extract retards hepatic steatosis and fibrosis in NAFLD mice in association with the reshaping of intestinal microecology | Frontiers in pharmacology | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/35959433 |
| 2025 | Cooperative nutrient scavenging is an evolutionary advantage in cancer | Nature | peer_reviewed_primary | in_vitro_or_enzymatic | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/39972131 |
| 2018 | Improving in vivo conversion of oleuropein into hydroxytyrosol by oral granules containing probiotic Lactobacillus plantarum 299v and an Olea europaea standardized extract | International journal of pharmaceutics | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/29526619 |
| 2022 | UCP2-dependent redox sensing in POMC neurons regulates feeding | Cell reports | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/36577374 |
| 2021 | Lactoyl leucine and isoleucine are bioavailable alternatives for canonical amino acids in cell culture media | Biotechnology and bioengineering | peer_reviewed_primary | in_vitro_or_enzymatic | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/33738790 |
| 2025 | N-Lactoyl-Phenylalanine modulates lipid metabolism in microglia/macrophage via the AMPK-PGC1α-PPARγ pathway to promote recovery in mice with spinal cord injury | Journal of neuroinflammation | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/40579710 |
| 1983 | Physical mapping of the exuT and uxaC operators by use of exu plasmids and generation of deletion mutants in vitro | Journal of bacteriology | peer_reviewed_primary | in_vitro_or_enzymatic | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/6309752 |
| 2024 | Exercise mitigates flow recirculation and activates metabolic transducer SCD1 to catalyze vascular protective metabolites | Science advances | peer_reviewed_primary | rodent | preclinical_experiment | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/38354249 |
| 2022 | Serum and brain metabolomic study reveals the protective effects of Bai-Mi-Decoction on rats with ischemic stroke | Frontiers in pharmacology | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/36506507 |
| 2020 | Urine metabolomics of rats with chronic atrophic gastritis | PloS one | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/33175875 |
| 2024 | Gegen Qinlian decoction alleviates depression-like behavior by modulating the gut microenvironment in CUMS rats | BMC complementary medicine and therapies | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/39304871 |
| 2022 | Shenkang Injection for Treating Renal Fibrosis-Metabonomics and Regulation of E3 Ubiquitin Ligase Smurfs on TGF-β/Smads Signal Transduction | Frontiers in pharmacology | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/35721120 |
| 2024 | Preparation and Preclinical Characterization of a Simple Ester for Dual Exogenous Supply of Lactate and Beta-hydroxybutyrate | Journal of agricultural and food chemistry | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/39214666 |
| 2024 | High-intensity interval training or lactate administration combined with aerobic training enhances visceral fat loss while promoting VMH neuroplasticity in female rats | Lipids in health and disease | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/39696579 |
| 2021 | Metabolomic profiling of plasma from middle-aged and advanced-age male mice reveals the metabolic abnormalities of carnitine biosynthesis in metallothionein gene knockout mice | Aging | peer_reviewed_primary | rodent | preclinical_experiment | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/34851303 |
| 2025 | High-Calorie Diet Consumption Induces Lac-Phe Changes in the Brain in a Time-of-Day Manner Independent of Exercise | Metabolites | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/40559399 |
| 2024 | Transgenic female mice producing trans 10, cis 12-conjugated linoleic acid present excessive prostaglandin E2, adrenaline, corticosterone, glucagon, and FGF21 | Scientific reports | peer_reviewed_primary | rodent | preclinical_experiment | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/38816541 |
| 2025 | Integrating network pharmacology, quantitative transcriptomic analysis, and experimental validation revealed the mechanism of cordycepin in the treatment of obesity | Frontiers in pharmacology | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/40438591 |
| 2025 | N-Lactoyl Phenylalanine Disrupts Insulin Signaling, Induces Inflammation, and Impairs Mitochondrial Respiration in Cell Models | Cells | peer_reviewed_primary | rodent | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://doi.org/10.3390/cells14161296 |


## Secondary synthesis (reviews, meta-analyses)

| year | title | journal | tier | species | design | accessions | review | url |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1993 | The complete general secretory pathway in gram-negative bacteria | Microbiological reviews | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/8096622 |
| 2023 | Multi-Omics Profiling for Health | Molecular & cellular proteomics : MCP | peer_reviewed_secondary_synthesis | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37119971 |
| 2023 | Exercise metabolism and adaptation in skeletal muscle | Nature reviews. Molecular cell biology | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | interventional_exercise_bout_or_program | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37225892 |
| 2023 | The role of efferocytosis-fueled macrophage metabolism in the resolution of inflammation | Immunological reviews | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37158427 |
| 2023 | Lactate as a myokine and exerkine: drivers and signals of physiology and metabolism | Journal of applied physiology (Bethesda, Md. : 1985) | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/36633863 |
| 2023 | Sarcopenia and Cognitive Decline in Older Adults: Targeting the Muscle-Brain Axis | Nutrients | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37111070 |
| 2023 | Gut commensals and their metabolites in health and disease | Frontiers in microbiology | peer_reviewed_secondary_synthesis | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/38029089 |
| 2023 | Role of diet and exercise in aging, Alzheimer's disease, and other chronic diseases | Ageing research reviews | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37832608 |
| 2022 | Role of brain-gut-muscle axis in human health and energy homeostasis | Frontiers in nutrition | peer_reviewed_secondary_synthesis | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/36276808 |
| 2025 | Solute carriers: The gatekeepers of metabolism | Cell | peer_reviewed_secondary_synthesis | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/39983672 |
| 2024 | Methylmalonic acid in aging and disease | Trends in endocrinology and metabolism: TEM | peer_reviewed_secondary_synthesis | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/38030482 |
| 2012 | Involvement of the ligninolytic system of white-rot and litter-decomposing fungi in the degradation of polycyclic aromatic hydrocarbons | Biotechnology research international | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/22830035 |
| 2023 | Phyllanthus emblica : a comprehensive review of its phytochemical composition and pharmacological properties | Frontiers in pharmacology | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37954853 |
| 2025 | Wearables in Chronomedicine and Interpretation of Circadian Health | Diagnostics (Basel, Switzerland) | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/39941257 |
| 2024 | Molecular insights of exercise therapy in disease prevention and treatment | Signal transduction and targeted therapy | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/38806473 |
| 2020 | A Public Health Issue: Dietary Supplements Promoted for Brain Health and Cognitive Performance | Journal of alternative and complementary medicine (New York, N.Y.) | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/32119795 |
| 2016 | Evaluation of Cancer Metabolomics Using ex vivo High Resolution Magic Angle Spinning (HRMAS) Magnetic Resonance Spectroscopy (MRS) | Metabolites | peer_reviewed_secondary_synthesis | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/27011205 |
| 2024 | Lipotoxicity as a therapeutic target in obesity and diabetic cardiomyopathy | Journal of pharmacy & pharmaceutical sciences : a publication of the Canadian Society for Pharmaceutical Sciences, Societe canadienne des sciences pharmaceutiques | peer_reviewed_secondary_synthesis | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/38706718 |
| 2023 | Exercise-induced hypothalamic neuroplasticity: Implications for energy and glucose metabolism | Molecular metabolism | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37268247 |
| 2023 | New insight of metabolomics in ocular diseases in the context of 3P medicine | The EPMA journal | peer_reviewed_secondary_synthesis | human | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/36866159 |
| 2023 | Exerkines and redox homeostasis | Redox biology | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37247469 |
| 2021 | Metabolomics in Retinal Diseases: An Update | Biology | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/34681043 |
| 2023 | Adipocyte- and Monocyte-Mediated Vicious Circle of Inflammation and Obesity (Review of Cellular and Molecular Mechanisms) | International journal of molecular sciences | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/37569635 |
| 2025 | Metabolomics in cardiometabolic diseases: Key biomarkers and therapeutic implications for insulin resistance and diabetes | Journal of internal medicine | peer_reviewed_secondary_synthesis | human | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/40289598 |
| 2024 | Exercise-induced appetite suppression: An update on potential mechanisms | Physiological reports | peer_reviewed_secondary_synthesis | human_and_animal | not_stated_in_retrieved_text | none in retrieved text | advisory_only | https://europepmc.org/article/MED/39187396 |


## Unscreenable records

Retrieved records that could not be screened: either no abstract was returned, or the abstract names no
species and carries no decisive modality signal. The `screen_basis` column in the screened CSV gives the
reason per record. These are unresolved, not excluded.

| year | title | journal | tier | species | design | accessions | review | url |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1979 | Lactose genes fused to exogenous promoters in one step using a Mu-lac bacteriophage: in vivo probe for transcriptional control sequences | Proceedings of the National Academy of Sciences of the United States of America | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/159458 |
| 1988 | A mutation affecting the regulation of a secA-lacZ fusion defines a new sec gene | Genetics | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/3284784 |
| 2002 | Replication fork collapse at replication terminator sequences | The EMBO journal | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/12110601 |
| 1992 | Autogenous regulation of ethanolamine utilization by a transcriptional activator of the eut operon in Salmonella typhimurium | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/1328159 |
| 1980 | Conjugal transfer of genetic information in group N streptococci | Applied and environmental microbiology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/6773476 |
| 1991 | Fnr mutants that activate gene expression in the presence of oxygen | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/1898918 |
| 2022 | Preparation and Taste Characteristics of Kokumi N -Lactoyl Phenylalanine in the Presence of Phenylalanine and Lactate | Journal of Agricultural and Food Chemistry | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://doi.org/10.1021/acs.jafc.2c00530 |
| 1991 | Neuropeptides Gly-Asp-Pro-Phe-Leu-Arg-Phe-amide (GDPFLRFamide) and Ser- Asp-Pro-Phe-Leu-Arg-Phe-amide (SDPFLRFamide) are encoded by an exon 3' to Phe-Met-Arg-Phe-NH2 (FMRFamide) in the snail Lymnaea stagnalis | The Journal of Neuroscience | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://doi.org/10.1523/jneurosci.11-03-00740.1991 |
| 1993 | A genetic analysis of various functions of the TyrR protein of Escherichia coli | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/8449883 |
| 1981 | Use of bacteriophage transposon Mu d1 to determine the orientation for three proC-linked phosphate-starvation-inducible (psi) genes in Escherichia coli K-12 | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/6260750 |
| 1981 | General method, using Mu-Mud1 dilysogens, to determine the direction of transcription of and generate deletions in the glnA region of Escherichia coli | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/6111550 |
| 1979 | Genetics and regulation of D-xylose utilization in Salmonella typhimurium LT2 | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/222732 |
| 1991 | Mutational analysis of nitrate regulatory gene narL in Escherichia coli K-12 | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/2066339 |
| 1985 | Natural history of restricted synthesis and expression of measles virus genes in subacute sclerosing panencephalitis | Proceedings of the National Academy of Sciences of the United States of America | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/3857631 |
| 1980 | Isolation of ara-lac gene fusions in Salmonella typhimurium LT2 by using transducing bacteriophage Mu d (Apr lac) | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/6773928 |
| 2022 | Integrated Fecal Microbiome and Metabolomics Reveals a Novel Potential Biomarker for Predicting Tibial Dyschondroplasia in Chickens | Frontiers in physiology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/35634144 |
| 2022 | Root exudates and rhizosphere soil bacterial relationships of Nitraria tangutorum are linked to k-strategists bacterial community under salt stress | Frontiers in plant science | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/36119572 |
| 1989 | Recombination between homologies in direct and inverse orientation in the chromosome of Salmonella: intervals which are nonpermissive for inversion formation | Genetics | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/2547692 |
| 1982 | Regulation of adenylate cyclase synthesis in Escherichia coli: studies with cya-lac operon and protein fusion strains | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/6286596 |
| 2022 | Systematic review of preterm birth multi-omic biomarker studies | Expert reviews in molecular medicine | peer_reviewed_secondary_synthesis | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/35379367 |
| 1987 | Isomerization of 6-Lactoyl Tetraliydropterin by Sepiapterin Reductase1 | The Journal of Biochemistry | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://doi.org/10.1093/oxfordjournals.jbchem.a121901 |
| 1981 | Alternate pathways of DNA replication: DNA polymerase I-dependent replication | Proceedings of the National Academy of Sciences of the United States of America | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/7031666 |
| 1992 | Amino acid substitutions in the CytR repressor which alter its capacity to regulate gene expression | Journal of bacteriology | peer_reviewed_primary | not_stated_in_retrieved_text | preclinical_experiment | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/1569019 |
| 2022 | Outrunning obesity with Lac-Phe? | Cell metabolism | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/35921816 |
| 2025 | Class I histone deacetylases catalyze lysine lactylation | The Journal of biological chemistry | peer_reviewed_primary | not_stated_in_retrieved_text | not_stated_in_retrieved_text | none in retrieved text | requires_human_review | https://europepmc.org/article/MED/40835008 |


## Accession bridge to retrievable data

No accession appears in the retrieved text of any of the 375 records. Abstracts rarely carry accessions, so this says nothing about whether these studies deposited data; it says the bridge to retrievable data cannot be built from bibliographic records alone.

A record with no accession in its retrieved text is an open question about deposition, not a confirmed
deposition gap: bibliographic text is not a data availability statement.

## Human-review escalations

419 escalation(s) raised. The full queue is in `data/live/literature/lacphe/literature_escalations.csv`; the counts below are
the queue by type, followed by the first 25 rows.

| escalation | records | decision_needed |
| --- | --- | --- |
| subject_name_not_located_in_record | 220 | check the full text before treating this record as subject evidence |
| unscreenable_record | 142 | obtain full text or exclude explicitly; do not treat as screened-out |
| unresolved_data_deposition | 30 | check the full-text data availability statement before recording a deposition gap |
| cross_source_metadata_conflict | 9 | confirm the authoritative bibliographic record before citing |
| preprint_without_peer_review | 9 | decide whether the claim may be cited as evidence at this tier |
| possible_name_homonym | 5 | confirm the chemical entity from the full text before counting this record as subject evidence |
| retraction_flag_in_publication_type | 2 | verify retraction status before any use |
| retrieval_source_unavailable | 1 | re-run the lane from a permitted network egress before treating the sweep as complete |
| retrieval_truncated | 1 | raise the retrieval cap or narrow the query before claiming a complete sweep |


| escalation | reason | decision_needed | title | record_url |
| --- | --- | --- | --- | --- |
| cross_source_metadata_conflict | journal: metabolomics != metabolomics : official journal of the metabolomic society | confirm the authoritative bibliographic record before citing | Exercise intensity determines circulating levels of Lac-Phe and other exerkines: a randomized crossover trial | https://doi.org/10.1007/s11306-025-02260-0 |
| cross_source_metadata_conflict | journal: biosensors & bioelectronics != biosensors and bioelectronics | confirm the authoritative bibliographic record before citing | Rapid indirect detection of N-lactoyl-phenylalanine using dual DNA biosensors based on solution-gated graphene field-effect transistor | https://europepmc.org/article/MED/39818180 |
| cross_source_metadata_conflict | journal: trends in endocrinology & metabolism != trends in endocrinology and metabolism: tem | confirm the authoritative bibliographic record before citing | Lac-Phe (N-lactoyl-phenylalanine) | https://doi.org/10.1016/j.tem.2024.05.007 |
| cross_source_metadata_conflict | journal: nature reviews endocrinology != nature reviews. endocrinology | confirm the authoritative bibliographic record before citing | Metformin acts through appetite-suppressing metabolite: Lac-Phe | https://doi.org/10.1038/s41574-024-00986-w |
| cross_source_metadata_conflict | title: metformin induces a lac-phe gut-brain signalling axis != metformin induces a lac-phe gut–brain signalling axis | confirm the authoritative bibliographic record before citing | Metformin induces a Lac-Phe gut–brain signalling axis | https://doi.org/10.1038/s42255-024-01014-x |
| cross_source_metadata_conflict | title: exercise-induced n-lactoylphenylalanine predicts adipose tissue loss during endurance training in overweight and obese humans != increased levels of n-lactoylphenylalanine after exercise are related to adipose tissue loss during endurance training in humans with overweight and obesity | confirm the authoritative bibliographic record before citing | Exercise-Induced N-Lactoylphenylalanine Predicts Adipose Tissue Loss during Endurance Training in Overweight and Obese Humans | https://doi.org/10.3390/metabo13010015 |
| cross_source_metadata_conflict | journal: medical review != medical review (2021) | confirm the authoritative bibliographic record before citing | Lac-Phe: a central metabolic regulator and biomarker | https://doi.org/10.1515/mr-2025-0030 |
| cross_source_metadata_conflict | title: proof-of-concept of a prior validated lc-ms/ms method for detection of n -lactoyl-phenylalanine in dried blood spots before, during and after a performance diagnostic test of junior squad triathletes != proof-of-concept of a prior validated lc-ms/ms method for detection of n-lactoyl-phenylalanine in dried blood spots before, during and after a performance diagnostic test of junior squad triathletes | confirm the authoritative bibliographic record before citing | Proof-of-concept of a prior validated LC-MS/MS method for detection of N-lactoyl-phenylalanine in dried blood spots before, during and after a performance diagnostic test of junior squad triathletes | https://doi.org/10.3389/fspor.2025.1600714 |
| cross_source_metadata_conflict | journal: antioxidants != antioxidants (basel, switzerland) | confirm the authoritative bibliographic record before citing | The Emerging Role of N-Lactoyl-Phenylalanine (Lac-Phe) in Metabolic Regulation and Disease: From Exercise-Induced Metabolite to Therapeutic Candidate | https://doi.org/10.3390/antiox15040441 |
| possible_name_homonym | the queried name appears alongside both materials-science and biological context terms, so which entity the string denotes is unresolved | confirm the chemical entity from the full text before counting this record as subject evidence | Bilayer Scaffolds Synergize Immunomodulation and Rejuvenation via Layer-Specific Release of CK2.1 and the "Exercise Hormone" Lac-Phe for Enhanced Osteochondral Regeneration | https://europepmc.org/article/MED/39529517 |
| possible_name_homonym | the queried name appears alongside both materials-science and biological context terms, so which entity the string denotes is unresolved | confirm the chemical entity from the full text before counting this record as subject evidence | Exercise-induced Metabolite N-lactoyl-phenylalanine Ameliorates Colitis by Inhibiting M1 Macrophage Polarization via the Suppression of the NF-κB Signaling Pathway | https://europepmc.org/article/MED/40562095 |
| possible_name_homonym | the queried name appears alongside both materials-science and biological context terms, so which entity the string denotes is unresolved | confirm the chemical entity from the full text before counting this record as subject evidence | Practical Synthesis of N-Lactoyl-Phenylalanine and Its Isotopically Deuterated Variant Lac-Phe-d5 | https://doi.org/10.2174/0115701786492436260617164313 |
| possible_name_homonym | the queried name appears alongside both materials-science and biological context terms, so which entity the string denotes is unresolved | confirm the chemical entity from the full text before counting this record as subject evidence | Lac-Phe: An Exercise Induced Metabolite with Immunomodulatory Potential in Inflammatory Diseases | https://doi.org/10.23937/2378-3672/1410077 |
| possible_name_homonym | the queried name appears alongside both materials-science and biological context terms, so which entity the string denotes is unresolved | confirm the chemical entity from the full text before counting this record as subject evidence | Distinct microRNA and protein profiles of extracellular vesicles secreted from myotubes from morbidly obese donors with type 2 diabetes in response to electrical pulse stimulation | https://europepmc.org/article/MED/37064893 |
| preprint_without_peer_review | preprint with no linked journal publication in the preprint server record | decide whether the claim may be cited as evidence at this tier | Lac-Phe mediates the anti-obesity effect of metformin | https://europepmc.org/article/PPR/PPR753566 |
| preprint_without_peer_review | preprint with no linked journal publication in the preprint server record | decide whether the claim may be cited as evidence at this tier | SLC17 transporters mediate renal excretion of Lac-Phe in mice and humans | https://doi.org/10.1101/2024.04.18.589815 |
| preprint_without_peer_review | preprint with no linked journal publication in the preprint server record | decide whether the claim may be cited as evidence at this tier | The blood metabolome of cognitive function and brain health in middle-aged adults – influences of genes, gut microbiome, and exposome | https://europepmc.org/article/PPR/PPR956091 |
| preprint_without_peer_review | preprint with no linked journal publication in the preprint server record | decide whether the claim may be cited as evidence at this tier | Metformin inhibits mitochondrial complex I in intestinal epithelium to promote glycemic control | https://europepmc.org/article/PPR/PPR1095512 |
| preprint_without_peer_review | preprint with no linked journal publication in the preprint server record | decide whether the claim may be cited as evidence at this tier | Exercise intensity modulates the human plasma secretome and interorgan communication | https://europepmc.org/article/PPR/PPR1106168 |
| preprint_without_peer_review | preprint with no linked journal publication in the preprint server record | decide whether the claim may be cited as evidence at this tier | Rapid detection of N-lactoyl-phenylalanine for exercise evaluation using dual DNA biosensors based on solution-gated graphene field-effect transistor | https://doi.org/10.21203/rs.3.rs-4865146/v1 |
| preprint_without_peer_review | preprint with no linked journal publication in the preprint server record | decide whether the claim may be cited as evidence at this tier | Integrated multi-omics analyses reveal causal insights into the molecular landscape of urologic cancers | https://europepmc.org/article/PPR/PPR982825 |
| preprint_without_peer_review | preprint with no linked journal publication in the preprint server record | decide whether the claim may be cited as evidence at this tier | Genome-wide identification of the GRAS transcription factor family and regulation of metabolites under drought and salt stress in Isatis indigotica | https://europepmc.org/article/PPR/PPR1176897 |
| preprint_without_peer_review | preprint with no linked journal publication in the preprint server record | decide whether the claim may be cited as evidence at this tier | N-Lactoyl-Phenylalanine: An Exercise-Inducible Metabolite that Suppresses Feeding and Obesity - Species Dependence and Compound Characterization | https://doi.org/10.2139/ssrn.6291466 |
| retraction_flag_in_publication_type | publication type mentions retraction | verify retraction status before any use | Withdrawn: Combinatorial lipidomics and proteomics underscore erythrocyte lipid membrane aberrations in the development of adverse cardio-cerebrovascular complications in maintenance hemodialysis patients | https://europepmc.org/article/MED/39159596 |
| retraction_flag_in_publication_type | publication type mentions retraction | verify retraction status before any use | The causal relationship between blood metabolites and rosacea: A Mendelian randomization | https://europepmc.org/article/MED/38895784 |


## Evaluation gates

| gate | status |
| --- | --- |
| FAIR provenance | pass — every record keeps source system, source URL, and identifiers |
| reproducibility | pass — screening is regenerated offline from the declared record set with deterministic rules |
| critical evidence | pass — structured evidence, text inference, and unknown-for-lack-of-text are distinct values |
| human review | pass — 419 escalation(s) raised |
| mirage detection | pass — unreachable and truncated sources are reported as availability gaps, never as zero hits |
