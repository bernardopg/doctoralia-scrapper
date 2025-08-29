from unittest.mock import MagicMock, patch

import pytest

from src.telegram_notifier import TelegramNotifier


@pytest.fixture
def telegram_notifier():
    mock_config = MagicMock()
    mock_config.telegram.enabled = True
    mock_config.telegram.token = "dummy_token"
    mock_config.telegram.chat_id = "dummy_chat_id"
    mock_logger = MagicMock()
    return TelegramNotifier(mock_config, mock_logger)


def test_send_message(telegram_notifier):
    # Simula uma resposta HTTP bem-sucedida
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        assert telegram_notifier.send_message("message")
