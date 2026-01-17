import configparser

from tldw_Server_API.app.core.Security import secret_manager as sm


def _empty_config():


    return configparser.ConfigParser()


def test_get_secret_override_does_not_mutate_config(monkeypatch):


    monkeypatch.setattr(sm, "load_comprehensive_config", _empty_config)

    manager = sm.SecretManager(validate_on_startup=False)
    manager._secret_configs = {
        "alpha": sm.SecretConfig(
            name="alpha",
            secret_type=sm.SecretType.API_KEY,
            env_var="ALPHA",
            required=True,
            default_value="default",
            min_length=1,
        )
    }
    monkeypatch.setenv("ALPHA", "abc123")

    manager.get_secret("alpha", required=False, default="override")
    manager.list_secrets()

    assert manager._secret_configs["alpha"].required is True
    assert manager._secret_configs["alpha"].default_value == "default"
