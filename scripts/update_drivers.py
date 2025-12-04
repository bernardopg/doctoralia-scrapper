#!/usr/bin/env python3
"""
Script para atualizar o ChromeDriver automaticamente.
Utiliza webdriver-manager para baixar a versão mais recente compatível.
"""

import sys


def update_chromedriver():
    """Atualiza o ChromeDriver para a versão mais recente."""
    try:
        from webdriver_manager.chrome import ChromeDriverManager

        print("→ Baixando ChromeDriver mais recente...")
        path = ChromeDriverManager().install()
        print(f"✅ ChromeDriver atualizado: {path}")
        return True
    except ImportError:
        print("❌ webdriver-manager não está instalado!")
        print("   Execute: poetry add webdriver-manager")
        return False
    except Exception as e:
        print(f"❌ Erro ao atualizar ChromeDriver: {e}")
        return False


def update_nltk_resources():
    """Atualiza recursos NLTK necessários."""
    try:
        import nltk
        import ssl

        # Bypass SSL verification issues
        try:
            _create_unverified_https_context = ssl._create_unverified_context
        except AttributeError:
            pass
        else:
            ssl._create_default_https_context = _create_unverified_https_context

        resources = [
            ("punkt_tab", "Tokenizer"),
            ("stopwords", "Stopwords"),
            ("averaged_perceptron_tagger", "POS Tagger"),
            ("wordnet", "WordNet"),
        ]

        print("📚 Atualizando recursos NLTK...")
        for resource, name in resources:
            print(f"   → Baixando {name}...")
            nltk.download(resource, quiet=True)

        print("✅ Recursos NLTK atualizados!")
        return True
    except ImportError:
        print("❌ NLTK não está instalado!")
        return False
    except Exception as e:
        print(f"❌ Erro ao atualizar NLTK: {e}")
        return False


def main():
    """Função principal."""
    if len(sys.argv) < 2:
        print("Uso: python update_drivers.py [chromedriver|nltk|all]")
        sys.exit(1)

    action = sys.argv[1].lower()
    success = True

    if action == "chromedriver":
        success = update_chromedriver()
    elif action == "nltk":
        success = update_nltk_resources()
    elif action == "all":
        success = update_chromedriver() and update_nltk_resources()
    else:
        print(f"Ação desconhecida: {action}")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
