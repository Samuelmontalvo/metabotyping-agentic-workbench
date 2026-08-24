# Human and rat BAG3 MoTrPAC plots

## Human PRECAWG app plot

- Source: https://data-viz.motrpac-data.org/precawg/
- App controls: Muscle; RNA-Seq; Gene symbols; BAG3; ENSG00000151929.10; log2 raw value; Exercise group; linear layout.
- Download status: the app exposed the combined plot download in this session; separate plot-data and plot-only downloads were not active.
- Output: `human_bag3_precawg_feature_trajectories.png`.

## Rat Data Hub plot

- Source: https://motrpac-data.org/ and public search API `https://search.motrpac-data.org/search/api`.
- Query: `ktype=gene`, `keys=BAG3`, `study=pass1b06`, `omics=transcriptomics`, `size=10000`.
- Exact BAG3 rows returned: 142.
- Tissues returned: adrenal; blood rna; brown adipose; colon; cortex; gastrocnemius; heart; hippocampus; hypothalamus; kidney; liver; lung; ovaries; small intestine; spleen; testes; vastus lateralis; vena cava; white adipose.
- Output: `rat_bag3_pass1b06_transcriptomics_timewise_all_tissues.png`.
- Muscle subset: `rat_bag3_pass1b06_transcriptomics_timewise_skeletal_muscle.png`.

## Interpretation guardrails

- The human plot is a PRECAWG acute-bout raw-value feature trajectory downloaded from the human visualization app.
- The rat plots are pass1b-06 timewise endurance-training differential rows from the Data Hub gene search API.
- These are provenance-compatible BAG3 visualizations, but they are not a direct statistical human-vs-rat comparison because protocol, model, value type, and species differ.
