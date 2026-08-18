"""Advisory-only scientific domain review contracts."""

from pathlib import Path

from .models import (
    DOMAIN_REVIEW_CONTRACT_VERSION,
    DOMAIN_REVIEW_SCHEMA_VERSION,
    ROLE_REVIEW_DIMENSIONS,
    DecisionAuthority,
    DomainReviewPacket,
    DomainReviewRole,
    EvidenceItem,
    EvidenceState,
    HumanAdjudicationStatus,
    HumanReviewQuestion,
    ProvenanceRecord,
    ReferencedEntities,
    ReviewBlocker,
    ReviewLimitation,
)
from .validation import (
    build_packet_digest,
    validate_domain_review_packet,
    validate_domain_review_packet_or_raise,
)


def domain_review_schema_path() -> Path:
    """Return the packaged JSON Schema for :class:`DomainReviewPacket`."""

    return Path(__file__).with_name("schemas") / "domain_review_packet.schema.json"


__all__ = [
    "DOMAIN_REVIEW_CONTRACT_VERSION",
    "DOMAIN_REVIEW_SCHEMA_VERSION",
    "ROLE_REVIEW_DIMENSIONS",
    "DecisionAuthority",
    "DomainReviewPacket",
    "DomainReviewRole",
    "EvidenceItem",
    "EvidenceState",
    "HumanAdjudicationStatus",
    "HumanReviewQuestion",
    "ProvenanceRecord",
    "ReferencedEntities",
    "ReviewBlocker",
    "ReviewLimitation",
    "build_packet_digest",
    "domain_review_schema_path",
    "validate_domain_review_packet",
    "validate_domain_review_packet_or_raise",
]
