#!/usr/bin/env python3
"""
Script para encontrar o seletor correto dos reviews
"""

import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def find_review_selector():
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

        # Procurar especificamente por reviews individuais
        print("=== ANALISANDO ESTRUTURA DE REVIEWS ===")

        # Examinar a estrutura das reviews na seção
        reviews_section = soup.find("section", id="profile-reviews")
        if reviews_section:
            # Procurar por elementos que contenham nomes de pacientes
            name_elements = reviews_section.find_all(
                string=lambda text: text and "Gabriela" in text
            )

            print(f"Elementos com 'Gabriela': {len(name_elements)}")

            for i, text_elem in enumerate(name_elements[:3]):
                if hasattr(text_elem, "parent"):
                    parent = text_elem.parent
                    print(f"\nReview {i + 1}:")
                    print(f"  Pai direto: {parent.name if parent else 'None'}")
                    print(
                        f"  Classes pai: {parent.get('class', []) if parent else 'None'}"
                    )

                    # Subir mais na hierarquia para encontrar o container da review
                    current = parent
                    for level in range(5):  # Subir até 5 níveis
                        if current and hasattr(current, "parent") and current.parent:
                            current = current.parent
                            classes = current.get("class", [])
                            if classes:
                                print(
                                    f"  Nível {level + 2}: {current.name} classes={classes}"
                                )
                                # Verificar se este container tem dados da review completa
                                container_text = current.get_text().strip()
                                if (
                                    "recomendo" in container_text.lower()
                                    or "profissional" in container_text.lower()
                                    or len(container_text) > 200
                                ):
                                    print(f"    👉 POSSÍVEL CONTAINER DA REVIEW!")
                                    print(
                                        f"    Seletor sugerido: {current.name}.{'.'.join(classes)}"
                                    )

        # Testar seletores específicos que podem funcionar
        print("\n=== TESTANDO SELETORES CANDIDATOS ===")
        candidate_selectors = [
            'div[data-test-id="opinion-block"]',  # Original (não funciona)
            "#profile-reviews .card-body",
            "#profile-reviews > div > div",
            ".opinions-list > div",
            ".card-body.opinions-list > div",
            'div[class*="opinion"]',
            "[data-cy]",
            'div:has(> div:contains("Gabriela"))',  # Não vai funcionar no BS4
        ]

        for selector in candidate_selectors:
            try:
                elements = soup.select(selector)
                print(f"{selector}: {len(elements)} elementos")

                if elements:
                    # Examinar o primeiro elemento
                    first = elements[0]
                    text = first.get_text().strip()
                    has_review_content = any(
                        word in text.lower()
                        for word in ["recomendo", "profissional", "médica"]
                    )
                    print(f"  Tem conteúdo de review: {has_review_content}")
                    if has_review_content:
                        print(f"  ⭐ CANDIDATO PROMISSOR!")
                        print(f"  Amostra: {text[:150]}...")
            except Exception as e:
                print(f"{selector}: ERRO - {e}")

        # Examinar estrutura específica da lista de opiniões
        print("\n=== ESTRUTURA OPINIONS-LIST ===")
        opinions_list = soup.find("div", class_="opinions-list")
        if opinions_list:
            children = opinions_list.find_all(recursive=False)
            print(f"Filhos diretos da opinions-list: {len(children)}")

            for i, child in enumerate(children[:5]):
                text = child.get_text().strip()
                classes = child.get("class", [])

                # Verificar se contém dados de review
                has_author = any(
                    name in text for name in ["Gabriela", "Ana", "Maria", "João"]
                )
                has_comment = len(text) > 100

                print(f"\nFilho {i + 1}:")
                print(f"  Tag: {child.name}")
                print(f"  Classes: {classes}")
                print(f"  Tem autor: {has_author}")
                print(f"  Tem comentário: {has_comment}")

                if has_author and has_comment:
                    print(f"  ⭐ POSSÍVEL REVIEW INDIVIDUAL!")
                    print(
                        f"  Seletor: .opinions-list > {child.name}"
                        + (f".{'.'.join(classes)}" if classes else "")
                    )
                    print(f"  Amostra: {text[:200]}...")

    finally:
        driver.quit()


if __name__ == "__main__":
    find_review_selector()
