# Exercise-study volcano figures (offline render of cached live tables)

Rendered by `scripts/render_exercise_studies_refmet_volcanoes.py` from the cached
differential tables in `data/live/`; `manifest.json` records, per figure, the
contrast semantics, FDR scope, feature-id rule, excluded internal standards,
RefMet match counts, source checksum, provenance status, and caveats. Colors are
RefMet super_class by exact name match against `data/live/refmet_annotations.csv`
(no RefMet release recorded); an unmatched feature is `unclassified_no_refmet_match`.

| Figure | Contrast | Test family shown | Read with |
| --- | --- | --- | --- |
| `ST004303_human_*` | 4P vs 1P, paired on log2 abundance | one BH family over the 266 features with >=3 complete pairs (scan lane) | MIE and SIE arms are pooled; 1P/4P read as pre/post from the MW `Time` factor, unverified against the protocol |
| `motrpac_human_endur_post_*` | ADU endurance post 3.5-4 h vs pre | **eleven** per-platform BH families overlaid, as released in MoTrPAC v1.3 dream-acute DA tables | a RefMet name measured on several platforms appears once per platform |
| `motrpac_pass1b06_8w_female_*` | 8-week trained vs sex-matched sedentary control, female | one timewise DA family (female) as released | training adaptation, not an acute bout; no retrieval provenance record for the table |
| `motrpac_pass1b06_8w_male_*` | same, male | one timewise DA family (male) as released | as above |

One figure is one contrast in one multiple-testing family. The rat table is
sex-stratified at the source and is never pooled into a single volcano; the
earlier pooled render was withdrawn because it double-counted every feature.
Twenty-one internal-standard rows per sex are excluded and counted in the
manifest.

`mw_exercise_studies.csv` is a keyword-retrieved candidate list with no recorded
query. `scripts/screen_mw_exercise_study_titles.py` writes
`mw_exercise_studies_screened.csv` and `mw_exercise_studies_screening.json`:
19 of 66 titles support an exercise context, 3 match only an ambiguous phrase,
and 44 contain no exercise term. Every row is `requires_human_review`; a title
term is inference, not a design classification.

`ST003807` is a registered exercise study with no fetched statistics table; it
is a coverage gap, not evidence that the study lacks data.
