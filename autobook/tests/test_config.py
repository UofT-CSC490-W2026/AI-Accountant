from config import get_settings


def test_cognito_user_pool_id_accepts_legacy_env_name(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("COGNITO_USER_POOL_ID", raising=False)
    monkeypatch.setenv("COGNITO_POOL_ID", "legacy-pool-id")

    settings = get_settings()

    assert settings.COGNITO_USER_POOL_ID == "legacy-pool-id"
