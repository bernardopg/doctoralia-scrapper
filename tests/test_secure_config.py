from pathlib import Path
from typing import Any, Dict

from src.secure_config import ENCRYPTED_PREFIX, ConfigValidator, SecureConfig


def test_encrypt_decrypt_round_trip(tmp_path: Path):
    cfg_file = tmp_path / "config.json"
    sc = SecureConfig(cfg_file, password="fixed-password")
    original: Dict[str, Any] = {
        "telegram": {"token": "bot123456:ABC", "chat_id": "123456", "enabled": True},
        "database": {"password": "secret_pass", "host": "localhost"},
        "normal": "value",
    }
    enc = sc.encrypt_sensitive_data(original)
    # Sensitive fields should be prefixed
    assert enc["telegram"]["token"].startswith(ENCRYPTED_PREFIX)
    assert enc["database"]["password"].startswith(ENCRYPTED_PREFIX)
    assert enc["telegram"]["chat_id"].startswith(ENCRYPTED_PREFIX)

    dec = sc.decrypt_sensitive_data(enc)
    assert dec["telegram"]["token"] == original["telegram"]["token"]
    assert dec["database"]["password"] == original["database"]["password"]
    assert dec["telegram"]["chat_id"] == original["telegram"]["chat_id"]
    assert dec["normal"] == "value"


def test_save_and_load_secure_config(tmp_path: Path):
    cfg_file = tmp_path / "secure.json"
    sc = SecureConfig(cfg_file, password="pwd")
    data = {"telegram": {"token": "bot999:XYZ", "chat_id": "777", "enabled": False}}
    sc.save_secure_config(data)
    loaded = sc.load_secure_config()
    assert loaded["telegram"]["token"] == data["telegram"]["token"]
    assert loaded["telegram"]["chat_id"] == data["telegram"]["chat_id"]


def test_config_validator_telegram_encrypted():
    assert ConfigValidator.validate_telegram_config("encrypted:ABCDEF", "encrypted:123")
    assert ConfigValidator.validate_telegram_config("bot123456:ABC", "123456")
    assert ConfigValidator.validate_telegram_config("bot123456:ABC", "@canal")
    assert not ConfigValidator.validate_telegram_config("badtoken", "123")
    assert not ConfigValidator.validate_telegram_config("", "")


def test_sanitize_input_limits_length():
    long = "x" * 1500
    sanitized = ConfigValidator.sanitize_input(long, max_length=1000)
    assert len(sanitized) == 1000
    dirty = "<script>alert('x')</script>"
    clean = ConfigValidator.sanitize_input(dirty)
    assert "<" not in clean and ">" not in clean
