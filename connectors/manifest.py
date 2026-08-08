"""Connector manifest loading and validation (B3).

Manifests are validated against schemas/connector-manifest.schema.json.
required_secret_handles are opaque NAMES; values live only in the sealed
secret provider and never enter manifests or model context.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMAS_DIR = os.path.normpath(os.path.join(HERE, "..", "schemas"))

MANIFEST_SCHEMA = os.path.join(SCHEMAS_DIR, "connector-manifest.schema.json")


class ManifestError(ValueError):
    pass


def load_manifest(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def validate_manifest(manifest, validator_factory=None):
    """Validate a manifest dict against the connector-manifest schema.

    validator_factory: callable(schema_dict) -> jsonschema validator, used by
    tests to inject jsonschema (ephemeral dep). If None, only structural
    checks run (used by runtime paths without jsonschema installed).
    """
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be an object")
    if validator_factory is not None:
        import json

        with open(MANIFEST_SCHEMA, encoding="utf-8") as fh:
            schema = json.load(fh)
        validator = validator_factory(schema)
        errors = sorted(validator.iter_errors(manifest), key=lambda e: str(e.path))
        if errors:
            raise ManifestError("; ".join(e.message for e in errors))
    required = {
        "connector_id", "platform", "version", "connector_mode",
        "supported_event_types", "supported_permissions",
        "required_secret_handles", "rate_limits", "data_retention",
        "provenance_method", "health_check", "revocation_method",
        "risk_class", "approval_state", "checksum", "maintainer",
        "license", "status",
    }
    missing = required - set(manifest)
    if missing:
        raise ManifestError("missing fields: %s" % ", ".join(sorted(missing)))
    return manifest
