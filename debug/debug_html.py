#!/usr/bin/env python3
"""
Script para debug do HTML da página Doctoralia
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


def debug_page_html():
    """Debug do HTML da página para encontrar os seletores corretos"""

    # Configurar Chrome
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        url = "https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"
        print(f"🌐 Acessando: {url}")

        driver.get(url)
        time.sleep(5)  # Aguardar carregamento

        # Clicar no botão "Veja Mais" uma vez para carregar mais reviews
        try:
            wait = WebDriverWait(driver, 10)
            load_more_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[data-id='load-more-opinions']")
                )
            )
            print("📚 Clicando em 'Veja Mais' para carregar reviews...")
            load_more_btn.click()
            time.sleep(3)
        except Exception as e:
            print(f"⚠️ Erro ao clicar 'Veja Mais': {e}")

        # Obter HTML da página
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        print("\n🔍 Analisando estrutura HTML...")

        # Tentar vários seletores possíveis para reviews
        selectors_to_try = [
            ".opinion",
            ".review",
            ".comment",
            ".feedback",
            "article",
            ".card",
            ".opinion-item",
            ".review-item",
            '[data-testid*="opinion"]',
            '[data-testid*="review"]',
            ".opinion-card",
            ".user-opinion",
            ".patient-opinion",
            ".testimonial",
        ]

        print("📝 Testando seletores de review:")
        found_elements = {}

        for selector in selectors_to_try:
            elements = soup.select(selector)
            if elements:
                found_elements[selector] = len(elements)
                print(f"  ✅ {selector}: {len(elements)} elementos")

                # Mostrar um exemplo do primeiro elemento
                if len(elements) > 0:
                    first_element = elements[0]
                    text_content = first_element.get_text().strip()[:200]
                    print(f"     📄 Exemplo: {text_content}...")
                    print(f"     🏷️  Classes: {first_element.get('class', [])}")
                    print(f"     🔗 Atributos: {list(first_element.attrs.keys())}")
            else:
                print(f"  ❌ {selector}: 0 elementos")

        # Verificar se há elementos com texto típico de reviews
        print("\n🔎 Procurando por texto típico de reviews...")
        text_patterns = [
            "recomend",
            "profissional",
            "atendimento",
            "consulta",
            "médica",
            "doutor",
        ]

        for pattern in text_patterns:
            # Procurar elementos que contenham o padrão de texto
            all_elements = soup.find_all(
                text=lambda t: isinstance(t, str) and pattern.lower() in t.lower()
            )
            if all_elements:
                print(f"  📝 Texto '{pattern}': {len(all_elements)} ocorrências")
                # Mostrar os pais desses elementos
                for i, text_elem in enumerate(all_elements[:3]):
                    parent = (
                        text_elem.parent
                        if hasattr(text_elem, "parent") and text_elem.parent
                        else None
                    )
                    if parent:
                        print(
                            f"     🔗 Elemento pai {i + 1}: {parent.name} com classes {parent.get('class', [])}"
                        )

        # Examinar estrutura geral da página
        print("\n🏗️ Estrutura geral da página:")
        main_containers = soup.select(
            "main, .main, #main, .content, .container, .wrapper"
        )
        for container in main_containers[:3]:
            print(
                f"  📦 Container: {container.name} classes={container.get('class', [])}"
            )

        # Verificar se há seções específicas de opiniões
        opinion_sections = soup.select(
            '[class*="opinion"], [class*="review"], [id*="opinion"], [id*="review"]'
        )
        print(f"\n💬 Seções de opinião encontradas: {len(opinion_sections)}")
        for section in opinion_sections[:5]:
            print(
                f"  📋 {section.name}: classes={section.get('class', [])} id={section.get('id')}"
            )

        print(f"\n📊 Resumo: {len(found_elements)} seletores encontraram elementos")
        if found_elements:
            best_selector = max(found_elements, key=lambda k: found_elements[k])
            print(
                f"🎯 Melhor seletor: {best_selector} com {found_elements[best_selector]} elementos"
            )

    finally:
        driver.quit()


if __name__ == "__main__":
    debug_page_html()
