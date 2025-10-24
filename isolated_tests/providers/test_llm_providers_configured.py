import configparser

def test_llm_providers_includes_moonshot_and_zai(monkeypatch):
    from tldw_Server_API.app.api.v1.endpoints import llm_providers as mod

    def _fake_load_config():
        cfg = configparser.ConfigParser()
        cfg.add_section('API')
        cfg.set('API', 'openai_api_key', 'sk-test')
        cfg.set('API', 'openai_model', 'gpt-4o-mini')
        cfg.set('API', 'moonshot_api_key', 'msk-test')
        cfg.set('API', 'moonshot_model', 'moonshot-v1-8k')
        cfg.set('API', 'zai_api_key', 'zk-test')
        cfg.set('API', 'zai_model', 'glm-4.5-flash')
        return cfg

    monkeypatch.setattr(mod, 'load_comprehensive_config', _fake_load_config)

    result = mod.get_configured_providers()
    names = [p.get('name') for p in result.get('providers', [])]
    assert 'moonshot' in names
    assert 'zai' in names

