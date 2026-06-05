import muesli_engine.secrets as secrets


class FakeKeyring:
    def __init__(self):
        self.store = {}

    def set_password(self, service, user, password):
        self.store[(service, user)] = password

    def get_password(self, service, user):
        return self.store.get((service, user))

    def delete_password(self, service, user):
        self.store.pop((service, user), None)


def test_set_get_delete_roundtrip(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(secrets, "keyring", fake)
    assert secrets.get_api_key("openai") is None
    secrets.set_api_key("openai", "sk-123")
    assert secrets.get_api_key("openai") == "sk-123"
    secrets.delete_api_key("openai")
    assert secrets.get_api_key("openai") is None


def test_keys_are_namespaced_per_provider(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr(secrets, "keyring", fake)
    secrets.set_api_key("openai", "sk-openai")
    secrets.set_api_key("anthropic", "sk-anthropic")
    assert secrets.get_api_key("openai") == "sk-openai"
    assert secrets.get_api_key("anthropic") == "sk-anthropic"
