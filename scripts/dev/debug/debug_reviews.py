#!/usr/bin/env python3
"""
Script para debug específico da seção de reviews
"""

import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def debug_reviews_section():
    """Debug específico da seção de reviews"""

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

        # Obter HTML da página
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Focar na seção de reviews
        print("\n🔍 Procurando seção de reviews...")
        reviews_section = soup.find("section", id="profile-reviews")

        if reviews_section:
            print("✅ Seção 'profile-reviews' encontrada!")

            # Examinar os filhos da seção
            children = reviews_section.find_all(recursive=False)
            print(f"📦 Encontrados {len(children)} elementos filhos na seção")

            for i, child in enumerate(children[:5]):
                print(f"\n  👶 Filho {i + 1}: {child.name}")
                print(f"     🏷️ Classes: {child.get('class', [])}")
                print(f"     🔗 ID: {child.get('id')}")

                # Verificar se contém reviews
                nested_elements = child.find_all(["div", "article", "li"], limit=10)
                potential_reviews = []

                for elem in nested_elements:
                    text = elem.get_text().strip()
                    classes = elem.get("class", [])

                    # Verificar padrões típicos de review
                    review_indicators = [
                        "recomendo",
                        "recomend",
                        "profissional",
                        "médica",
                        "médico",
                        "atendimento",
                        "consulta",
                        "tratamento",
                        "paciente",
                        "excelente",
                    ]

                    if (
                        any(
                            indicator in text.lower() for indicator in review_indicators
                        )
                        and len(text) > 50
                    ):
                        potential_reviews.append(
                            {
                                "element": elem.name,
                                "classes": classes,
                                "text_preview": (
                                    text[:100] + "..." if len(text) > 100 else text
                                ),
                            }
                        )

                if potential_reviews:
                    print(
                        f"     💬 Possíveis reviews encontradas: {len(potential_reviews)}"
                    )
                    for j, review in enumerate(potential_reviews[:2]):
                        print(
                            f"       {j + 1}. {review['element']} classes={review['classes']}"
                        )
                        print(f"          📝 \"{review['text_preview']}\"")

            # Procurar por padrões específicos de review dentro da seção
            print("\n🔎 Procurando padrões específicos de review...")

            # Tentar seletores mais específicos
            specific_selectors = [
                'div[class*="opinion"]',
                'div[class*="review"]',
                'div[class*="comment"]',
                'li[class*="opinion"]',
                'li[class*="review"]',
                ".card .card-body",
                '[data-cy*="opinion"]',
                '[data-cy*="review"]',
                "div[data-id]",
                ".row .col",
            ]

            for selector in specific_selectors:
                elements = reviews_section.select(selector)
                if elements:
                    print(f"  ✅ {selector}: {len(elements)} elementos")

                    # Examinar os primeiros elementos
                    for k, elem in enumerate(elements[:3]):
                        text = elem.get_text().strip()[:150]
                        if len(text) > 30:  # Só mostrar elementos com texto substancial
                            print(f"    {k + 1}. Classes: {elem.get('class', [])}")
                            print(f'       📝 "{text}..."')
                            break
                else:
                    print(f"  ❌ {selector}: 0 elementos")

        else:
            print("❌ Seção 'profile-reviews' não encontrada!")

            # Procurar outras seções relacionadas a reviews
            print("\n🔍 Procurando outras seções de review...")
            all_sections = soup.find_all("section")
            for section in all_sections:
                section_id = section.get("id", "")
                section_classes = section.get("class", [])
                if any(
                    keyword
                    in str(section_id).lower() + " ".join(section_classes).lower()
                    for keyword in ["review", "opinion", "comment", "feedback"]
                ):
                    print(
                        f"  📋 Seção encontrada: id='{section_id}' classes={section_classes}"
                    )

    finally:
        driver.quit()


if __name__ == "__main__":
    debug_reviews_section()
