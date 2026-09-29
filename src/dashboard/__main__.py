"""Permite executar o dashboard via ``python -m src.dashboard``."""

# Apply nltk security patch (CVE-2024-53889) before any nltk imports
from src.dashboard.app import start_dashboard

if __name__ == "__main__":
    start_dashboard()
