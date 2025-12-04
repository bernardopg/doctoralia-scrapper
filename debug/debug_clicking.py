#!/usr/bin/env python3
"""
Debug script to capture page state after clicking phase.
"""

import os
import sys
import time

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup  # noqa: E402
from selenium import webdriver  # noqa: E402
from selenium.webdriver.chrome.options import Options  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.support import expected_conditions as EC  # noqa: E402
from selenium.webdriver.support.ui import WebDriverWait  # noqa: E402
from src.scraper import DoctoraliaScraper  # noqa: E402


def debug_clicking_phase():
    """Debug what happens during and after the clicking phase."""
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

        # Create scraper instance
        from config.settings import AppConfig

        config = AppConfig.load()
        scraper = DoctoraliaScraper(config)
        scraper.driver = driver

        print("\n=== Initial State ===")
        initial_count = scraper._count_current_reviews()
        print(f"Initial review count: {initial_count}")

        print("\n=== Starting Click Phase ===")
        # Call click_load_more_button method directly
        clicks = scraper.click_load_more_button()
        print(f"Clicks performed: {clicks}")

        print("\n=== Immediately After Click Phase ===")
        immediate_count = scraper._count_current_reviews()
        print(f"Review count immediately after clicking: {immediate_count}")

        # Get page source right after clicking
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        review_elements = soup.find_all("div", {"data-test-id": "opinion-block"})
        print(f"BeautifulSoup elements found: {len(review_elements)}")

        # Check if there are any JavaScript errors
        logs = driver.get_log("browser")
        if logs:
            print(f"\nBrowser console logs: {len(logs)} entries")
            for log in logs[-5:]:  # Show last 5 logs
                print(f"  {log['level']}: {log['message']}")
        else:
            print("\nNo browser console logs")

        # Check current URL (in case of redirect)
        current_url = driver.current_url
        print(f"\nCurrent URL: {current_url}")
        print(f"URL changed: {current_url != url}")

        # Wait 5 seconds and check again
        print("\n=== After 5 Second Wait ===")
        time.sleep(5)
        wait_count = scraper._count_current_reviews()
        print(f"Review count after 5s wait: {wait_count}")

        current_url_after = driver.current_url
        print(f"URL after wait: {current_url_after}")
        print(f"URL changed during wait: {current_url_after != current_url}")

        # Check page title and basic structure
        print(f"\nPage title: {driver.title}")

        # Look for error messages or loading indicators
        error_elements = driver.find_elements(
            By.CSS_SELECTOR, ".error, .loading, .spinner"
        )
        print(f"Error/loading elements found: {len(error_elements)}")

        # Check if reviews section still exists
        reviews_section = driver.find_elements(By.ID, "profile-reviews")
        print(f"Reviews section exists: {len(reviews_section) > 0}")

        if len(reviews_section) > 0:
            reviews_section_html = reviews_section[0].get_attribute("outerHTML")
            if reviews_section_html:
                print(f"Reviews section HTML length: {len(reviews_section_html)}")
                print(f"Reviews section snippet: {reviews_section_html[:200]}...")
            else:
                print("Reviews section HTML is None")

    except Exception as e:
        print(f"Error during debugging: {e}")
        import traceback

        traceback.print_exc()

    finally:
        driver.quit()


if __name__ == "__main__":
    debug_clicking_phase()
