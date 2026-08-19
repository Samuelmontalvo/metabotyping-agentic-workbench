"""Evaluate project skills and agent manifests against explicit local contracts."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SKILL_ROOTS = {
    "codex": ROOT / ".agents/skills",
    "claude": ROOT / ".claude/skills",
}

AGENT_ROOTS = {
    "codex": ROOT / ".codex/agents",
    "claude": ROOT / ".claude/agents",
}

AGENT_ALIAS_REGISTRY = ROOT / ".agents/agent_aliases.toml"

EXPECTED_CANONICAL_AGENT_NAMES = {
    "assay-harmonization-skeptic",
    "benchmark-agent",
    "biospecimen-preanalytics-reviewer",
    "cross-field-consistency-arbitrator",
    "dataset-readiness-reviewer",
    "discovery-orchestrator",
    "exercise-phenotype-harmonization-reviewer",
    "harmonization-skeptic",
    "literature-retrieval",
    "metabolite-identity-resolver",
    "metabolomics-visualization-analyst",
    "metadata-extraction-critic",
    "metadata-extractor",
    "motrpac-metadata-readiness-analyst",
    "multi-source-orchestrator",
    "pipeline-builder",
    "repository-discovery",
    "source-registry-librarian",
    "statistical-estimand-and-synthesis-skeptic",
    "study-design-population-context-reviewer",
    "variable-crosswalk",
}

EXPECTED_DEPRECATED_AGENT_ALIASES = {
    "data-quality-reviewer": {
        "alias": "data-quality-reviewer",
        "canonical": "dataset-readiness-reviewer",
        "status": "deprecated",
        "deprecated_since": "0.2.0",
        "remove_in": "0.3.0",
        "compatibility": "behaviorally_equivalent",
        "platforms": ["codex", "claude"],
    },
    "motrpac-replication-analyst": {
        "alias": "motrpac-replication-analyst",
        "canonical": "motrpac-metadata-readiness-analyst",
        "status": "deprecated",
        "deprecated_since": "0.2.0",
        "remove_in": "0.3.0",
        "compatibility": "behaviorally_equivalent",
        "platforms": ["codex", "claude"],
    },
}

_ALIAS_KEYS = {
    "alias",
    "canonical",
    "status",
    "deprecated_since",
    "remove_in",
    "compatibility",
    "platforms",
}
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_AGENT_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

REQUIRED_SECTIONS = [
    "# Purpose",
    "# Inputs",
    "# Steps",
    "# Outputs",
    "# Validation Checks",
    "# Failure Modes",
    "# Human-Review Triggers",
    "# Evaluation Gates",
]

QUALITY_GATES = {
    "fair_data": {
        "all": ["fair"],
        "any": ["metadata", "provenance", "accession", "source"],
    },
    "reproducibility": {
        "all": ["reproduc"],
        "any": ["declared", "regenerated", "deterministic"],
    },
    "critical_evidence": {
        "all": ["critical evidence", "do not"],
        "any": ["missing", "uncertain", "inferred", "assumption", "approved"],
    },
    "human_review": {
        "all": ["human", "review"],
        "any": ["trigger", "decision", "reviewer"],
    },
    "structured_scoring": {
        "all": ["skill quality rubric", "pass only"],
        "any": ["score", "quality", "evidence", "validation"],
    },
}

# Each skill must name the executable artifact that implements it. Agent-only
# synthesis is allowed only when the skill says so explicitly.
EXPECTED_IMPLEMENTATIONS: dict[str, tuple[str, ...]] = {
    "assay-platform-harmonization": (
        "src/metabotyping_agentic/harmonization/assay_models.py",
        "src/metabotyping_agentic/harmonization/assay_harmonization.py",
        "scripts/build_assay_harmonization_plan.py",
    ),
    "benchmark-agents": ("src/metabotyping_agentic/evaluation/benchmark.py",),
    "biospecimen-preanalytics-reviewer": (
        "src/metabotyping_agentic/review/validation.py",
        "src/metabotyping_agentic/review/models.py",
    ),
    "define-inclusion-criteria": ("src/metabotyping_agentic/discovery/criteria.py",),
    "exercise-phenotype-harmonization-reviewer": (
        "src/metabotyping_agentic/review/validation.py",
        "src/metabotyping_agentic/review/models.py",
    ),
    "grant-aims-refiner": (),
    "harmonization-plan": ("src/metabotyping_agentic/harmonization/harmonization_plan.py",),
    "harmonization-skeptic": ("src/metabotyping_agentic/harmonization/skeptic.py",),
    "human-review-packet": ("src/metabotyping_agentic/reports/render.py",),
    "metabolite-effect-search": ("scripts/run_metabolite_effect_search.py",),
    "metabolite-identity-resolution": (
        "src/metabotyping_agentic/harmonization/assay_models.py",
        "src/metabotyping_agentic/harmonization/assay_harmonization.py",
    ),
    "metadata-card-extraction": (
        "src/metabotyping_agentic/extraction/metadata_cards.py",
        "src/metabotyping_agentic/extraction/variable_inventory.py",
    ),
    "motrpac-alignment": ("src/metabotyping_agentic/evaluation/motrpac_alignment.py",),
    "motrpac-plotting": (
        "src/metabotyping_agentic/plotting/motrpac_plot_helpers.R",
        "src/metabotyping_agentic/plotting/metabolomics.py",
        "scripts/render_synthetic_motrpac_plot_suite.py",
    ),
    "multi-database-metabolomics-router": (
        "src/metabotyping_agentic/knowledge/source_registry.py",
    ),
    "plot-motrpac-bag3": (
        ".agents/skills/plot-motrpac-bag3/scripts/plot_bag3_acute_motrpac.R",
        ".agents/skills/plot-motrpac-bag3/scripts/plot_rat_bag3_from_search_api.R",
        "src/metabotyping_agentic/plotting/motrpac_plot_helpers.R",
    ),
    "quality-scoring": ("src/metabotyping_agentic/evaluation/quality_scoring.py",),
    "recommendation-engine": ("src/metabotyping_agentic/discovery/recommender.py",),
    "repository-intake": (
        "src/metabotyping_agentic/discovery/repositories.py",
        "src/metabotyping_agentic/discovery/mirage_detector.py",
    ),
    "statistical-estimand-and-synthesis-skeptic": (
        "src/metabotyping_agentic/review/validation.py",
        "src/metabotyping_agentic/review/models.py",
    ),
    "study-dataset-discovery": (
        "src/metabotyping_agentic/discovery/literature.py",
        "src/metabotyping_agentic/discovery/recommender.py",
    ),
    "study-design-population-context-reviewer": (
        "src/metabotyping_agentic/review/validation.py",
        "src/metabotyping_agentic/review/models.py",
    ),
    "variable-crosswalk": ("src/metabotyping_agentic/harmonization/crosswalk.py",),
}


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def parse_frontmatter(text: str) -> tuple[dict[str, str], str, list[str]]:
    """Parse the simple YAML frontmatter used by project Markdown contracts."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, ["missing opening frontmatter delimiter"]
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return {}, text, ["missing closing frontmatter delimiter"]

    values: dict[str, str] = {}
    errors: list[str] = []
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            errors.append(f"invalid frontmatter line: {line}")
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values, "\n".join(lines[end + 1 :]), errors


def normalize_agent_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _is_normalized_agent_slug(name: str) -> bool:
    return bool(_AGENT_SLUG_RE.fullmatch(name)) and normalize_agent_name(name) == name


def _semver_key(value: str) -> tuple[Any, ...]:
    match = _SEMVER_RE.fullmatch(value)
    if not match:
        raise ValueError(f"invalid semantic version: {value!r}")
    major, minor, patch, prerelease, _build = match.groups()
    prerelease_key: tuple[tuple[int, Any], ...] = ()
    if prerelease is not None:
        parts: list[tuple[int, Any]] = []
        for identifier in prerelease.split("."):
            if identifier.isdigit():
                if len(identifier) > 1 and identifier.startswith("0"):
                    raise ValueError(f"invalid semantic version: {value!r}")
                parts.append((0, int(identifier)))
            else:
                parts.append((1, identifier))
        prerelease_key = tuple(parts)
    return (
        int(major),
        int(minor),
        int(patch),
        1 if prerelease is None else 0,
        prerelease_key,
    )


def _project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        value = tomllib.load(handle).get("project", {}).get("version", "")
    _semver_key(str(value))
    return str(value)


def _contract_fingerprint(value: str) -> str:
    """Normalize host whitespace while preserving exact contract semantics."""
    return " ".join(value.strip().split())


def _normalized_description(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _deprecated_alias_description(canonical: str, remove_in: str) -> str:
    return (
        f"Deprecated alias for {canonical}; remove in {remove_in}. "
        "Behavior is otherwise equivalent."
    )


def load_agent_alias_registry(
    path: Path = AGENT_ALIAS_REGISTRY,
) -> tuple[dict[str, Any], list[str]]:
    """Load and structurally validate the repository-owned alias registry."""
    try:
        with path.open("rb") as handle:
            registry = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {"schema_version": None, "aliases": []}, [
            f"agent alias registry error: {exc}"
        ]

    issues: list[str] = []
    if set(registry) != {"schema_version", "aliases"}:
        issues.append(
            "agent alias registry must contain only schema_version and aliases"
        )
    if registry.get("schema_version") != 1:
        issues.append("agent alias registry schema_version must equal 1")
    aliases = registry.get("aliases")
    if not isinstance(aliases, list):
        issues.append("agent alias registry aliases must be an array")
        aliases = []

    alias_names: list[str] = []
    canonical_names: list[str] = []
    normalized_rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(aliases, start=1):
        label = f"agent alias registry row {index}"
        if not isinstance(raw_row, dict):
            issues.append(f"{label} must be a table")
            continue
        row = dict(raw_row)
        if set(row) != _ALIAS_KEYS:
            missing = sorted(_ALIAS_KEYS - set(row))
            extra = sorted(set(row) - _ALIAS_KEYS)
            if missing:
                issues.append(f"{label} missing keys: {', '.join(missing)}")
            if extra:
                issues.append(f"{label} unsupported keys: {', '.join(extra)}")
        for key in _ALIAS_KEYS - {"platforms"}:
            if not isinstance(row.get(key), str) or not str(row.get(key)).strip():
                issues.append(f"{label} {key} must be a nonempty string")

        alias = str(row.get("alias", ""))
        canonical = str(row.get("canonical", ""))
        if not _is_normalized_agent_slug(alias):
            issues.append(f"{label} alias must be a normalized hyphenated slug")
        if not _is_normalized_agent_slug(canonical):
            issues.append(f"{label} canonical must be a normalized hyphenated slug")
        if alias == canonical:
            issues.append(f"{label} alias and canonical must differ")
        if row.get("status") != "deprecated":
            issues.append(f"{label} status must equal deprecated")
        if row.get("compatibility") != "behaviorally_equivalent":
            issues.append(
                f"{label} compatibility must equal behaviorally_equivalent"
            )
        if row.get("platforms") != ["codex", "claude"]:
            issues.append(f"{label} platforms must equal ['codex', 'claude']")
        try:
            deprecated_key = _semver_key(str(row.get("deprecated_since", "")))
            removal_key = _semver_key(str(row.get("remove_in", "")))
            if deprecated_key >= removal_key:
                issues.append(f"{label} deprecated_since must precede remove_in")
        except ValueError as exc:
            issues.append(f"{label} {exc}")
        alias_names.append(alias)
        canonical_names.append(canonical)
        normalized_rows.append(row)

    duplicates = sorted(
        {name for name in alias_names if alias_names.count(name) > 1 and name}
    )
    for alias in duplicates:
        issues.append(f"duplicate agent alias: {alias}")
    duplicate_targets = sorted(
        {
            name
            for name in canonical_names
            if canonical_names.count(name) > 1 and name
        }
    )
    for canonical in duplicate_targets:
        issues.append(f"duplicate canonical alias target: {canonical}")
    alias_set = set(alias_names)
    for row in normalized_rows:
        canonical = str(row.get("canonical", ""))
        if canonical in alias_set:
            issues.append(
                f"agent alias {row.get('alias', '')} targets alias {canonical}; "
                "aliases must resolve in one hop"
            )

    return {"schema_version": registry.get("schema_version"), "aliases": normalized_rows}, issues


def resolve_agent_name(
    name: str,
    registry: dict[str, Any] | None = None,
    project_version: str | None = None,
) -> str:
    """Resolve a current alias exactly one hop or return the normalized name."""
    if registry is None:
        registry, issues = load_agent_alias_registry()
        if issues:
            raise ValueError("; ".join(issues))
    rows = registry.get("aliases", [])
    if not isinstance(rows, list):
        raise ValueError("agent alias registry aliases must be an array")
    aliases = {str(row.get("alias", "")): row for row in rows if isinstance(row, dict)}
    if len(aliases) != len(rows):
        raise ValueError("agent aliases must be unique tables")
    for alias, row in aliases.items():
        canonical = str(row.get("canonical", ""))
        if not alias or not canonical or canonical in aliases:
            raise ValueError("agent aliases must resolve exactly one hop")
    normalized = normalize_agent_name(name)
    row = aliases.get(normalized)
    if row is None:
        return normalized
    version = project_version or _project_version()
    if _semver_key(version) >= _semver_key(str(row["remove_in"])):
        raise ValueError(
            f"expired agent alias {normalized}: remove_in {row['remove_in']} reached"
        )
    return str(row["canonical"])


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _skill_pair_path(platform: str, name: str) -> Path:
    other_platform = "claude" if platform == "codex" else "codex"
    return SKILL_ROOTS[other_platform] / name / "SKILL.md"


def evaluate_skill_file(path: Path, platform: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    frontmatter, _, frontmatter_errors = parse_frontmatter(text)
    name = frontmatter.get("name", "")
    directory_name = path.parent.name
    lower = text.lower()

    missing_sections = [section for section in REQUIRED_SECTIONS if section not in text]
    gate_results: dict[str, bool] = {}
    for gate, config in QUALITY_GATES.items():
        gate_results[gate] = all(term in lower for term in config["all"]) and any(
            term in lower for term in config["any"]
        )

    structural_checks = {
        "valid_frontmatter": not frontmatter_errors,
        "name_matches_directory": name == directory_name,
        "description_present": bool(frontmatter.get("description")),
        **{f"section:{section[2:]}": section not in missing_sections for section in REQUIRED_SECTIONS},
        **{f"gate:{gate}": result for gate, result in gate_results.items()},
    }

    pair_path = _skill_pair_path(platform, directory_name)
    pair_exists = pair_path.exists()
    exact_pair = pair_exists and pair_path.read_text(encoding="utf-8") == text

    expected_paths = EXPECTED_IMPLEMENTATIONS.get(directory_name)
    if expected_paths is None:
        implementation_declared = False
        implementation_paths_exist = False
        implementation_status = "unregistered"
    elif not expected_paths:
        implementation_declared = "agent-only" in lower
        implementation_paths_exist = True
        implementation_status = "agent_only_declared" if implementation_declared else "undeclared_agent_only"
    else:
        implementation_declared = all(item in text for item in expected_paths)
        implementation_paths_exist = all((ROOT / item).exists() for item in expected_paths)
        implementation_status = "linked" if implementation_declared and implementation_paths_exist else "broken_link"

    operational_checks = {
        "paired_counterpart_exists": pair_exists,
        "paired_contract_exact": exact_pair,
        "implementation_declared": implementation_declared,
        "implementation_paths_exist": implementation_paths_exist,
    }
    structural_score = _mean([float(value) for value in structural_checks.values()])
    operational_score = _mean([float(value) for value in operational_checks.values()])

    issues = list(frontmatter_errors)
    issues.extend(f"missing {section}" for section in missing_sections)
    issues.extend(f"failed quality gate: {gate}" for gate, passed in gate_results.items() if not passed)
    issues.extend(f"failed operational check: {name}" for name, passed in operational_checks.items() if not passed)

    return {
        "path": _relative(path),
        "platform": platform,
        "name": directory_name,
        "structural_score": structural_score,
        "operational_score": operational_score,
        "overall_score": round((structural_score + operational_score) / 2, 3),
        "structural_checks": structural_checks,
        "operational_checks": operational_checks,
        "implementation_status": implementation_status,
        "implementation_paths": list(expected_paths or []),
        "issues": issues,
    }


def evaluate_skills() -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    for platform, root in SKILL_ROOTS.items():
        rows.extend(evaluate_skill_file(path, platform) for path in sorted(root.glob("*/SKILL.md")))

    inventory_issues: list[str] = []
    names_by_platform = {
        platform: {path.parent.name for path in root.glob("*/SKILL.md")}
        for platform, root in SKILL_ROOTS.items()
    }
    for name in sorted(names_by_platform["codex"] ^ names_by_platform["claude"]):
        present = [platform for platform, names in names_by_platform.items() if name in names]
        inventory_issues.append(f"unpaired skill {name}: present only in {', '.join(present)}")
    expected_skill_names = set(EXPECTED_IMPLEMENTATIONS)
    for platform, names in names_by_platform.items():
        for name in sorted(expected_skill_names - names):
            inventory_issues.append(f"missing expected {platform} skill {name}")
        for name in sorted(names - expected_skill_names):
            inventory_issues.append(f"unexpected {platform} skill {name}")
    for row in rows:
        if row["implementation_status"] in {"unregistered", "broken_link", "undeclared_agent_only"}:
            inventory_issues.append(f"skill implementation issue: {row['path']} ({row['implementation_status']})")
    return rows, inventory_issues


def _load_codex_agent(path: Path) -> tuple[dict[str, Any], str, list[str]]:
    try:
        with path.open("rb") as handle:
            config = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {}, "", [str(exc)]
    allowed_keys = {"name", "description", "developer_instructions"}
    errors = [
        "unsupported Codex agent manifest keys: "
        + ", ".join(sorted(set(config) - allowed_keys))
    ] if set(config) - allowed_keys else []
    instructions = str(config.get("developer_instructions", ""))
    return config, instructions, errors


def _load_claude_agent(path: Path) -> tuple[dict[str, Any], str, list[str]]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body, errors = parse_frontmatter(text)
    allowed_keys = {"name", "description"}
    if set(frontmatter) - allowed_keys:
        errors.append(
            "unsupported Claude agent frontmatter keys: "
            + ", ".join(sorted(set(frontmatter) - allowed_keys))
        )
    return frontmatter, body, errors


def evaluate_agents(
    project_version: str | None = None,
    alias_registry_path: Path = AGENT_ALIAS_REGISTRY,
) -> tuple[list[dict[str, Any]], list[str]]:
    paths_by_platform = {
        "codex": sorted(AGENT_ROOTS["codex"].glob("*.toml")),
        "claude": sorted(AGENT_ROOTS["claude"].glob("*.md")),
    }
    logical_paths: dict[str, dict[str, list[Path]]] = {"codex": {}, "claude": {}}
    for platform, paths in paths_by_platform.items():
        for path in paths:
            logical_name = normalize_agent_name(path.stem)
            logical_paths[platform].setdefault(logical_name, []).append(path)

    inventory_issues: list[str] = []
    for platform, groups in logical_paths.items():
        for name, paths in groups.items():
            if len(paths) > 1:
                inventory_issues.append(
                    f"duplicate logical {platform} agent {name}: " + ", ".join(_relative(path) for path in paths)
                )
            for path in paths:
                if path.stem != name or not _is_normalized_agent_slug(path.stem):
                    inventory_issues.append(
                        f"unsupported {platform} agent filename {path.name}: "
                        "use the normalized hyphenated canonical or registered alias name"
                    )

    registry, registry_issues = load_agent_alias_registry(alias_registry_path)
    inventory_issues.extend(registry_issues)
    alias_specs = {
        str(row.get("alias", "")): row
        for row in registry.get("aliases", [])
        if isinstance(row, dict) and str(row.get("alias", ""))
    }
    alias_names = set(alias_specs)
    expected_alias_names = set(EXPECTED_DEPRECATED_AGENT_ALIASES)
    for alias in sorted(expected_alias_names - alias_names):
        inventory_issues.append(f"missing expected deprecated agent alias {alias}")
    for alias in sorted(alias_names - expected_alias_names):
        inventory_issues.append(f"unexpected deprecated agent alias {alias}")
    for alias in sorted(alias_names & expected_alias_names):
        if alias_specs[alias] != EXPECTED_DEPRECATED_AGENT_ALIASES[alias]:
            inventory_issues.append(
                f"deprecated agent alias metadata mismatch: {alias}"
            )
    version = project_version or _project_version()
    try:
        version_key = _semver_key(version)
    except ValueError as exc:
        inventory_issues.append(str(exc))
        version_key = (0, 0, 0)

    for platform, groups in logical_paths.items():
        canonical_names = set(groups) - alias_names
        for name in sorted(EXPECTED_CANONICAL_AGENT_NAMES - canonical_names):
            inventory_issues.append(f"missing expected canonical {platform} agent {name}")
        for name in sorted(canonical_names - EXPECTED_CANONICAL_AGENT_NAMES):
            inventory_issues.append(f"unexpected canonical {platform} agent {name}")

    for alias, spec in sorted(alias_specs.items()):
        canonical = str(spec.get("canonical", ""))
        declared_platforms = spec.get("platforms", [])
        for platform in ("codex", "claude"):
            if platform not in declared_platforms:
                continue
            if len(logical_paths[platform].get(alias, [])) != 1:
                inventory_issues.append(
                    f"deprecated agent alias {alias} must have exactly one {platform} shim"
                )
            if len(logical_paths[platform].get(canonical, [])) != 1:
                inventory_issues.append(
                    f"unknown canonical target {canonical} for agent alias {alias} "
                    f"on {platform}"
                )
        try:
            expired = version_key >= _semver_key(str(spec.get("remove_in", "")))
        except ValueError:
            expired = False
        if expired:
            inventory_issues.append(
                f"expired agent alias {alias}: remove_in {spec.get('remove_in')} "
                f"reached by {version}"
            )

    loaded: dict[str, dict[str, list[dict[str, Any]]]] = {
        "codex": {},
        "claude": {},
    }
    for platform, groups in logical_paths.items():
        for logical_name, paths in groups.items():
            records: list[dict[str, Any]] = []
            for path in paths:
                if platform == "codex":
                    metadata, instructions, parse_errors = _load_codex_agent(path)
                else:
                    metadata, instructions, parse_errors = _load_claude_agent(path)
                records.append(
                    {
                        "path": path,
                        "metadata": metadata,
                        "instructions": instructions,
                        "parse_errors": parse_errors,
                    }
                )
            loaded[platform][logical_name] = records

    def single_record(platform: str, logical_name: str) -> dict[str, Any] | None:
        records = loaded[platform].get(logical_name, [])
        return records[0] if len(records) == 1 else None

    def paired_contract_parity(logical_name: str) -> bool:
        codex = single_record("codex", logical_name)
        claude = single_record("claude", logical_name)
        if codex is None or claude is None:
            return False
        return (
            _normalized_description(codex["metadata"].get("description", ""))
            == _normalized_description(claude["metadata"].get("description", ""))
            and _contract_fingerprint(codex["instructions"])
            == _contract_fingerprint(claude["instructions"])
        )

    for logical_name in sorted(
        set(logical_paths["codex"]) & set(logical_paths["claude"])
    ):
        if not paired_contract_parity(logical_name):
            inventory_issues.append(
                f"paired agent contract parity mismatch: {logical_name}"
            )

    rows: list[dict[str, Any]] = []
    for platform, groups in loaded.items():
        other_platform = "claude" if platform == "codex" else "codex"
        for logical_name, records in sorted(groups.items()):
            for record in records:
                path = record["path"]
                metadata = record["metadata"]
                instructions = record["instructions"]
                parse_errors = record["parse_errors"]
                declared_name = str(metadata.get("name", ""))
                lower = instructions.lower()
                alias_spec = alias_specs.get(logical_name)
                is_alias = alias_spec is not None
                canonical_name = (
                    str(alias_spec.get("canonical", ""))
                    if alias_spec is not None
                    else logical_name
                )
                checks = {
                    "valid_config": not parse_errors,
                    "name_matches_filename": (
                        declared_name == path.stem == logical_name
                        and _is_normalized_agent_slug(declared_name)
                    ),
                    "description_present": bool(metadata.get("description")),
                    "paired_counterpart_exists": logical_name in loaded[other_platform],
                    "paired_contract_parity": paired_contract_parity(logical_name),
                    "input_output_review_contract": all(
                        marker in lower for marker in ["input contract", "output contract", "review boundary"]
                    ),
                    "safety_language": "do not" in lower or "never" in lower,
                    "evidence_language": any(
                        marker in lower for marker in ["provenance", "missing evidence", "unknown", "disagreement"]
                    ),
                }
                if alias_spec is not None:
                    canonical_record = single_record(platform, canonical_name)
                    try:
                        removal_key = _semver_key(str(alias_spec.get("remove_in", "")))
                    except ValueError:
                        removal_key = (0, 0, 0)
                    checks.update(
                        {
                            "deprecated_alias_description": (
                                _normalized_description(
                                    metadata.get("description", "")
                                )
                                == _normalized_description(
                                    _deprecated_alias_description(
                                        canonical_name,
                                        str(alias_spec.get("remove_in", "")),
                                    )
                                )
                            ),
                            "alias_platform_declared": (
                                platform in alias_spec.get("platforms", [])
                            ),
                            "one_hop_alias_resolution": (
                                canonical_name not in alias_names
                                and canonical_name != logical_name
                            ),
                            "behaviorally_equivalent_to_canonical": (
                                canonical_record is not None
                                and _contract_fingerprint(instructions)
                                == _contract_fingerprint(
                                    canonical_record["instructions"]
                                )
                            ),
                            "alias_not_expired": version_key < removal_key,
                        }
                    )
                issues = list(parse_errors)
                issues.extend(f"failed contract check: {name}" for name, passed in checks.items() if not passed)
                rows.append(
                    {
                        "path": _relative(path),
                        "platform": platform,
                        "name": logical_name,
                        "canonical_name": canonical_name,
                        "is_deprecated_alias": is_alias,
                        "score": _mean([float(value) for value in checks.values()]),
                        "checks": checks,
                        "issues": issues,
                    }
                )

    all_names = set(logical_paths["codex"]) | set(logical_paths["claude"])
    for name in sorted(all_names):
        present = [platform for platform, groups in logical_paths.items() if name in groups]
        if len(present) != len(logical_paths):
            inventory_issues.append(f"unpaired agent {name}: present only in {', '.join(present)}")
    return rows, inventory_issues


def evaluate_repository(
    project_version: str | None = None,
    alias_registry_path: Path = AGENT_ALIAS_REGISTRY,
) -> dict[str, Any]:
    skills, skill_issues = evaluate_skills()
    all_agents, agent_issues = evaluate_agents(
        project_version=project_version,
        alias_registry_path=alias_registry_path,
    )
    agents = [row for row in all_agents if not row["is_deprecated_alias"]]
    agent_aliases = [row for row in all_agents if row["is_deprecated_alias"]]
    inventory_issues = skill_issues + agent_issues
    paired_skill_names = sorted(
        {row["name"] for row in skills if row["platform"] == "codex"}
        & {row["name"] for row in skills if row["platform"] == "claude"}
    )
    paired_agent_names = sorted(
        {row["name"] for row in agents if row["platform"] == "codex"}
        & {row["name"] for row in agents if row["platform"] == "claude"}
    )
    paired_alias_names = sorted(
        {row["name"] for row in agent_aliases if row["platform"] == "codex"}
        & {row["name"] for row in agent_aliases if row["platform"] == "claude"}
    )
    paired_addressable_names = sorted(set(paired_agent_names) | set(paired_alias_names))
    return {
        "summary": {
            "skill_files": len(skills),
            "paired_skill_names": len(paired_skill_names),
            "mean_skill_structural_score": _mean([row["structural_score"] for row in skills]),
            "mean_skill_operational_score": _mean([row["operational_score"] for row in skills]),
            "agent_files": len(agents),
            "paired_agent_names": len(paired_agent_names),
            "mean_agent_contract_score": _mean([row["score"] for row in agents]),
            "deprecated_agent_alias_files": len(agent_aliases),
            "paired_deprecated_agent_alias_names": len(paired_alias_names),
            "mean_deprecated_agent_alias_contract_score": _mean(
                [row["score"] for row in agent_aliases]
            ),
            "addressable_agent_files": len(all_agents),
            "addressable_agent_names": len(
                {row["name"] for row in all_agents}
            ),
            "paired_addressable_agent_names": len(paired_addressable_names),
            "inventory_issue_count": len(inventory_issues),
        },
        "inventory_issues": inventory_issues,
        "skills": skills,
        "agents": agents,
        "agent_aliases": agent_aliases,
    }


def _skill_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Skill file | Structural | Operational | Overall | Pair | Implementation | Issues |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        pair = "pass" if row["operational_checks"]["paired_contract_exact"] else "fail"
        lines.append(
            "| `{path}` | {structural:.3f} | {operational:.3f} | {overall:.3f} | {pair} | {implementation} | {issues} |".format(
                path=row["path"],
                structural=row["structural_score"],
                operational=row["operational_score"],
                overall=row["overall_score"],
                pair=pair,
                implementation=row["implementation_status"],
                issues="; ".join(row["issues"]) or "none",
            )
        )
    return "\n".join(lines)


def _agent_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Agent file | Contract score | Pair | Issues |",
        "| --- | ---: | --- | --- |",
    ]
    for row in rows:
        pair = (
            "pass"
            if row["checks"]["paired_counterpart_exists"]
            and row["checks"]["paired_contract_parity"]
            else "fail"
        )
        lines.append(
            "| `{path}` | {score:.3f} | {pair} | {issues} |".format(
                path=row["path"],
                score=row["score"],
                pair=pair,
                issues="; ".join(row["issues"]) or "none",
            )
        )
    return "\n".join(lines)


def render_report(results: dict[str, Any]) -> str:
    summary = results["summary"]
    issues = results["inventory_issues"]
    issue_lines = "\n".join(f"- {issue}" for issue in issues) if issues else "- None."
    return f"""# Skill and Agent Evaluation Report

This deterministic audit evaluates project-scoped skill and agent contracts. It checks structure, scientific guardrails, exact normalized Codex/Claude contract parity, declared implementation paths, canonical and deprecated-alias inventories, one-hop alias safety, duplicate logical agent names, and explicit input/output/review boundaries. It does not substitute for executing every scientific workflow against independent real-world data.

## Summary

- Skill files: {summary['skill_files']} ({summary['paired_skill_names']} paired skill names).
- Mean skill structural score: {summary['mean_skill_structural_score']:.3f}.
- Mean skill operational-linkage score: {summary['mean_skill_operational_score']:.3f}.
- Canonical agent files: {summary['agent_files']} ({summary['paired_agent_names']} paired canonical names).
- Mean agent contract score: {summary['mean_agent_contract_score']:.3f}.
- Deprecated alias files: {summary['deprecated_agent_alias_files']} ({summary['paired_deprecated_agent_alias_names']} paired alias names).
- Mean deprecated-alias contract score: {summary['mean_deprecated_agent_alias_contract_score']:.3f}.
- Host-addressable manifests: {summary['addressable_agent_files']} ({summary['addressable_agent_names']} names).
- Inventory issues: {summary['inventory_issue_count']}.

## Inventory Issues

{issue_lines}

## Skill Results

{_skill_markdown(results['skills'])}

## Canonical Agent Results

{_agent_markdown(results['agents'])}

## Deprecated Agent Aliases

{_agent_markdown(results['agent_aliases'])}
"""


def main() -> None:
    results = evaluate_repository()
    docs_dir = ROOT / "docs"
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / "skill_evaluation_results.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (docs_dir / "skill_evaluation_report.md").write_text(
        render_report(results),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
