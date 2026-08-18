"""Approved deterministic transform descriptions."""

APPROVED_TRANSFORMS = {
    "identity": "Copy source value without transformation after schema validation.",
    "multiply_by_18.0182": "Convert fasting glucose from mmol/L to mg/dL.",
}


def is_transform_approved(name: str) -> bool:
    return name in APPROVED_TRANSFORMS

