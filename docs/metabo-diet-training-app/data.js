const TRAINING_DATA = {
  module: {
    title: "Metabo-Diet Harmonization Trainer",
    subtitle: "Diet, phenotype, and metabolomics cross-resource practice",
    audience: "Intermediate CFDE learners",
    estimatedTime: "2.5 hours",
    deliverableDate: "August 14, 2026",
    sourceNote:
      "Synthetic training data only. Public resource names are used as instructional contexts, not live data pulls."
  },
  lessons: [
    {
      id: "why",
      label: "Why it matters",
      time: "20 min",
      focus: "Connect diet, activity, clinical context, and metabolomics reuse.",
      outcome: "Identify why cohort context must be preserved before interpretation."
    },
    {
      id: "cohorts",
      label: "Cohort structure",
      time: "30 min",
      focus: "Compare diet, activity, exercise, clinical, and provenance fields.",
      outcome: "Classify variables as comparable, partially comparable, or not comparable."
    },
    {
      id: "crosswalk",
      label: "Crosswalk builder",
      time: "35 min",
      focus: "Map variables with units, timing, modality, and evidence.",
      outcome: "Route uncertain mappings to human review instead of forced ETL."
    },
    {
      id: "analysis",
      label: "Guided analysis",
      time: "40 min",
      focus: "Interpret exploratory outputs in light of design differences.",
      outcome: "Separate signal, context, and unsupported inference."
    },
    {
      id: "transfer",
      label: "Transfer check",
      time: "15 min",
      focus: "Apply the same review logic to another CFDE-style resource.",
      outcome: "Export a reusable harmonization artifact and transfer checklist."
    }
  ],
  cohorts: [
    {
      id: "nph",
      name: "Nutrition for Precision Health proxy",
      anchor: "Diet-centered cohort context",
      access: "Public metadata description; synthetic practice rows",
      strengths: ["dietary recall structure", "clinical phenotypes", "meal timing context"],
      constraints: ["participant-level data not included", "metabolomics tables represented synthetically"]
    },
    {
      id: "motrpac",
      name: "MoTrPAC proxy",
      anchor: "Exercise-centered cohort context",
      access: "Open summary-style practice data",
      strengths: ["exercise timing", "CPET context", "biospecimen timepoints"],
      constraints: ["diet context is limited", "training arms require explicit provenance"]
    },
    {
      id: "mw",
      name: "Metabolomics Workbench proxy",
      anchor: "Transfer resource",
      access: "Open repository pattern; synthetic examples",
      strengths: ["accession-first discovery", "assay metadata", "metabolite identifiers"],
      constraints: ["phenotype depth varies", "codebook completeness must be checked"]
    }
  ],
  comparisonRows: [
    {
      id: "dietary_pattern",
      domain: "Dietary pattern",
      nph: "24-hour recall and diet-pattern metadata",
      motrpac: "Limited diet context alongside exercise protocol",
      expected: "partial",
      evidence: "Same broad domain, different measurement depth and study intent."
    },
    {
      id: "exercise_exposure",
      domain: "Exercise exposure",
      nph: "Lifestyle/activity context",
      motrpac: "Structured acute and training exercise protocol",
      expected: "partial",
      evidence: "Activity context can inform interpretation, but protocol exposure is not equivalent."
    },
    {
      id: "cpet",
      domain: "Cardiorespiratory fitness",
      nph: "May be absent or indirectly represented",
      motrpac: "CPET and VO2-related endpoints",
      expected: "not",
      evidence: "Do not infer CPET compatibility without endpoint and protocol evidence."
    },
    {
      id: "biospecimen_timing",
      domain: "Biospecimen timing",
      nph: "Diet/visit-centered collection context",
      motrpac: "Pre/post acute exercise and training follow-up",
      expected: "partial",
      evidence: "Timing can be aligned only after preserving visit, fasting, and exposure context."
    },
    {
      id: "metabolite_id",
      domain: "Metabolite identifiers",
      nph: "Identifier table with database cross-references",
      motrpac: "Metabolite features with platform-specific naming",
      expected: "direct",
      evidence: "Identifier crosswalks can be shared when IDs and provenance are retained."
    }
  ],
  crosswalkRows: [
    {
      id: "vo2max",
      study: "SYN-MOTRPAC-LIKE",
      sourceVariable: "vo2max",
      label: "VO2max",
      unit: "mL/kg/min",
      timing: "baseline",
      modality: "CPET",
      candidate: "vo2max",
      correctStatus: "accepted",
      confidence: 0.96,
      rationale: "Confirmed maximal test endpoint with matching unit and timing.",
      provenance: "Synthetic MoTrPAC-like variable dictionary"
    },
    {
      id: "vo2peak",
      study: "SYN-CPET-RICH",
      sourceVariable: "vo2peak",
      label: "VO2peak",
      unit: "mL/kg/min",
      timing: "baseline",
      modality: "CPET",
      candidate: "vo2max",
      correctStatus: "review",
      confidence: 0.58,
      rationale: "Related endpoint, but VO2peak must not be collapsed into vo2max without protocol evidence.",
      provenance: "Synthetic CPET-rich variable dictionary"
    },
    {
      id: "diet_score",
      study: "SYN-DIET-BODY",
      sourceVariable: "diet_score",
      label: "Diet quality score",
      unit: "points",
      timing: "baseline",
      modality: "diet",
      candidate: "not_mapped",
      correctStatus: "rejected",
      confidence: 0.19,
      rationale: "No supported common-variable mapping is defined for this synthetic diet score.",
      provenance: "Synthetic diet and body-composition cohort"
    },
    {
      id: "daily_steps",
      study: "SYN-ACTI-MET",
      sourceVariable: "daily_steps",
      label: "Daily steps",
      unit: "steps/day",
      timing: "7-day average",
      modality: "actigraphy",
      candidate: "steps_per_day",
      correctStatus: "review",
      confidence: 0.72,
      rationale: "Likely compatible, but device window and aggregation definition need review.",
      provenance: "Synthetic actigraphy-metabolomics cohort"
    },
    {
      id: "body_mass_index",
      study: "SYN-DIET-BODY",
      sourceVariable: "body_mass_index",
      label: "BMI",
      unit: "kg/m^2",
      timing: "baseline",
      modality: "body composition",
      candidate: "bmi",
      correctStatus: "review",
      confidence: 0.76,
      rationale: "Synonym and unit match, but provenance and calculation basis should be checked.",
      provenance: "Synthetic diet and body-composition cohort"
    },
    {
      id: "glucose_fasting",
      study: "SYN-OMICS-GEN",
      sourceVariable: "glucose_fasting",
      label: "Fasting glucose",
      unit: "mmol/L",
      timing: "baseline",
      modality: "clinical",
      candidate: "fasting_glucose",
      correctStatus: "review",
      confidence: 0.67,
      rationale: "Concept matches, but unit conversion and assay context require review.",
      provenance: "Synthetic metadata-only omics cohort"
    }
  ],
  quizQuestions: [
    {
      id: "q1",
      question: "What is the safest action when a variable name looks similar but unit or protocol evidence is incomplete?",
      options: [
        "Accept the mapping and document it later",
        "Route the mapping to human review",
        "Drop the variable from the inventory"
      ],
      answer: 1
    },
    {
      id: "q2",
      question: "Which evidence is required before treating VO2peak as vo2max?",
      options: [
        "Both labels include VO2",
        "The studies are exercise studies",
        "Protocol and endpoint evidence support equivalence"
      ],
      answer: 2
    },
    {
      id: "q3",
      question: "What should a harmonization crosswalk preserve?",
      options: [
        "Only the final common variable name",
        "Source variable, provenance, decision status, and rationale",
        "Only high-confidence accepted variables"
      ],
      answer: 1
    },
    {
      id: "q4",
      question: "Why use synthetic data in this app?",
      options: [
        "To avoid controlled-access data and keep the module reproducible",
        "To remove the need for provenance",
        "To make all mappings automatically valid"
      ],
      answer: 0
    }
  ],
  transferChecklist: [
    "Confirm repository accession, metadata, codebook, data files, assay platform, and biospecimen timing.",
    "Separate direct matches from enrichment candidates and mirage risks.",
    "Check units, timing windows, specimen matrices, and measurement protocols before mapping.",
    "Route low-confidence or endpoint-ambiguous variables to human review.",
    "Export the crosswalk with provenance and decision rationale before downstream analysis."
  ],
  interpretationSignals: [
    { label: "Identifier overlap", value: 72, detail: "Shared HMDB or InChIKey evidence" },
    { label: "Timing compatibility", value: 46, detail: "Visit and exposure context aligned" },
    { label: "Diet context", value: 64, detail: "Diet metadata available for interpretation" },
    { label: "Review burden", value: 38, detail: "Rows requiring human review" }
  ]
};
