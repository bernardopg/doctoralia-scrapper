#!/usr/bin/env python3
"""
Comparar Selenium vs BeautifulSoup para encontrar o problema
"""

import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def compare_selenium_vs_bs4():
    # Configurar Chrome
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        url = "https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"
        print(f"Acessando: {url}")

        driver.get(url)
        time.sleep(5)

        # Clicar em "Veja Mais" uma vez
        try:
            wait = WebDriverWait(driver, 10)
            load_more_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[data-id='load-more-opinions']")
                )
            )
            print("Clicando em 'Veja Mais'...")
            load_more_btn.click()
            time.sleep(3)
        except Exception as e:
            print(f"Erro ao clicar: {e}")

        print("\n=== COMPARAÇÃO SELENIUM vs BeautifulSoup ===")

        # 1. Contar com Selenium
        selenium_elements = driver.find_elements(
            By.CSS_SELECTOR, "[data-test-id='opinion-block']"
        )
        print(
            f"Selenium encontrou: {len(selenium_elements)} elementos [data-test-id='opinion-block']"
        )

        # 2. Obter page_source e contar com BeautifulSoup
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        bs4_elements = soup.find_all("div", {"data-test-id": "opinion-block"})
        print(
            f"BeautifulSoup encontrou: {len(bs4_elements)} elementos [data-test-id='opinion-block']"
        )

        # 3. Comparar outros seletores
        print("\n=== TESTANDO OUTROS SELETORES ===")
        test_selectors = [
            "[data-test-id='opinion-block']",
            ".opinions-list > div",
            "#profile-reviews div",
            "[data-id]",
        ]

        for selector in test_selectors:
            # Selenium
            try:
                sel_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                sel_count = len(sel_elements)
            except Exception:
                sel_count = 0

            # BeautifulSoup
            try:
                bs4_elements = soup.select(selector)
                bs4_count = len(bs4_elements)
            except Exception:
                bs4_count = 0

            print(f"{selector}:")
            print(f"  Selenium: {sel_count} | BeautifulSoup: {bs4_count}")

            if sel_count != bs4_count:
                print("  ⚠️ DIFERENÇA DETECTADA!")

        # 4. Verificar se page_source contém os dados esperados
        print("\n=== ANÁLISE DO PAGE_SOURCE ===")
        print("Tamanho do page_source: {len(page_source)} caracteres")

        # Procurar por texto específico dos reviews
        search_terms = [
            "Gabriela Coelho",
            'data-test-id="opinion-block"',
            "opinion-comment",
        ]
        for term in search_terms:
            count = page_source.count(term)
            print(f"'{term}' aparece {count} vezes no page_source")

        # 5. Verificar se há JavaScript que pode estar interferindo
        script_tags = soup.find_all("script")
        print(f"\nEncontradas {len(script_tags)} tags <script>")

        # Verificar se há carregamento assíncrono
        for script in script_tags[:5]:
            script_content = script.get_text()
            if (
                "opinion" in script_content.lower()
                or "review" in script_content.lower()
            ):
                print("⚠️ Script com conteúdo relacionado a reviews encontrado")
                break

        # 6. Tentar aguardar mais tempo e verificar novamente
        print("\n=== AGUARDANDO MAIS TEMPO ===")
        time.sleep(5)

        page_source_2 = driver.page_source
        soup_2 = BeautifulSoup(page_source_2, "html.parser")
        bs4_elements_2 = soup_2.find_all("div", {"data-test-id": "opinion-block"})
        print(
            f"Após 5s adicionais, BeautifulSoup encontrou: {len(bs4_elements_2)} elementos"
        )

        if len(bs4_elements_2) != len(bs4_elements):
            print("✅ Conteúdo mudou após aguardar!")

    finally:
        driver.quit()


if __name__ == "__main__":
    compare_selenium_vs_bs4()
