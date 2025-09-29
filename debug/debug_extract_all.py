#!/usr/bin/env python3
"""
Debug the _extract_all_reviews function to see exactly what's happening.
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


def test_extract_all_reviews():
    """Test the actual _extract_all_reviews function."""
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

        # Create scraper instance
        from config.settings import AppConfig

        config = AppConfig.load()
        scraper = DoctoraliaScraper(config)
        scraper.driver = driver

        # Now let's debug the _extract_all_reviews function step by step
        print("\n=== Debugging _extract_all_reviews function ===")

        # Get page source and parse (same as in the function)
        page_source = scraper.driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")

        review_elements = soup.find_all("div", {"data-test-id": "opinion-block"})
        print(f"Found {len(review_elements)} review elements")

        reviews_data = []

        for review_index, review_element in enumerate(
            review_elements[:5]
        ):  # Test first 5
            print(f"\n--- Processing Review {review_index + 1} ---")

            try:
                # Extract comment first (like the function does)
                comment = scraper.extract_comment(review_element)
                print(f"Comment extracted: {comment is not None}")
                if comment:
                    print(f"Comment preview: {comment[:50]}...")

                if not comment:
                    print(
                        f"Review {review_index + 1} would be skipped due to no comment"
                    )
                    continue

                # Extract all other fields
                author = scraper.extract_author_name(review_element)
                rating = scraper.extract_rating(review_element)
                date = scraper.extract_date(review_element)
                doctor_reply = scraper.extract_reply(review_element)

                print(f"Author: {author}")
                print(f"Rating: {rating}")
                print(f"Date: {date}")
                print(f"Doctor reply: {doctor_reply is not None}")

                # Create the review data (like the function does)
                review_data = {
                    "id": review_index + 1,
                    "author": author,
                    "comment": comment,
                    "rating": rating,
                    "date": date,
                    "doctor_reply": doctor_reply,
                }

                print(f"Before filtering: {len(review_data)} fields")
                print(f"Fields: {list(review_data.keys())}")
                print(
                    f"Non-None values: {sum(1 for v in review_data.values() if v is not None)}"
                )

                # Apply the filtering (this is the suspicious line)
                review_data_filtered = {
                    k: v for k, v in review_data.items() if v is not None
                }

                print(f"After filtering: {len(review_data_filtered)} fields")
                print(f"Filtered fields: {list(review_data_filtered.keys())}")

                if review_data_filtered:
                    reviews_data.append(review_data_filtered)
                    print(f"Review {review_index + 1} ADDED to results")
                else:
                    print(f"Review {review_index + 1} EXCLUDED (empty after filtering)")

            except Exception as e:
                print(f"Error processing review {review_index + 1}: {e}")
                import traceback

                traceback.print_exc()

        print(f"\n=== Final Results ===")
        print(f"Total reviews processed: {min(5, len(review_elements))}")
        print(f"Reviews in final data: {len(reviews_data)}")

        # Now call the actual function to compare
        print(f"\n=== Calling actual _extract_all_reviews ===")
        actual_result = scraper._extract_all_reviews()
        print(f"Actual function returned: {len(actual_result)} reviews")

        if actual_result:
            print("Sample review from actual function:")
            print(actual_result[0])

    finally:
        driver.quit()


if __name__ == "__main__":
    test_extract_all_reviews()
