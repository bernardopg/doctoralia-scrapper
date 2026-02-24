"""
Multi-site support for medical review scraping.
Base classes and specific implementations for different medical review platforms.
"""

import json
import logging
import random
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


@dataclass
class ReviewData:
    """Standardized review data structure."""

    author: str
    rating: float
    comment: str
    date: str
    doctor_reply: Optional[str] = None
    review_id: Optional[str] = None
    verified: bool = False
    helpful_votes: int = 0
    platform: str = "unknown"


@dataclass
class DoctorData:
    """Standardized doctor data structure."""

    name: str
    specialty: str
    location: str
    rating: float
    total_reviews: int
    platform: str
    profile_url: str
    verified: bool = False


class BaseMedicalScraper(ABC):
    """
    Abstract base class for medical review scrapers.
    Provides common functionality and defines the interface.
    """

    def __init__(self, config: Any, logger: Optional[logging.Logger] = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.driver: Optional[webdriver.Chrome] = None
        self.platform_name = "base"

    @abstractmethod
    def get_platform_name(self) -> str:
        """Return the name of the platform this scraper handles."""
        pass

    @abstractmethod
    def validate_url(self, url: str) -> bool:
        """Validate if the URL belongs to this platform."""
        pass

    @abstractmethod
    def extract_doctor_info(self) -> DoctorData:
        """Extract doctor information from the current page."""
        pass

    @abstractmethod
    def extract_reviews(self) -> List[ReviewData]:
        """Extract all reviews from the current page."""
        pass

    @abstractmethod
    def get_load_more_selector(self) -> Optional[str]:
        """Return the CSS selector for the 'load more' button."""
        pass

    def setup_driver(self) -> bool:
        """Setup Chrome WebDriver with common configuration."""
        try:
            options = webdriver.ChromeOptions()
            if self.config.scraping.headless:
                options.add_argument("--headless=new")

            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument(f"--user-agent={self.get_random_user_agent()}")

            service = webdriver.ChromeService(
                executable_path=ChromeDriverManager().install()
            )
            self.driver = webdriver.Chrome(service=service, options=options)

            self.driver.implicitly_wait(self.config.scraping.implicit_wait)
            return True

        except Exception as e:
            self.logger.error(f"Failed to setup driver: {e}")
            return False

    def get_random_user_agent(self) -> str:
        """Return a random user agent string."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        ]
        return random.choice(user_agents)

    def navigate_to_page(self, url: str) -> bool:
        """Navigate to the given URL."""
        if not self.driver:
            return False

        try:
            self.driver.get(url)
            WebDriverWait(self.driver, self.config.scraping.explicit_wait).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            # Human-like delay usando configuração
            delay = random.uniform(
                self.config.delays.human_like_min, self.config.delays.human_like_max
            )
            time.sleep(delay)
            return True
        except Exception as e:
            self.logger.error(f"Failed to navigate to {url}: {e}")
            return False

    def click_load_more_reviews(self, max_clicks: int = 50) -> int:
        """Click load more button until no more reviews or max_clicks reached."""
        if not self.driver:
            return 0

        clicks = 0
        selector = self.get_load_more_selector()

        if not selector:
            return 0

        while clicks < max_clicks:
            try:
                load_more_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                load_more_button.click()
                clicks += 1
                # Delay configurável entre cliques
                delay = random.uniform(
                    self.config.delays.human_like_min, self.config.delays.human_like_max
                )
                time.sleep(delay)
            except Exception:
                break

        return clicks

    def save_data(
        self, doctor_data: DoctorData, reviews: List[ReviewData]
    ) -> Optional[Path]:
        """Save scraped data to JSON file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.platform_name}_{doctor_data.name.replace(' ', '_')}_{timestamp}.json"

            data_dir = Path(self.config.data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)

            output_file = data_dir / filename

            data = {
                "platform": self.platform_name,
                "scraped_at": datetime.now().isoformat(),
                "doctor": {
                    "name": doctor_data.name,
                    "specialty": doctor_data.specialty,
                    "location": doctor_data.location,
                    "rating": doctor_data.rating,
                    "total_reviews": doctor_data.total_reviews,
                    "profile_url": doctor_data.profile_url,
                    "verified": doctor_data.verified,
                },
                "reviews": [
                    {
                        "author": review.author,
                        "rating": review.rating,
                        "comment": review.comment,
                        "date": review.date,
                        "doctor_reply": review.doctor_reply,
                        "review_id": review.review_id,
                        "verified": review.verified,
                        "helpful_votes": review.helpful_votes,
                    }
                    for review in reviews
                ],
                "summary": {
                    "total_reviews": len(reviews),
                    "average_rating": (
                        sum(r.rating for r in reviews) / len(reviews) if reviews else 0
                    ),
                    "reviews_with_reply": sum(1 for r in reviews if r.doctor_reply),
                },
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"Data saved to {output_file}")
            return output_file

        except Exception as e:
            self.logger.error(f"Failed to save data: {e}")
            return None

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class DoctoraliaMultiSiteScraper(BaseMedicalScraper):
    """Scraper for Doctoralia.com.br (multi-site variant)"""

    def get_platform_name(self) -> str:
        return "doctoralia"

    def validate_url(self, url: str) -> bool:
        return "doctoralia.com.br" in url

    def extract_doctor_info(self) -> DoctorData:
        """Extract doctor information from Doctoralia page."""
        if not self.driver:
            raise RuntimeError("Driver not initialized")

        try:
            # Extract doctor name
            name_selectors = [
                "h1[data-test-id='doctor-name']",
                ".doctor-name h1",
                "h1",
            ]

            doctor_name = "Unknown Doctor"
            for selector in name_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    doctor_name = element.text.strip()
                    break
                except Exception:
                    continue

            # Extract specialty and location
            specialty = "Unknown Specialty"
            location = "Unknown Location"

            try:
                specialty_element = self.driver.find_element(
                    By.CSS_SELECTOR, "[data-test-id='doctor-specialty']"
                )
                specialty = specialty_element.text.strip()
            except Exception:
                pass

            try:
                location_element = self.driver.find_element(
                    By.CSS_SELECTOR, "[data-test-id='doctor-location']"
                )
                location = location_element.text.strip()
            except Exception:
                pass

            # Extract rating
            rating = 0.0
            try:
                rating_element = self.driver.find_element(
                    By.CSS_SELECTOR, "[data-test-id='doctor-rating']"
                )
                rating_text = rating_element.text.strip()
                match = re.search(r"(\d+\.?\d*)", rating_text)
                if match:
                    rating = float(match.group(1))
            except Exception:
                pass

            return DoctorData(
                name=doctor_name,
                specialty=specialty,
                location=location,
                rating=rating,
                total_reviews=0,  # Will be updated after extracting reviews
                platform=self.platform_name,
                profile_url=self.driver.current_url,
            )

        except Exception as e:
            self.logger.error(f"Failed to extract doctor info: {e}")
            return DoctorData(
                name="Unknown",
                specialty="Unknown",
                location="Unknown",
                rating=0.0,
                total_reviews=0,
                platform=self.platform_name,
                profile_url=self.driver.current_url if self.driver else "",
            )

    def extract_reviews(self) -> List[ReviewData]:
        """Extract reviews from Doctoralia page."""
        if not self.driver:
            return []

        reviews = []
        try:
            review_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "[data-test-id='opinion-block']"
            )

            for element in review_elements:
                try:
                    # Extract review data
                    author = "Anonymous"
                    try:
                        author_element = element.find_element(
                            By.CSS_SELECTOR, "[data-test-id='review-author']"
                        )
                        author = author_element.text.strip()
                    except Exception:
                        pass

                    rating = 0.0
                    try:
                        rating_element = element.find_element(
                            By.CSS_SELECTOR, "[data-test-id='review-rating']"
                        )
                        rating_text = (
                            rating_element.get_attribute("data-rating")
                            or rating_element.text
                        )
                        match = re.search(r"(\d+\.?\d*)", rating_text)
                        if match:
                            rating = float(match.group(1))
                    except Exception:
                        pass

                    comment = ""
                    try:
                        comment_element = element.find_element(
                            By.CSS_SELECTOR, "[data-test-id='review-comment']"
                        )
                        comment = comment_element.text.strip()
                    except Exception:
                        pass

                    date = ""
                    try:
                        date_element = element.find_element(
                            By.CSS_SELECTOR, "[data-test-id='review-date']"
                        )
                        date = date_element.text.strip()
                    except Exception:
                        pass

                    doctor_reply = None
                    try:
                        reply_element = element.find_element(
                            By.CSS_SELECTOR, "[data-test-id='doctor-reply']"
                        )
                        doctor_reply = reply_element.text.strip()
                    except Exception:
                        pass

                    reviews.append(
                        ReviewData(
                            author=author,
                            rating=rating,
                            comment=comment,
                            date=date,
                            doctor_reply=doctor_reply,
                            platform=self.platform_name,
                        )
                    )

                except Exception as e:
                    self.logger.warning(f"Failed to extract review: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to extract reviews: {e}")

        return reviews

    def get_load_more_selector(self) -> Optional[str]:
        """Return the CSS selector for Doctoralia's load more button."""
        return "button[data-id='load-more-opinions']"


class ScraperFactory:
    """
    Factory class for creating appropriate scraper instances.
    """

    @staticmethod
    def create_scraper(
        url: str, config: Any, logger: Optional[logging.Logger] = None
    ) -> Optional[BaseMedicalScraper]:
        """
        Create the appropriate scraper for the given URL.
        """
        scrapers = [
            DoctoraliaMultiSiteScraper,
        ]

        for scraper_class in scrapers:
            scraper = scraper_class(config, logger)
            if scraper.validate_url(url):
                return scraper

        return None

    @staticmethod
    def get_supported_platforms() -> List[str]:
        """Return list of supported platforms."""
        return ["doctoralia"]
