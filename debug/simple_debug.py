#!/usr/bin/env python3
"""
Script simples para examinar seletores de review
"""

import time

from bs4 import BeautifulSoup, element
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def main():
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

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Examinar a seção de reviews
        print("\n=== SEÇÃO PROFILE-REVIEWS ===")
        reviews_section = soup.find("section", id="profile-reviews")

        if reviews_section:
            print("✅ Seção encontrada!")

            # Garantir que reviews_section é um Tag antes de chamar find_all
            if isinstance(reviews_section, element.Tag):
                all_divs = reviews_section.find_all("div")
            else:
                # Fallback: reparse o HTML do trecho para obter um Tag
                print(
                    "⚠️ 'profile-reviews' encontrada, mas não é um Tag. Reparseando para fallback."
                )
                reviews_soup = BeautifulSoup(str(reviews_section), "html.parser")
                all_divs = reviews_soup.find_all("div")

            print(f"Total de divs na seção: {len(all_divs)}")

            review_candidates = []
            for div in all_divs:
                text = div.get_text().strip()
                classes = " ".join(div.get("class", []))

                # Filtrar elementos que podem ser reviews
                if len(text) > 100 and any(
                    word in text.lower()
                    for word in [
                        "recomendo",
                        "profissional",
                        "médica",
                        "atendimento",
                        "consulta",
                    ]
                ):
                    review_candidates.append(
                        {
                            "classes": classes,
                            "text": text[:200] + "..." if len(text) > 200 else text,
                        }
                    )

            print(f"\nCandidatos a reviews encontrados: {len(review_candidates)}")
            for i, candidate in enumerate(review_candidates[:5]):
                print(f"\n{i + 1}. Classes: {candidate['classes']}")
                print(f"   Texto: {candidate['text']}")

        else:
            print("❌ Seção não encontrada!")

        # Tentar seletores CSS específicos
        print("\n=== TESTANDO SELETORES CSS ===")
        test_selectors = [
            "#profile-reviews div",
            "#profile-reviews .card",
            '[data-cy="doctor-opinion"]',
            ".opinion",
            ".review",
            ".patient-opinion",
        ]

        for selector in test_selectors:
            elements = soup.select(selector)
            print(f"{selector}: {len(elements)} elementos")

            if elements:
                first_elem = elements[0]
                first_text = first_elem.get_text().strip()[:150]
                print(f"   Primeiro elemento: {first_text}...")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
