#!/usr/bin/env python3
"""
Script para examinar estrutura dos comentários
"""

import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def examine_comment_structure():
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

        # Encontrar elementos de review
        review_elements = soup.find_all("div", {"data-test-id": "opinion-block"})
        print(f"Elementos de review encontrados: {len(review_elements)}")

        if review_elements:
            # Examinar primeiro elemento de review
            first_review = review_elements[0]
            print("\n=== PRIMEIRO REVIEW ===")
            print(f"HTML básico: {str(first_review)[:300]}...")

            # Procurar por comentários usando diferentes seletores
            comment_selectors = [
                'p[data-test-id="opinion-comment"]',  # Original
                "p",  # Qualquer parágrafo
                'div[data-test-id*="comment"]',
                'div[class*="comment"]',
                ".comment",
                '[data-test-id*="opinion"]',
                'div[data-id*="comment"]',
            ]

            print("\n=== TESTANDO SELETORES DE COMENTÁRIO ===")
            for selector in comment_selectors:
                comment_elements = first_review.select(selector)
                print(f"{selector}: {len(comment_elements)} elementos")

                if comment_elements:
                    for i, elem in enumerate(comment_elements[:2]):
                        text = elem.get_text().strip()
                        if len(text) > 20:  # Só comentários substanciais
                            print(f"  {i + 1}. {text[:100]}...")

            # Examinar todos os parágrafos para encontrar o comentário
            print("\n=== TODOS OS PARÁGRAFOS NO REVIEW ===")
            all_paragraphs = first_review.find_all("p")
            for i, p in enumerate(all_paragraphs):
                text = p.get_text().strip()
                classes = p.get("class", [])
                data_attrs = {k: v for k, v in p.attrs.items() if k.startswith("data-")}

                print(f"Parágrafo {i + 1}:")
                print(f"  Classes: {classes}")
                print(f"  Data attrs: {data_attrs}")
                print(f"  Texto: {text[:150]}...")

                # Verificar se parece um comentário de review
                if len(text) > 50 and any(
                    word in text.lower()
                    for word in ["recomendo", "profissional", "ótima", "excelente"]
                ):
                    print(f"  ⭐ POSSÍVEL COMENTÁRIO DE REVIEW!")

            # Examinar todas as divs para encontrar comentários
            print("\n=== DIVS COM TEXTO LONGO ===")
            all_divs = first_review.find_all("div")
            for i, div in enumerate(all_divs):
                text = div.get_text().strip()
                if len(text) > 50:
                    classes = div.get("class", [])
                    data_attrs = {
                        k: v for k, v in div.attrs.items() if k.startswith("data-")
                    }

                    # Verificar se parece um comentário
                    if any(
                        word in text.lower()
                        for word in [
                            "recomendo",
                            "profissional",
                            "ótima",
                            "excelente",
                            "médica",
                        ]
                    ):
                        print(f"Div {i + 1} (possível comentário):")
                        print(f"  Classes: {classes}")
                        print(f"  Data attrs: {data_attrs}")
                        print(f"  Texto: {text[:150]}...")
                        print(f"  ⭐ CANDIDATO A COMENTÁRIO!")

    finally:
        driver.quit()


if __name__ == "__main__":
    examine_comment_structure()
