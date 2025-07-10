import json
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from selenium import webdriver
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchElementException,
    SessionNotCreatedException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# pylint: disable=too-few-public-methods
class MockConfig:
    """
    Mock configuration class for DoctoraliaScraper.
    Contains scraping and data directory settings.
    """

    class _ScrapingConfig:
        """
        Scraping configuration settings.
        """

        # pylint: disable=too-few-public-methods

        def __init__(self) -> None:
            self.headless = True
            self.page_load_timeout = 60
            self.implicit_wait = 10
            self.explicit_wait = 20
            self.delay_min = 1.5
            self.delay_max = 3.5
            self.max_retries = 3

        def get_wait_times(self) -> Dict[str, int]:
            """Return a dictionary of wait time configurations."""
            return {
                "page_load": self.page_load_timeout,
                "implicit": self.implicit_wait,
                "explicit": self.explicit_wait,
            }

    def __init__(self) -> None:
        self.scraping = self._ScrapingConfig()
        # Adjust this path to your desired data directory
        self.data_dir = Path("./doctoralia_data")

    def get_data_path(self) -> Path:
        """Return the configured data directory path."""
        return self.data_dir


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
default_logger = logging.getLogger(__name__)


class DoctoraliaScraper:
    def __init__(
        self, config_obj: Any, logger_instance: Optional[logging.Logger] = None
    ) -> None:
        self.config = config_obj
        self.logger = logger_instance or default_logger
        self.driver: Optional[webdriver.Chrome] = None

    def get_random_user_agent(self) -> str:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36",
        ]
        return random.choice(user_agents)

    def setup_driver(self) -> bool:
        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                self.logger.info(
                    f"Tentativa {attempt + 1}/{max_attempts} de inicializar navegador..."
                )

                chromedriver_binary = ChromeDriverManager().install()

                options = Options()

                if self.config.scraping.headless:
                    options.add_argument("--headless=new")

                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-software-rasterizer")
                options.add_argument("--window-size=1920,1080")
                options.add_argument(f"--user-agent={self.get_random_user_agent()}")
                options.add_argument("--memory-pressure-off")
                options.add_argument("--max_old_space_size=4096")
                options.add_argument("--disable-background-timer-throttling")
                options.add_argument("--disable-renderer-backgrounding")
                options.add_argument("--disable-backgrounding-occluded-windows")
                options.add_argument("--disable-logging")
                options.add_argument("--log-level=3")
                options.add_argument("--silent")
                options.add_experimental_option("excludeSwitches", ["enable-logging"])
                options.add_experimental_option("useAutomationExtension", False)
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--disable-extensions")
                options.add_argument("--disable-plugins")
                options.add_argument("--disable-images")
                options.add_argument("--disable-web-security")
                options.add_argument("--allow-running-insecure-content")
                options.add_argument("--aggressive-cache-discard")
                options.add_argument("--disable-background-networking")

                service = Service(chromedriver_binary)
                self.driver = webdriver.Chrome(service=service, options=options)

                self.driver.set_page_load_timeout(
                    self.config.scraping.page_load_timeout
                )
                self.driver.implicitly_wait(self.config.scraping.implicit_wait)

                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

                self.logger.info("✅ Navegador inicializado com sucesso")
                return True

            except SessionNotCreatedException as e:
                self.logger.warning(
                    "Erro de sessão na tentativa %d: %s", attempt + 1, e
                )
                if attempt < max_attempts - 1:
                    time.sleep(2)
                else:
                    self.logger.error(
                        "Falha ao criar sessão do navegador após todas as tentativas"
                    )
                    return False

            except WebDriverException as e:
                self.logger.error(
                    "❌ Erro ao inicializar navegador (tentativa %d): %s",
                    attempt + 1,
                    e,
                )
                if attempt < max_attempts - 1:
                    time.sleep(2)
                else:
                    return False

        return False

    def safe_driver_quit(self) -> None:
        if self.driver:
            try:
                self.logger.info("🔄 Encerrando navegador...")
                self.driver.quit()
                self.logger.info("✅ Navegador encerrado com sucesso")
            except WebDriverException as e:
                self.logger.warning("⚠️ Aviso ao encerrar navegador: %s", e)
            finally:
                self.driver = None

    def add_human_delay(
        self, min_delay: Optional[float] = None, max_delay: Optional[float] = None
    ) -> None:
        min_d = min_delay or self.config.scraping.delay_min
        max_d = max_delay or self.config.scraping.delay_max
        delay = random.uniform(min_d, max_d)  # nosec B311
        time.sleep(delay)

    def retry_on_failure(
        self, func: Any, *args: Any, max_retries: Optional[int] = None, **kwargs: Any
    ) -> Any:
        max_retries_value = max_retries or self.config.scraping.max_retries
        last_exception = None

        for attempt in range(max_retries_value):
            try:
                return func(*args, **kwargs)
            except (
                TimeoutException,
                WebDriverException,
                InvalidSessionIdException,
            ) as e:
                last_exception = e
                self.logger.warning(
                    f"Tentativa {attempt + 1}/{max_retries_value} falhou: {type(e).__name__}"
                )
                if attempt < max_retries_value - 1:
                    wait_time = (attempt + 1) * 2
                    self.logger.info(
                        "Aguardando %ds antes da próxima tentativa...", wait_time
                    )
                    time.sleep(wait_time)
                else:
                    break
            except ValueError as e:
                self.logger.error("Erro não recuperável: %s", e)
                raise e

        raise (
            last_exception
            if last_exception
            else RuntimeError("Falha após todas as tentativas")
        )

    def extract_doctor_name(self) -> Optional[str]:
        css_selector = '[data-test-id="doctor-header-fullname"] span[itemprop="name"]'

        def _extract_name() -> Optional[str]:
            if self.driver is None:
                raise RuntimeError("Driver não inicializado")
            wait = WebDriverWait(self.driver, self.config.scraping.explicit_wait)
            name_element = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector))
            )
            text_content = name_element.get_attribute("textContent")
            if text_content:
                doctor_name = text_content.strip()
                return self.clean_text(doctor_name)
            return None

        try:
            doctor_name = self.retry_on_failure(_extract_name)
            return str(doctor_name) if doctor_name is not None else None
        except (TimeoutException, NoSuchElementException):
            self.logger.warning(
                "Nome do médico não encontrado com o seletor principal. Tentando fallback."
            )
            try:
                if self.driver is None:
                    return None
                name_element = self.driver.find_element(
                    By.CSS_SELECTOR, 'span[itemprop="name"]'
                )
                text_content = name_element.get_attribute("textContent")
                if text_content:
                    return self.clean_text(text_content.strip())
                return None
            except NoSuchElementException:
                self.logger.error("Nome do médico não encontrado mesmo com fallback.")
                return None
        except WebDriverException as e:
            self.logger.error("Erro ao extrair nome do médico: %s", e)
            return None

    def _find_load_more_button(
        self, button_selectors: List[str]
    ) -> Optional[WebElement]:
        """Find the first visible and enabled 'Load More' button."""
        if not self.driver:
            return None

        for selector in button_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        self.logger.info(
                            f"Botão 'Veja Mais' encontrado com seletor: {selector}"
                        )
                        return element
            except NoSuchElementException:
                continue
        return None

    def click_load_more_button(self) -> int:
        if self.driver is None:
            self.logger.error("Driver não inicializado")
            return 0

        clicks_realizados = 0
        max_clicks = 50
        button_selectors = [
            "button[data-id='load-more-opinions']",
            "a[data-test-id='load-more-opinions']",
            "#profile-reviews > div > div.card-footer.text-center > button",
            ".text-center button",
        ]

        initial_reviews_count = self._count_current_reviews()
        self.logger.info("Comentários iniciais encontrados: %d", initial_reviews_count)

        method_start_time = time.time()
        method_timeout = 180  # 3 minutes

        while clicks_realizados < max_clicks:
            if time.time() - method_start_time > method_timeout:
                self.logger.warning(
                    "Timeout de %ds atingido para carregamento de comentários",
                    method_timeout,
                )
                break

            try:
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                self.add_human_delay(1.0, 2.0)

                veja_mais_button = self._find_load_more_button(button_selectors)

                if not veja_mais_button:
                    self.logger.info(
                        "Botão 'Veja Mais' não encontrado ou não visível. "
                        "Provavelmente todos os comentários foram carregados."
                    )
                    break

                reviews_before = self._count_current_reviews()

                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", veja_mais_button
                )
                self.add_human_delay(0.5, 1.0)
                self.driver.execute_script("arguments[0].click();", veja_mais_button)
                clicks_realizados += 1
                self.logger.info(
                    "✅ Clique %d realizado no botão 'Veja Mais'", clicks_realizados
                )

                # Wait for new reviews to load using a reliable explicit wait
                wait = WebDriverWait(self.driver, 15)
                wait.until(lambda d: self._count_current_reviews() > reviews_before)

                reviews_after = self._count_current_reviews()
                self.logger.info(
                    "Novos comentários carregados: %d → %d",
                    reviews_before,
                    reviews_after,
                )

                # Wait for page to stabilize after loading new content
                self.add_human_delay(2.0, 4.0)

            except TimeoutException:
                self.logger.warning(
                    "Timeout esperando por novos comentários após clique %d. Parando.",
                    clicks_realizados,
                )
                break
            except WebDriverException as e:
                self.logger.warning(
                    "Erro ao clicar ou carregar mais comentários: %s", e
                )
                break

        final_count = self._count_current_reviews()
        load_summary = (
            f"📊 Carregamento concluído: Cliques: {clicks_realizados}, "
            f"Inicial: {initial_reviews_count}, Final: {final_count}"
        )
        self.logger.info(
            load_summary
        )  # Este log já é feito acima, remover linha duplicada

        # Wait a bit before finishing to ensure all background processes are complete
        self.add_human_delay(2.0, 3.0)

        return clicks_realizados

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned

    def extract_rating(self, review_element: Any) -> Optional[int]:
        soup = self._ensure_soup(review_element)
        if not soup or not isinstance(soup, Tag):
            return None
        try:
            rating_container = soup.find("div", {"data-score": True})
            if (
                rating_container
                and isinstance(rating_container, Tag)
                and rating_container.has_attr("data-score")
            ):
                data_score = rating_container.get("data-score")
                if isinstance(data_score, str) and data_score.isdigit():
                    return int(data_score)
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.debug("Não foi possível extrair nota: %s", e)
        return None

    def extract_date(self, review_element: WebElement) -> Optional[str]:
        soup = self._ensure_soup(review_element)
        if not soup or not isinstance(soup, Tag):
            return None
        try:
            date_element = soup.find("time", {"itemprop": "datePublished"})
            if (
                date_element
                and isinstance(date_element, Tag)
                and date_element.has_attr("datetime")
            ):
                datetime_attr = date_element.get("datetime")
                if isinstance(datetime_attr, str):
                    return datetime_attr
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.debug("Erro ao parsear data: %s", e)
        return None

    def extract_author_name(self, review_element: WebElement) -> Optional[str]:
        soup = self._ensure_soup(review_element)
        if not soup or not isinstance(soup, Tag):
            return None
        try:
            header = soup.find("div", class_="opinion-header")
            if header and isinstance(header, Tag):
                author_element = header.select_one('span[itemprop="name"]')
                if author_element and isinstance(author_element, Tag):
                    author_name = self.clean_text(author_element.get_text(strip=True))
                    if "Dra." not in author_name and "Dr." not in author_name:
                        return author_name
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.debug("Erro ao parsear autor: %s", e)
        return None

    def extract_comment(self, review_element: WebElement) -> Optional[str]:
        soup = self._ensure_soup(review_element)
        if not soup or not isinstance(soup, Tag):
            return None
        try:
            comment_element = soup.find("p", {"data-test-id": "opinion-comment"})
            if comment_element and isinstance(comment_element, Tag):
                return self.clean_text(comment_element.get_text(strip=True))
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.debug("Erro ao extrair comentário: %s", e)
        return None

    def extract_reply(self, review_element: WebElement) -> Optional[str]:
        """Extract doctor's reply from a review element."""
        result = None
        soup = self._ensure_soup(review_element)

        if soup and isinstance(soup, Tag):
            try:
                reply_element = soup.find("div", {"data-id": "doctor-answer-content"})
                if reply_element and isinstance(reply_element, Tag):
                    paragraphs = reply_element.find_all("p")
                    if len(paragraphs) > 1:
                        result = self.clean_text(paragraphs[1].get_text(strip=True))
                    else:
                        result = self.clean_text(reply_element.get_text(strip=True))
            except (ValueError, TypeError, AttributeError) as e:
                self.logger.debug("Erro ao extrair resposta: %s", e)

        return result

    def _ensure_soup(self, element: WebElement) -> Optional[Tag]:
        """Convert an element to BeautifulSoup Tag if possible."""
        if element is None:
            return None
        if isinstance(element, Tag):
            return element

        result = None
        try:
            # Selenium WebElement
            if hasattr(element, "get_attribute"):
                html = element.get_attribute("outerHTML")
                if html:
                    soup = BeautifulSoup(html, "html.parser")
                    # Find first Tag in contents
                    for tag in soup.contents:
                        if isinstance(tag, Tag):
                            result = tag
                            break
                        break
            # HTML string
            elif isinstance(element, str):
                soup = BeautifulSoup(element, "html.parser")
                # Find first Tag in contents
                for tag in soup.contents:
                    if isinstance(tag, Tag):
                        result = tag
                        break
        except (ValueError, TypeError, AttributeError) as e:
            self.logger.debug("Erro ao converter elemento para BeautifulSoup: %s", e)

        return result

    def _get_soup_tag(self, element: WebElement) -> Optional[Tag]:
        soup = self._ensure_soup(element)
        return soup if isinstance(soup, Tag) else None

    def _process_single_scrape_attempt(
        self, url: str, attempt: int
    ) -> Optional[Dict[str, Any]]:
        """Process a single scraping attempt and return data or None if failed."""
        result = None
        max_retries = self.config.scraping.max_retries

        self.logger.info(
            f"🚀 Iniciando scraping (tentativa {attempt + 1}/{max_retries})..."
        )

        # Validate URL first before any browser operations
        if not url.startswith("https://www.doctoralia.com.br/"):
            self.logger.error("URL deve ser do Doctoralia")
            return None

        # Setup browser
        if not self.setup_driver():
            self.logger.error("❌ Falha na inicialização do navegador")
            return None

        try:
            # Guard against None driver
            if self.driver is None:
                raise RuntimeError("Driver not available after setup")

            # Load page
            self.logger.info("🌐 Acessando página: %s", url)
            self.driver.get(url)
            WebDriverWait(self.driver, self.config.scraping.explicit_wait).until(
                EC.presence_of_element_located((By.ID, "profile-reviews"))
            )
            self.add_human_delay()

            # Extract doctor information
            self.logger.info("👨‍⚕️ Extraindo nome do médico...")
            doctor_name = self.extract_doctor_name()
            if doctor_name:
                self.logger.info("Médico identificado: %s", doctor_name)
            else:
                self.logger.warning("Não foi possível identificar o nome do médico.")

            # Load and process reviews
            self.logger.info("📚 Carregando todos os comentários...")
            self.click_load_more_button()

            self.logger.info("🔍 Processando comentários com BeautifulSoup...")
            reviews_data = self._extract_all_reviews()

            # Create result
            result = {
                "url": url,
                "doctor_name": doctor_name,
                "extraction_timestamp": datetime.now().isoformat(),
                "reviews": reviews_data,
                "total_reviews": len(reviews_data),
            }

            self.logger.info(
                "✅ Extração concluída: %d comentários encontrados.", len(reviews_data)
            )

        except WebDriverException as e:
            self.logger.error(
                "❌ Erro durante scraping (tentativa %d): %s",
                attempt + 1,
                e,
                exc_info=True,
            )
            result = None

        finally:
            self.safe_driver_quit()

        return result

    def scrape_reviews(self, url: str) -> Optional[Dict[str, Any]]:
        """Main method to scrape doctor reviews with retry logic."""
        result = None
        max_retries = self.config.scraping.max_retries

        for attempt in range(max_retries):
            try:
                # Try to scrape
                result = self._process_single_scrape_attempt(url, attempt)
                if result:
                    break

                # If we failed but have more attempts, wait and try again
                if attempt < max_retries - 1:
                    wait_time = 5 + (attempt * 2)  # Increasing backoff
                    self.logger.info("🔄 Tentando novamente em %ds...", wait_time)
                    time.sleep(wait_time)

            except WebDriverException as e:
                self.logger.error(
                    "❌ Erro crítico na tentativa %d: %s", attempt + 1, e, exc_info=True
                )
                if attempt < max_retries - 1:
                    time.sleep(10)

        return result

    def _extract_all_reviews(self) -> List[Dict]:
        if not self.driver:
            return []

        reviews_data: List[Dict[str, Any]] = []
        page_source = self.driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")

        review_elements = soup.find_all("div", {"data-test-id": "opinion-block"})
        self.logger.info(
            f"Encontrados {len(review_elements)} elementos de review com o seletor principal."
        )

        for review_index, review_element in enumerate(review_elements):
            try:
                comment = self.extract_comment(review_element)
                if not comment:
                    self.logger.warning(
                        f"Comentário {review_index + 1} ignorado por falta de texto."
                    )
                    continue

                # Use direct assignment to reduce local variables
                review_data = {
                    "id": review_index + 1,
                    "author": self.extract_author_name(review_element),
                    "comment": comment,  # Reuse already extracted comment
                    "rating": self.extract_rating(review_element),
                    "date": self.extract_date(review_element),
                    "doctor_reply": self.extract_reply(review_element),
                }

                review_data = {k: v for k, v in review_data.items() if v is not None}
                reviews_data.append(review_data)

            except (ValueError, TypeError, AttributeError) as e:
                self.logger.warning(
                    "Erro ao processar avaliação %d: %s", review_index + 1, e
                )
                continue
            except (TimeoutException, WebDriverException) as e:
                self.logger.warning(
                    "Erro de navegador ao processar avaliação %d: %s",
                    review_index + 1,
                    e,
                )
                continue

        self.logger.info("Extraídos %d comentários com sucesso.", len(reviews_data))
        return reviews_data

    def save_data(self, data: Dict[str, Any]) -> Optional[Path]:
        if not data or not data.get("reviews"):
            self.logger.warning("Nenhum dado para salvar.")
            return None

        try:
            self.config.data_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            doctor_name = data.get("doctor_name", "unknown_doctor")
            clean_name = (
                re.sub(r"[^\w\s-]", "", doctor_name).strip().replace(" ", "_").lower()
            )
            file_name = f"{timestamp}_{clean_name}.json"
            file_path = self.config.data_dir / file_name
            file_path = Path(file_path)  # Explicit cast to Path

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info("💾 Dados salvos com sucesso em: %s", file_path)
            return file_path
        except IOError as e:
            self.logger.error("Erro ao salvar os dados: %s", e)
            return None

    def _count_current_reviews(self) -> int:
        if self.driver is None:
            return 0
        try:
            review_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "[data-test-id='opinion-block']"
            )
            return len(review_elements)
        except WebDriverException as e:
            self.logger.debug("Erro ao contar comentários: %s", e)
            return 0


if __name__ == "__main__":
    TARGET_URL = (
        "https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"
    )
    config_instance = MockConfig()
    scraper = DoctoraliaScraper(
        config_obj=config_instance, logger_instance=default_logger
    )
    scraped_data = scraper.scrape_reviews(TARGET_URL)
    if scraped_data:
        default_logger.info("\n--- RESUMO DA EXTRAÇÃO ---")
        default_logger.info("Médico: %s", scraped_data.get("doctor_name"))
        default_logger.info(
            "Total de Avaliações Extraídas: %s", scraped_data.get("total_reviews")
        )
        saved_file = scraper.save_data(scraped_data)
        if saved_file and scraped_data.get("reviews"):
            default_logger.info("\n--- AMOSTRA DAS AVALIAÇÕES ---")
            for i, review in enumerate(scraped_data.get("reviews", [])[:3]):
                default_logger.info("\nReview #%d:", i + 1)
                default_logger.info("  Autor: %s", review.get("author", "N/A"))
                default_logger.info("  Nota: %s", review.get("rating", "N/A"))
                default_logger.info("  Data: %s", review.get("date", "N/A"))
                default_logger.info(
                    "  Comentário: %s...", review.get("comment", "")[:100]
                )
                if review.get("doctor_reply"):
                    default_logger.info(
                        "  Resposta: %s...", review.get("doctor_reply", "")[:100]
                    )
    else:
        default_logger.error("A extração de dados falhou após todas as tentativas.")
