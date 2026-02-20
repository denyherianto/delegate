"""Tests for network allowlist management."""

import pytest

from delegate.network import (
    DEFAULT_DOMAINS,
    PKG_CACHE_ENV_VARS,
    _validate_domain,
    allow_domain,
    build_cache_env,
    disallow_domain,
    get_allowed_domains,
    load_config,
    reset_config,
    save_config,
)
from delegate.paths import network_config_path


@pytest.fixture
def tmp_hc(tmp_path):
    """Provide a temporary hc_home with protected/ dir."""
    hc = tmp_path / "hc"
    hc.mkdir()
    (hc / "protected").mkdir()
    return hc


# ---------------------------------------------------------------------------
# Domain validation
# ---------------------------------------------------------------------------

class TestDomainValidation:
    def test_simple_domain(self):
        _validate_domain("example.com")

    def test_subdomain(self):
        _validate_domain("api.github.com")

    def test_wildcard_subdomain(self):
        _validate_domain("*.openai.com")

    def test_hyphenated_domain(self):
        _validate_domain("my-service.example.com")

    def test_invalid_domain_rejects_spaces(self):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            _validate_domain("not a domain")

    def test_invalid_domain_rejects_slashes(self):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            _validate_domain("http://example.com")

    def test_invalid_domain_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            _validate_domain("")

    def test_invalid_domain_rejects_port(self):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            _validate_domain("example.com:8080")

    def test_bare_wildcard_rejected(self):
        """Bare '*' is no longer valid — use explicit domains."""
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            _validate_domain("*")


# ---------------------------------------------------------------------------
# Config read/write
# ---------------------------------------------------------------------------

class TestConfig:
    def test_default_when_no_file(self, tmp_hc):
        """Returns curated default list when file doesn't exist."""
        config = load_config(tmp_hc)
        assert config["allowedDomains"] == DEFAULT_DOMAINS

    def test_save_and_load(self, tmp_hc):
        """Can save and load a config."""
        save_config(tmp_hc, {"allowedDomains": ["example.com"]})
        config = load_config(tmp_hc)
        assert config["allowedDomains"] == ["example.com"]

    def test_corrupt_file_returns_defaults(self, tmp_hc):
        """Corrupt YAML returns defaults."""
        path = network_config_path(tmp_hc)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{{invalid yaml::")
        config = load_config(tmp_hc)
        assert config["allowedDomains"] == DEFAULT_DOMAINS

    def test_legacy_wildcard_migrated(self, tmp_hc):
        """Old configs with just ['*'] are migrated to the default list."""
        save_config(tmp_hc, {"allowedDomains": ["*"]})
        config = load_config(tmp_hc)
        assert config["allowedDomains"] == DEFAULT_DOMAINS
        # Also verify it was persisted (not just in-memory)
        config2 = load_config(tmp_hc)
        assert config2["allowedDomains"] == DEFAULT_DOMAINS


# ---------------------------------------------------------------------------
# Allow / disallow / reset
# ---------------------------------------------------------------------------

class TestAllowDomain:
    def test_allow_appends_to_defaults(self, tmp_hc):
        """Adding a domain appends to the default list."""
        result = allow_domain(tmp_hc, "custom.example.com")
        assert "custom.example.com" in result
        # All defaults should still be there
        for d in DEFAULT_DOMAINS:
            assert d in result

    def test_allow_appends_to_custom(self, tmp_hc):
        """Adding a second custom domain appends."""
        save_config(tmp_hc, {"allowedDomains": ["example.com"]})
        result = allow_domain(tmp_hc, "api.github.com")
        assert set(result) == {"example.com", "api.github.com"}

    def test_allow_idempotent(self, tmp_hc):
        """Adding same domain twice is a no-op."""
        save_config(tmp_hc, {"allowedDomains": ["example.com"]})
        result = allow_domain(tmp_hc, "example.com")
        assert result == ["example.com"]

    def test_allow_wildcard_domain(self, tmp_hc):
        """Can add wildcard subdomain patterns."""
        save_config(tmp_hc, {"allowedDomains": ["example.com"]})
        result = allow_domain(tmp_hc, "*.openai.com")
        assert "*.openai.com" in result

    def test_allow_invalid_domain_raises(self, tmp_hc):
        with pytest.raises(ValueError, match="Invalid domain pattern"):
            allow_domain(tmp_hc, "not valid!")


class TestDisallowDomain:
    def test_disallow_removes(self, tmp_hc):
        """Can remove a domain."""
        save_config(tmp_hc, {"allowedDomains": ["example.com", "api.github.com"]})
        result = disallow_domain(tmp_hc, "example.com")
        assert result == ["api.github.com"]

    def test_disallow_to_empty_is_ok(self, tmp_hc):
        """Can remove the last domain — results in empty list (block all)."""
        save_config(tmp_hc, {"allowedDomains": ["example.com"]})
        result = disallow_domain(tmp_hc, "example.com")
        assert result == []

    def test_disallow_nonexistent_raises(self, tmp_hc):
        """Cannot remove a domain not in the list."""
        save_config(tmp_hc, {"allowedDomains": ["example.com"]})
        with pytest.raises(ValueError, match="not in the allowlist"):
            disallow_domain(tmp_hc, "other.com")


class TestReset:
    def test_reset_restores_defaults(self, tmp_hc):
        """Reset restores the curated default list."""
        save_config(tmp_hc, {"allowedDomains": ["example.com"]})
        result = reset_config(tmp_hc)
        assert result == DEFAULT_DOMAINS


# ---------------------------------------------------------------------------
# get_allowed_domains
# ---------------------------------------------------------------------------

class TestGetAllowedDomains:
    def test_returns_defaults_when_no_file(self, tmp_hc):
        result = get_allowed_domains(tmp_hc)
        assert result == DEFAULT_DOMAINS

    def test_returns_custom_list(self, tmp_hc):
        save_config(tmp_hc, {"allowedDomains": ["custom.dev"]})
        result = get_allowed_domains(tmp_hc)
        assert result == ["custom.dev"]

    def test_default_domains_contains_key_registries(self):
        """Sanity check: the default list covers major package managers."""
        assert "pypi.org" in DEFAULT_DOMAINS
        assert "registry.npmjs.org" in DEFAULT_DOMAINS
        assert "crates.io" in DEFAULT_DOMAINS
        assert "proxy.golang.org" in DEFAULT_DOMAINS
        assert "rubygems.org" in DEFAULT_DOMAINS
        assert "github.com" in DEFAULT_DOMAINS
        assert "gitlab.com" in DEFAULT_DOMAINS
        # Java / Kotlin
        assert "repo1.maven.org" in DEFAULT_DOMAINS
        assert "plugins.gradle.org" in DEFAULT_DOMAINS
        # .NET
        assert "api.nuget.org" in DEFAULT_DOMAINS
        # Swift / iOS
        assert "cdn.cocoapods.org" in DEFAULT_DOMAINS
        # Dart
        assert "pub.dev" in DEFAULT_DOMAINS
        # PHP
        assert "packagist.org" in DEFAULT_DOMAINS
        # Elixir
        assert "hex.pm" in DEFAULT_DOMAINS
        # Haskell
        assert "hackage.haskell.org" in DEFAULT_DOMAINS


# ---------------------------------------------------------------------------
# Package-manager cache env vars
# ---------------------------------------------------------------------------

class TestBuildCacheEnv:
    def test_returns_all_keys(self):
        """build_cache_env returns one entry for every template."""
        env = build_cache_env("/cache")
        assert set(env.keys()) == set(PKG_CACHE_ENV_VARS.keys())

    def test_substitutes_cache_root(self):
        """All values use the provided cache root."""
        env = build_cache_env("/team/123/.pkg-cache")
        for key, val in env.items():
            assert val.startswith("/team/123/.pkg-cache/"), f"{key}={val}"
            assert "{cache_root}" not in val

    def test_known_env_vars(self):
        """Spot-check a few well-known cache env vars."""
        env = build_cache_env("/c")
        assert env["PIP_CACHE_DIR"] == "/c/pip"
        assert env["UV_CACHE_DIR"] == "/c/uv"
        assert env["npm_config_cache"] == "/c/npm"
        assert env["CARGO_HOME"] == "/c/cargo"
        assert env["GOMODCACHE"] == "/c/gomod"
        assert env["GRADLE_USER_HOME"] == "/c/gradle"
        assert "MAVEN_REPO_LOCAL" not in env  # Maven has no env-var
        assert env["NUGET_PACKAGES"] == "/c/nuget"
        assert env["PUB_CACHE"] == "/c/pub"

    def test_path_object_accepted(self, tmp_path):
        """Can pass a Path object instead of string."""
        env = build_cache_env(tmp_path / ".pkg-cache")
        assert str(tmp_path / ".pkg-cache") in env["PIP_CACHE_DIR"]
