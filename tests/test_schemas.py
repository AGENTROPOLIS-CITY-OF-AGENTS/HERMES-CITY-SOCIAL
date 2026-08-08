"""Schema contract tests for HERMES-SOCIAL contracts (B2).

Run via:
  uv run --with jsonschema python -m unittest discover -s tests -v
"""
import datetime as _dt
import glob
import json
import os
import unittest

from jsonschema import Draft202012Validator

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCHEMAS = os.path.join(ROOT, "schemas")
VALID = os.path.join(SCHEMAS, "fixtures", "valid")
INVALID = os.path.join(SCHEMAS, "fixtures", "invalid")

SCHEMA_FILES = [
    "social-event.schema.json",
    "social-account.schema.json",
    "action-receipt.schema.json",
    "connector-manifest.schema.json",
    "approval-request.schema.json",
    "council-decision.schema.json",
    "community-intake.schema.json",
]

# Credential-like keys forbidden at any depth.
FORBIDDEN_KEYS = {
    "token", "secret", "password", "authorization", "cookie",
    "api_key", "apikey", "bearer", "client_secret",
}
# Secret-looking value prefixes (matches VALUES, not env-var names).
FORBIDDEN_VALUE_PREFIXES = (
    "sk-", "sk_live", "ghp_", "AKIA", "xoxb-", "xoxp-",
    "Bearer ", "-----BEGIN", "AIza",
)

NOW = _dt.datetime(2026, 8, 6, 18, 30, 0, tzinfo=_dt.timezone.utc)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def has_credential(obj):
    hits = []
    for k, v in walk(obj):
        if isinstance(k, str) and k.lower() in FORBIDDEN_KEYS:
            hits.append("key:" + k)
        if isinstance(v, str) and v.strip().startswith(FORBIDDEN_VALUE_PREFIXES):
            hits.append("value:" + k)
    return hits


def business_rules(schema_name, obj):
    """Domain business rules beyond JSON Schema. schema_name is the schema
    FILENAME (e.g. 'action-receipt.schema.json'). Returns list of violations."""
    violations = []
    if schema_name == "action-receipt.schema.json":
        if obj.get("status") == "completed" and not obj.get("provider_reference"):
            violations.append("completed receipt requires provider_reference")
    if schema_name == "approval-request.schema.json":
        if obj.get("status") == "pending":
            expires = obj.get("expires_at")
            if not expires:
                violations.append("pending approval requires expires_at")
            else:
                try:
                    exp = _dt.datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    if exp <= NOW:
                        violations.append("pending approval must not be expired")
                except ValueError:
                    violations.append("expires_at not parseable")
    if schema_name == "social-event.schema.json":
        score = obj.get("risk_score")
        level = obj.get("risk_level")
        bands = {"low": (0, 24), "moderate": (25, 49), "high": (50, 74), "critical": (75, 100)}
        if score is not None and level in bands:
            lo, hi = bands[level]
            if not (lo <= score <= hi):
                violations.append("risk_level %s does not match risk_score %s (expected %s-%s)" % (level, score, lo, hi))
    if schema_name == "social-account.schema.json":
        if obj.get("permissions", {}).get("execute") is True and obj.get("status") != "approved_execute":
            violations.append("execute permission requires status approved_execute")
    return violations


def errors(schema, obj):
    validator = Draft202012Validator(schema)
    return [e.message for e in sorted(validator.iter_errors(obj), key=lambda e: str(e.path))]


class SchemaContractTests(unittest.TestCase):
    def test_all_schemas_present(self):
        for name in SCHEMA_FILES:
            self.assertTrue(os.path.isfile(os.path.join(SCHEMAS, name)), "missing schema " + name)

    def test_schema_parse(self):
        for name in SCHEMA_FILES:
            schema = load_json(os.path.join(SCHEMAS, name))
            Draft202012Validator.check_schema(schema)

    def test_schema_version_present(self):
        for name in SCHEMA_FILES:
            schema = load_json(os.path.join(SCHEMAS, name))
            self.assertIn("schema_version", schema.get("properties", {}), name)

    def test_valid_fixtures_pass(self):
        paths = sorted(glob.glob(os.path.join(VALID, "*.json")))
        self.assertTrue(paths, "no valid fixtures")
        for path in paths:
            name = os.path.basename(path)
            schema_name = name.split(".")[0] + ".schema.json"
            schema = load_json(os.path.join(SCHEMAS, schema_name))
            obj = load_json(path)
            with self.subTest(fixture=name):
                errs = errors(schema, obj)
                self.assertEqual(errs, [], "%s: %s" % (name, errs))
                creds = has_credential(obj)
                self.assertEqual(creds, [], "%s: credential fields %s" % (name, creds))
                viol = business_rules(schema_name, obj)
                self.assertEqual(viol, [], "%s: business rules %s" % (name, viol))

    def test_invalid_fixtures_fail(self):
        paths = sorted(glob.glob(os.path.join(INVALID, "*.json")))
        self.assertTrue(paths, "no invalid fixtures")
        for path in paths:
            name = os.path.basename(path)
            schema_name = name.split(".")[0] + ".schema.json"
            schema = load_json(os.path.join(SCHEMAS, schema_name))
            obj = load_json(path)
            with self.subTest(fixture=name):
                errs = errors(schema, obj)
                creds = has_credential(obj)
                viol = business_rules(schema_name, obj)
                self.assertTrue(errs or creds or viol, "%s: expected rejection but nothing fired" % name)

    def test_forbidden_credential_scan_bites(self):
        # A fixture that deliberately leaks a credential must be caught by the scan.
        leak = load_json(os.path.join(INVALID, "social-event.credential-leak.json"))
        self.assertTrue(has_credential(leak))


if __name__ == "__main__":
    unittest.main()
