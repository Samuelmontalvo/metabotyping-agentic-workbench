"""Deterministic semantic validation for advisory domain review packets.

JSON Schema checks shape when ``jsonschema`` is installed.  These checks cover
the safety-critical semantics with the Python standard library as well, so an
offline fallback cannot silently weaken the review boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from enum import Enum
from typing import Any

from .models import (
    DOMAIN_REVIEW_CONTRACT_VERSION,
    DOMAIN_REVIEW_SCHEMA_VERSION,
    ROLE_REVIEW_DIMENSIONS,
    DecisionAuthority,
    DomainReviewRole,
    EvidenceState,
    HumanAdjudicationStatus,
)

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")

_ROOT_KEYS = {
    "schema_version",
    "contract_version",
    "packet_id",
    "scope_version",
    "role",
    "research_question",
    "intended_use",
    "referenced_entities",
    "provenance",
    "evidence",
    "limitations",
    "blockers",
    "human_review_questions",
    "decision_authority",
    "human_adjudication_status",
    "executable_actions",
    "packet_digest",
}
_ENTITY_KEYS = {"study_ids", "dataset_ids", "variable_ids", "effect_ids"}
_PROVENANCE_KEYS = {
    "provenance_id",
    "source_artifact",
    "record_locator",
    "source_sha256",
    "extraction_method",
}
_EVIDENCE_KEYS = {
    "evidence_id",
    "dimension",
    "state",
    "detail",
    "provenance_ids",
}
_LIMITATION_KEYS = {"limitation_id", "description", "evidence_ids"}
_BLOCKER_KEYS = {"blocker_id", "description", "evidence_ids"}
_QUESTION_KEYS = {"question_id", "question", "evidence_ids"}

_ID_KEY_BY_COLLECTION = {
    "provenance": "provenance_id",
    "evidence": "evidence_id",
    "limitations": "limitation_id",
    "blockers": "blocker_id",
    "human_review_questions": "question_id",
}
_FORBIDDEN_FIELD_NAMES = {
    "accepted",
    "rejected",
    "acceptance",
    "rejection",
    "confidence",
    "approved_transform",
    "permitted_analysis",
    "pooling_authorized",
    "confidence_score",
    "confidence_scores",
    "transform",
    "transforms",
    "pooling_permission",
    "pooling_permissions",
    "pooling_authorization",
    "risk_of_bias_score",
    "risk_of_bias_scores",
    "meta_analytic_result",
    "meta_analytic_results",
    "meta_analysis_result",
    "meta_analysis_results",
    "pooled_estimate",
    "pooled_effect",
    "effect_calculation",
}
_TIME_FIELD_NAMES = {
    "created_at",
    "generated_at",
    "updated_at",
    "timestamp",
}
_EVIDENCE_STATES_REQUIRING_PROVENANCE = {
    EvidenceState.REPORTED.value,
    EvidenceState.DOCUMENTED_ABSENT.value,
    EvidenceState.CONFLICTING.value,
}
_AUTHORITY_PROSE_FIELDS = {"intended_use", "detail", "description"}
_AUTHORITY_STATEMENT_PATTERNS = (
    (
        "acceptance or rejection decision",
        re.compile(
            r"\b(?:accept|reject)(?:s|ed|ing)?\s+"
            r"(?:(?:this|the|a|an)\s+)?"
            r"(?:mapping|dataset|study|evidence|candidate)\b|"
            r"\b(?:mapping|dataset|study|evidence|candidate)\s+"
            r"(?:(?:is|was|has been|should be|must be|can be|may be|will be)\s+)?"
            r"(?:accepted|rejected)\b|"
            r"\b(?:acceptance|rejection)\s+(?:is\s+)?"
            r"(?:recommended|approved|authorized|final|warranted)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "confidence score",
        re.compile(
            r"\bconfidence(?:\s+score)?\s*"
            r"(?:(?:is|=|:)\s*)?"
            r"(?:0(?:\.\d+)?|1(?:\.0+)?|high|medium|low)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "approved transform",
        re.compile(
            r"\b(?:transform(?:ation)?\s+(?:is\s+)?"
            r"(?:approved|authorized|permitted|allowed)|"
            r"(?:approved|authorized|permitted|allowed)\s+transform)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "pooling permission",
        re.compile(
            r"\b(?:pooling\s+(?:is\s+)?"
            r"(?:approved|authorized|permitted|allowed)|"
            r"(?:approve|authorize|permit|allow)(?:s|ed|ing)?\s+"
            r"(?:\w+\s+){0,3}pooling)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "risk-of-bias score",
        re.compile(
            r"\brisk[-_ ]of[-_ ]bias\s+score\s*"
            r"(?:(?:is|=|:)\s*)?(?:\d+(?:\.\d+)?|high|medium|low)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "meta-analytic result",
        re.compile(
            r"\b(?:meta[-_ ]analytic\s+(?:result|estimate)|"
            r"pooled\s+(?:result|estimate|effect))\s*"
            r"(?:(?:is|=|:)\s*)?\S+",
            re.IGNORECASE,
        ),
    ),
)


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        model = value
        dumped = model.model_dump()
        for key in list(dumped):
            if hasattr(model, key):
                dumped[key] = _plain(getattr(model, key))
        for key, item in getattr(model, "__dict__", {}).items():
            if not key.startswith("_") and key not in dumped:
                dumped[key] = _plain(item)
        pydantic_extra = getattr(model, "__pydantic_extra__", None)
        if isinstance(pydantic_extra, dict):
            for key, item in pydantic_extra.items():
                dumped[key] = _plain(item)
        return dumped
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canonicalize(value: Any, *, field_name: str = "") -> Any:
    """Canonicalize unordered, ID-keyed packet collections without mutation."""

    value = _plain(value)
    if isinstance(value, dict):
        return {
            key: _canonicalize(item, field_name=key)
            for key, item in sorted(value.items())
            if key != "packet_digest"
        }
    if isinstance(value, list):
        items = [_canonicalize(item) for item in value]
        id_key = _ID_KEY_BY_COLLECTION.get(field_name)
        if id_key and all(isinstance(item, dict) for item in items):
            return sorted(
                items,
                key=lambda item: (
                    str(item.get(id_key, "")),
                    _canonical_json(item),
                ),
            )
        if field_name.endswith("_ids") or all(
            isinstance(item, (str, int, float, bool)) or item is None for item in items
        ):
            return sorted(items, key=_canonical_json)
        return items
    return value


def build_packet_digest(packet_without_digest: Any) -> str:
    """Return a stable SHA-256 over packet scope, evidence, and provenance.

    ``packet_digest`` is ignored when present.  ID-keyed collections and
    reference-ID lists are sorted before serialization, making the digest
    independent of harmless input ordering.
    """

    canonical = _canonicalize(packet_without_digest)
    payload = _canonical_json(canonical).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value
    return str(value).strip() if value is not None else ""


def _mapping(value: Any) -> dict[str, Any] | None:
    value = _plain(value)
    return value if isinstance(value, dict) else None


def _check_object_keys(
    value: dict[str, Any],
    *,
    expected: set[str],
    label: str,
    errors: list[str],
) -> None:
    missing = sorted(expected - set(value))
    extra = sorted(set(value) - expected)
    if missing:
        errors.append(f"{label} missing required fields: {', '.join(missing)}")
    if extra:
        errors.append(f"{label} contains unsupported fields: {', '.join(extra)}")


def _check_nonempty_text(
    value: Any,
    *,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a nonempty string")


def _check_string_id_list(
    value: Any,
    *,
    label: str,
    errors: list[str],
    require_nonempty: bool = False,
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    if require_nonempty and not value:
        errors.append(f"{label} must contain at least one ID")
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}[{index}] must be a nonempty string")
        else:
            result.append(item)
    if len(result) != len(set(result)):
        errors.append(f"{label} contains duplicate IDs")
    if result != sorted(result):
        errors.append(f"{label} must use stable sorted ordering")
    return result


def _check_id_order(
    rows: list[dict[str, Any]],
    *,
    id_key: str,
    label: str,
    errors: list[str],
) -> None:
    ids = [row.get(id_key) for row in rows]
    valid_ids = [item for item in ids if isinstance(item, str) and item.strip()]
    if len(valid_ids) != len(set(valid_ids)):
        errors.append(f"{label} contains duplicate {id_key} values")
    if len(valid_ids) == len(rows) and valid_ids != sorted(valid_ids):
        errors.append(f"{label} must use stable {id_key} ordering")


def _iter_object_rows(
    value: Any,
    *,
    label: str,
    expected_keys: set[str],
    errors: list[str],
    require_nonempty: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    if require_nonempty and not value:
        errors.append(f"{label} must contain at least one item")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        row = _mapping(item)
        if row is None:
            errors.append(f"{label}[{index}] must be an object")
            continue
        _check_object_keys(
            row,
            expected=expected_keys,
            label=f"{label}[{index}]",
            errors=errors,
        )
        rows.append(row)
    return rows


def _scan_for_forbidden_fields(
    value: Any,
    *,
    path: str,
    errors: list[str],
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}" if path else key
            normalized_key = key.lower()
            prohibited_decision_field = (
                key in _FORBIDDEN_FIELD_NAMES
                or "acceptance" in normalized_key
                or "rejection" in normalized_key
                or "confidence" in normalized_key
                or "transform" in normalized_key
                or (
                    "pooling" in normalized_key
                    and any(
                        token in normalized_key
                        for token in ("allow", "authoriz", "combinable", "permission")
                    )
                )
                or (
                    "risk_of_bias" in normalized_key
                    and "score" in normalized_key
                )
                or (
                    any(
                        token in normalized_key
                        for token in ("meta_analytic", "meta_analysis")
                    )
                    and any(
                        token in normalized_key
                        for token in ("effect", "estimate", "result")
                    )
                )
                or (
                    normalized_key.startswith("pooled_")
                    and any(
                        token in normalized_key
                        for token in ("effect", "estimate", "result")
                    )
                )
            )
            if prohibited_decision_field:
                errors.append(
                    f"{item_path} is prohibited in an advisory-only review packet"
                )
            if key in _TIME_FIELD_NAMES or key.endswith("_timestamp"):
                errors.append(f"{item_path} is a prohibited nondeterministic time field")
            _scan_for_forbidden_fields(item, path=item_path, errors=errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_for_forbidden_fields(
                item,
                path=f"{path}[{index}]",
                errors=errors,
            )
    elif isinstance(value, str):
        field_name = path.rsplit(".", 1)[-1]
        if field_name not in _AUTHORITY_PROSE_FIELDS:
            return
        review_authored_text = re.sub(
            r"\b(?:without|cannot|never|must not|do not|does not|did not)\b"
            r"[^.;!?]*",
            "",
            value,
            flags=re.IGNORECASE,
        )
        for label, pattern in _AUTHORITY_STATEMENT_PATTERNS:
            if pattern.search(review_authored_text):
                errors.append(
                    f"{path} contains a prohibited advisory authority statement: "
                    f"{label}"
                )


def validate_domain_review_packet(packet: Any) -> list[str]:
    """Return contract-integrity errors without making a scientific decision."""

    data = _mapping(packet)
    if data is None:
        return ["domain review packet must be an object"]

    errors: list[str] = []
    _check_object_keys(data, expected=_ROOT_KEYS, label="packet", errors=errors)
    _scan_for_forbidden_fields(data, path="packet", errors=errors)

    if data.get("schema_version") != DOMAIN_REVIEW_SCHEMA_VERSION:
        errors.append(
            "schema_version must equal "
            f"{DOMAIN_REVIEW_SCHEMA_VERSION!r}"
        )
    if data.get("contract_version") != DOMAIN_REVIEW_CONTRACT_VERSION:
        errors.append(
            "contract_version must equal "
            f"{DOMAIN_REVIEW_CONTRACT_VERSION!r}"
        )
    _check_nonempty_text(data.get("packet_id"), label="packet_id", errors=errors)
    _check_nonempty_text(
        data.get("scope_version"),
        label="scope_version",
        errors=errors,
    )
    _check_nonempty_text(
        data.get("research_question"),
        label="research_question",
        errors=errors,
    )
    _check_nonempty_text(data.get("intended_use"), label="intended_use", errors=errors)

    role = _text(data.get("role"))
    known_roles = {item.value for item in DomainReviewRole}
    if role not in known_roles:
        errors.append(f"unsupported domain review role: {role or '<missing>'}")

    entities = _mapping(data.get("referenced_entities"))
    entity_ids: list[str] = []
    if entities is None:
        errors.append("referenced_entities must be an object")
    else:
        _check_object_keys(
            entities,
            expected=_ENTITY_KEYS,
            label="referenced_entities",
            errors=errors,
        )
        for key in sorted(_ENTITY_KEYS):
            entity_ids.extend(
                _check_string_id_list(
                    entities.get(key),
                    label=f"referenced_entities.{key}",
                    errors=errors,
                )
            )
        if not entity_ids:
            errors.append("referenced_entities must identify at least one scoped entity")

    provenance_rows = _iter_object_rows(
        data.get("provenance"),
        label="provenance",
        expected_keys=_PROVENANCE_KEYS,
        errors=errors,
        require_nonempty=True,
    )
    _check_id_order(
        provenance_rows,
        id_key="provenance_id",
        label="provenance",
        errors=errors,
    )
    provenance_ids: set[str] = set()
    for index, row in enumerate(provenance_rows):
        prefix = f"provenance[{index}]"
        for key in (
            "provenance_id",
            "source_artifact",
            "record_locator",
            "extraction_method",
        ):
            _check_nonempty_text(row.get(key), label=f"{prefix}.{key}", errors=errors)
        provenance_id = row.get("provenance_id")
        if isinstance(provenance_id, str) and provenance_id.strip():
            provenance_ids.add(provenance_id)
        source_sha256 = row.get("source_sha256")
        if not isinstance(source_sha256, str) or not _SHA256_RE.fullmatch(source_sha256):
            errors.append(f"{prefix}.source_sha256 must be a lowercase SHA-256")

    evidence_rows = _iter_object_rows(
        data.get("evidence"),
        label="evidence",
        expected_keys=_EVIDENCE_KEYS,
        errors=errors,
        require_nonempty=True,
    )
    _check_id_order(
        evidence_rows,
        id_key="evidence_id",
        label="evidence",
        errors=errors,
    )
    evidence_ids: set[str] = set()
    covered_dimensions: set[str] = set()
    known_states = {item.value for item in EvidenceState}
    for index, row in enumerate(evidence_rows):
        prefix = f"evidence[{index}]"
        for key in ("evidence_id", "dimension", "detail"):
            _check_nonempty_text(row.get(key), label=f"{prefix}.{key}", errors=errors)
        evidence_id = row.get("evidence_id")
        if isinstance(evidence_id, str) and evidence_id.strip():
            evidence_ids.add(evidence_id)
        dimension = row.get("dimension")
        if isinstance(dimension, str) and dimension.strip():
            covered_dimensions.add(dimension)
        state = _text(row.get("state"))
        if state not in known_states:
            errors.append(f"{prefix}.state is unsupported: {state or '<missing>'}")
        linked_provenance = _check_string_id_list(
            row.get("provenance_ids"),
            label=f"{prefix}.provenance_ids",
            errors=errors,
        )
        dangling = sorted(set(linked_provenance) - provenance_ids)
        if dangling:
            errors.append(
                f"{prefix}.provenance_ids contains unresolved references: "
                f"{', '.join(dangling)}"
            )
        if state in _EVIDENCE_STATES_REQUIRING_PROVENANCE and not linked_provenance:
            errors.append(f"{prefix} with state {state!r} requires provenance")

    if role in ROLE_REVIEW_DIMENSIONS:
        required_dimensions = set(ROLE_REVIEW_DIMENSIONS[role])
        missing_dimensions = sorted(required_dimensions - covered_dimensions)
        unknown_dimensions = sorted(covered_dimensions - required_dimensions)
        if missing_dimensions:
            errors.append(
                "evidence is missing required role dimensions: "
                + ", ".join(missing_dimensions)
            )
        if unknown_dimensions:
            errors.append(
                "evidence contains dimensions outside the role profile: "
                + ", ".join(unknown_dimensions)
            )

    linked_collections = (
        (
            "limitations",
            _LIMITATION_KEYS,
            "limitation_id",
            "description",
            False,
        ),
        ("blockers", _BLOCKER_KEYS, "blocker_id", "description", False),
        (
            "human_review_questions",
            _QUESTION_KEYS,
            "question_id",
            "question",
            True,
        ),
    )
    for collection, keys, id_key, text_key, require_nonempty in linked_collections:
        rows = _iter_object_rows(
            data.get(collection),
            label=collection,
            expected_keys=keys,
            errors=errors,
            require_nonempty=require_nonempty,
        )
        _check_id_order(
            rows,
            id_key=id_key,
            label=collection,
            errors=errors,
        )
        for index, row in enumerate(rows):
            prefix = f"{collection}[{index}]"
            _check_nonempty_text(row.get(id_key), label=f"{prefix}.{id_key}", errors=errors)
            _check_nonempty_text(
                row.get(text_key),
                label=f"{prefix}.{text_key}",
                errors=errors,
            )
            linked_evidence = _check_string_id_list(
                row.get("evidence_ids"),
                label=f"{prefix}.evidence_ids",
                errors=errors,
                require_nonempty=True,
            )
            dangling = sorted(set(linked_evidence) - evidence_ids)
            if dangling:
                errors.append(
                    f"{prefix}.evidence_ids contains unresolved references: "
                    f"{', '.join(dangling)}"
                )

    if _text(data.get("decision_authority")) != DecisionAuthority.ADVISORY_ONLY.value:
        errors.append("decision_authority must remain 'advisory_only'")
    if (
        _text(data.get("human_adjudication_status"))
        != HumanAdjudicationStatus.REQUIRED.value
    ):
        errors.append("human_adjudication_status must remain 'required'")
    executable_actions = data.get("executable_actions")
    if not isinstance(executable_actions, list):
        errors.append("executable_actions must be a list")
    elif executable_actions:
        errors.append("executable_actions must be empty for advisory-only review")

    packet_digest = data.get("packet_digest")
    if not isinstance(packet_digest, str) or not _SHA256_RE.fullmatch(packet_digest):
        errors.append("packet_digest must be a lowercase SHA-256")
    else:
        expected_digest = build_packet_digest(data)
        if packet_digest != expected_digest:
            errors.append(
                "packet_digest does not match the canonical packet content "
                f"(expected {expected_digest})"
            )

    return errors


def validate_domain_review_packet_or_raise(packet: Any) -> None:
    """Raise ``ValueError`` when packet contract integrity is invalid."""

    errors = validate_domain_review_packet(packet)
    if errors:
        raise ValueError("domain review packet failed validation: " + "; ".join(errors))
