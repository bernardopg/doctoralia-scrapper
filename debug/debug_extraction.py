#!/usr/bin/env python3
"""
Debug script to test extraction functions directly with real review elements.
"""

import os
import sys
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Import our scraper to test extraction functions
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from scraper import DoctoraliaScraper


def test_extraction_directly():
    """Test extraction functions directly with actual page data."""
    url = "https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"

    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    )

    driver = webdriver.Chrome(options=chrome_options)

    try:
        print(f"Loading URL: {url}")
        driver.get(url)

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Scroll to reviews section
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        # Click "Veja Mais" once to get more reviews
        try:
            veja_mais = driver.find_element(
                By.CSS_SELECTOR, "button[data-id='load-more-opinions']"
            )
            if veja_mais.is_displayed():
                driver.execute_script("arguments[0].click();", veja_mais)
                time.sleep(3)
                print("Clicked 'Veja Mais' button")
        except Exception as e:
            print(f"Could not click 'Veja Mais': {e}")

        # Get page source and parse
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")

        # Find review elements
        review_elements = soup.find_all("div", {"data-test-id": "opinion-block"})
        print(f"\nFound {len(review_elements)} review elements")

        if not review_elements:
            print("No review elements found! Checking alternative selectors...")
            alternatives = [
                (
                    "div[data-test-id*='opinion']",
                    soup.select("div[data-test-id*='opinion']"),
                ),
                ("div.opinion", soup.select("div.opinion")),
                (".review", soup.select(".review")),
                (
                    "[data-test-id]",
                    soup.select("[data-test-id]")[:5],
                ),  # First 5 elements with data-test-id
            ]

            for selector, elements in alternatives:
                print(f"  {selector}: {len(elements)} elements")
                if elements and len(elements) <= 5:
                    for i, elem in enumerate(elements):
                        print(
                            f"    Element {i}: {elem.get('data-test-id', 'no-test-id')} - {elem.name}"
                        )
            return

        # Create scraper instance to test extraction functions
        from config.settings import AppConfig

        config = AppConfig.load()
        scraper = DoctoraliaScraper(config)
        scraper.driver = driver

        # Test extraction on first few reviews
        for i, review_element in enumerate(review_elements[:3]):
            print(f"\n--- Testing Review {i + 1} ---")

            # Test each extraction function
            try:
                comment = scraper.extract_comment(review_element)
                print(f"Comment: {comment[:100] if comment else 'None'}...")

                author = scraper.extract_author_name(review_element)
                print(f"Author: {author}")

                rating = scraper.extract_rating(review_element)
                print(f"Rating: {rating}")

                date = scraper.extract_date(review_element)
                print(f"Date: {date}")

                reply = scraper.extract_reply(review_element)
                print(f"Reply: {reply[:50] if reply else 'None'}...")

                # Check if we got any data
                has_data = any([comment, author, rating, date])
                print(f"Has any data: {has_data}")

                if not has_data:
                    print("No data extracted! Debugging selectors...")

                    # Check what's actually in this element
                    print(f"Element HTML snippet: {str(review_element)[:300]}...")

                    # Test individual selectors
                    comment_elem = review_element.select_one(
                        'p[data-test-id="opinion-comment"]'
                    )
                    print(f"Comment element found: {comment_elem is not None}")
                    if comment_elem:
                        print(
                            f"Comment text: {comment_elem.get_text(strip=True)[:50]}..."
                        )

                    rating_elem = review_element.select_one("div[data-score]")
                    print(f"Rating element found: {rating_elem is not None}")
                    if rating_elem:
                        print(f"Rating score: {rating_elem.get('data-score')}")

                    author_elem = review_element.select_one("h4 span")
                    print(f"Author element found: {author_elem is not None}")
                    if author_elem:
                        print(f"Author text: {author_elem.get_text(strip=True)}")

            except Exception as e:
                print(f"Error extracting from review {i + 1}: {e}")
                import traceback

                traceback.print_exc()

    finally:
        driver.quit()


if __name__ == "__main__":
    test_extraction_directly()
