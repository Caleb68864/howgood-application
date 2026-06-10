import hashlib
import hmac
import json
from pathlib import Path

import pytest
import yaml

from apply_howgood import (
    ApplicationConfig,
    canonical_json,
    get_secret,
    load_config,
    sign_body,
    validate_config,
    validate_payload,
)


TEST_SECRET = "test-secret"


def valid_payload():
    return {
        "name": "Test User",
        "email": "test@example.com",
        "resume": "https://example.com/resume.pdf",
        "location": "Test City, Test State, United States",
        "linkedin": "https://www.linkedin.com/in/test-user/",
        "codeLink": "https://github.com/example/howgood-application",
        "yearsPython": 8,
        "yearsDjango": 0,
        "repos": "https://github.com/example",
        "notes": "Test notes.",
    }


def valid_config():
    return ApplicationConfig(
        endpoint="https://api.example.com/apply",
        default_secret=TEST_SECRET,
        secret_env_var="TEST_APPLICATION_HMAC_SECRET",
        payload=valid_payload(),
    )


def test_config_and_payload_are_valid():
    config = valid_config()

    assert validate_config(config) == []
    assert validate_payload(config.payload) == []


def test_canonical_json_is_deterministic():
    payload = {
        "b": 2,
        "a": 1,
    }

    assert canonical_json(payload) == '{"a":1,"b":2}'


def test_signature_matches_python_hmac_reference():
    raw_body = '{"a":1,"b":2}'

    expected = hmac.new(
        TEST_SECRET.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert sign_body(raw_body, TEST_SECRET) == expected


def test_payload_body_can_round_trip_from_json():
    payload = valid_payload()
    raw_body = canonical_json(payload)

    assert json.loads(raw_body) == payload


def test_load_config_from_yaml(tmp_path: Path):
    config_path = tmp_path / "application.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "api": {
                    "endpoint": "https://api.example.com/apply",
                    "defaultSecret": TEST_SECRET,
                    "secretEnvVar": "TEST_APPLICATION_HMAC_SECRET",
                },
                "payload": valid_payload(),
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.endpoint == "https://api.example.com/apply"
    assert config.default_secret == TEST_SECRET
    assert config.secret_env_var == "TEST_APPLICATION_HMAC_SECRET"
    assert config.payload == valid_payload()


def test_load_config_accepts_snake_case_api_keys(tmp_path: Path):
    config_path = tmp_path / "application.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "api": {
                    "endpoint": "https://api.example.com/apply",
                    "default_secret": TEST_SECRET,
                    "secret_env_var": "TEST_APPLICATION_HMAC_SECRET",
                },
                "payload": valid_payload(),
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.default_secret == TEST_SECRET
    assert config.secret_env_var == "TEST_APPLICATION_HMAC_SECRET"


def test_get_secret_prefers_configured_environment_variable(monkeypatch: pytest.MonkeyPatch):
    config = valid_config()
    monkeypatch.setenv(config.secret_env_var, "override-secret")

    assert get_secret(config) == "override-secret"


def test_get_secret_uses_yaml_default_when_environment_variable_is_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    config = valid_config()
    monkeypatch.delenv(config.secret_env_var, raising=False)

    assert get_secret(config) == TEST_SECRET


def test_invalid_endpoint_fails_validation():
    config = ApplicationConfig(
        endpoint="not-a-url",
        default_secret=TEST_SECRET,
        secret_env_var="TEST_APPLICATION_HMAC_SECRET",
        payload=valid_payload(),
    )

    errors = validate_config(config)

    assert "api.endpoint must be a valid http(s) URL" in errors


def test_invalid_email_fails_validation():
    payload = valid_payload()
    payload["email"] = "not-an-email"

    errors = validate_payload(payload)

    assert "email must look like a valid email address" in errors


def test_missing_required_field_fails_validation():
    payload = valid_payload()
    payload["resume"] = ""

    errors = validate_payload(payload)

    assert "resume is required and must be a non-empty string" in errors


def test_negative_years_fail_validation():
    payload = valid_payload()
    payload["yearsPython"] = -1

    errors = validate_payload(payload)

    assert "yearsPython must be a non-negative integer" in errors
