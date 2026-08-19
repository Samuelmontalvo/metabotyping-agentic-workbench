# Rat BAG3 MoTrPAC plot

## Rat Data Hub plot

- Source: https://motrpac-data.org/ and public search API `https://search.motrpac-data.org/search/api`.
- Query: `ktype=gene`, `keys=BAG3`, `study=pass1b06`, `omics=transcriptomics`, `size=10000`.
- Exact BAG3 rows returned: 142.
- Tissues returned: adrenal; blood rna; brown adipose; colon; cortex; gastrocnemius; heart; hippocampus; hypothalamus; kidney; liver; lung; ovaries; small intestine; spleen; testes; vastus lateralis; vena cava; white adipose.
- Output: `rat_bag3_pass1b06_transcriptomics_timewise_all_tissues.png`.
- Muscle subset: `rat_bag3_pass1b06_transcriptomics_timewise_skeletal_muscle.png`.

## Interpretation guardrails

- Rat plots are pass1b-06 timewise endurance-training differential rows from the Data Hub gene search API.
- Do not present these as human PRECAWG acute-bout raw-value trajectories or as a direct cross-species statistical comparison.
