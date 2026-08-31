from __future__ import annotations

import pytest

from nebula_mcp.config import Settings, load_settings

BASE_ENV = {
    "NEBULA_ADDRESSES": "db-a:9669,db-b:9669",
    "NEBULA_USERNAME": "reader",
    "NEBULA_PASSWORD": "secret-value",
}


def test_settings_parse_defaults_and_redact_secrets() -> None:
    settings = Settings.from_env(BASE_ENV)

    assert settings.addresses == "db-a:9669,db-b:9669"
    assert settings.password.get_secret_value() == "secret-value"
    assert settings.allow_mutations is False
    assert settings.max_rows == 100
    assert "secret-value" not in repr(settings)
    assert settings.public_view() == {
        "address_count": 2,
        "username": "r***r",
        "default_schema": None,
        "default_graph": None,
        "tls_enabled": False,
        "allow_mutations": False,
    }


def test_settings_parse_boolean_and_numeric_overrides() -> None:
    settings = Settings.from_env(
        {
            **BASE_ENV,
            "NEBULA_ALLOW_MUTATIONS": "yes",
            "NEBULA_TLS_ENABLED": "1",
            "NEBULA_MAX_ROWS": "25",
        }
    )

    assert settings.allow_mutations is True
    assert settings.tls_enabled is True
    assert settings.max_rows == 25


def test_settings_reject_missing_password() -> None:
    with pytest.raises(ValueError, match="NEBULA_PASSWORD"):
        Settings.from_env({k: v for k, v in BASE_ENV.items() if k != "NEBULA_PASSWORD"})


def test_settings_reject_invalid_pool_bounds() -> None:
    with pytest.raises(ValueError, match="pool_min_size"):
        Settings.from_env(
            {
                **BASE_ENV,
                "NEBULA_POOL_MIN_SIZE": "11",
                "NEBULA_POOL_MAX_SIZE": "10",
            }
        )


@pytest.mark.parametrize("addresses", ["missing-port", "host:0", "host:65536", ":9669"])
def test_settings_reject_invalid_addresses(addresses: str) -> None:
    with pytest.raises(ValueError, match="NEBULA_ADDRESSES"):
        Settings.from_env({**BASE_ENV, "NEBULA_ADDRESSES": addresses})


def test_load_settings_reports_all_missing_required_names_without_values() -> None:
    settings, problem = load_settings({"NEBULA_USERNAME": "visible-user"})

    assert settings is None
    assert problem is not None
    assert problem.variable_names == ("NEBULA_ADDRESSES", "NEBULA_PASSWORD")
    assert "visible-user" not in problem.model_dump_json()


def test_load_settings_reports_invalid_pool_variables() -> None:
    settings, problem = load_settings(
        {
            **BASE_ENV,
            "NEBULA_POOL_MIN_SIZE": "20",
            "NEBULA_POOL_MAX_SIZE": "10",
        }
    )

    assert settings is None
    assert problem is not None
    assert problem.variable_names == ("NEBULA_POOL_MAX_SIZE", "NEBULA_POOL_MIN_SIZE")
