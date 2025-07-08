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
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# --- Mock Configuration and Logger Setup for Standalone Execution ---


class MockConfig:
    """A mock configuration class to make the script self-contained."""

    def __init__(self):
        self.scraping = self._ScrapingConfig()
        # Adjust this path to your desired data directory
        self.data_dir = Path("./doctoralia_data")

    class _ScrapingConfig:
        """Nested scraping configuration."""

        def __init__(self):
            self.headless = True
            self.page_load_timeout = 60
            self.implicit_wait = 10
            self.explicit_wait = 20
            self.delay_min = 1.5
            self.delay_max = 3.5
            self.max_retries = 3


# Standard logger setup

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
# --- End of Setup ---


class DoctoraliaScraper:
    # <--- REFACTOR: Type hint for logger is now more specific.
    def __init__(self, config: Any, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.driver: Optional[webdriver.Chrome] = None
        # <--- REFACTOR: Removed unused `skip_keywords` list.
        # This list was defined but never used in the original code.

    def get_random_user_agent(self) -> str:
        """Retorna um user-agent aleatório"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        ]
        return random.choice(user_agents)

    def setup_driver(self) -> bool:
        """Configura o driver do Chrome com configurações otimizadas"""
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
                self.logger.warning(f"Erro de sessão na tentativa {attempt + 1}: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)
                else:
                    self.logger.error(
                        "Falha ao criar sessão do navegador após todas as tentativas"
                    )
                    return False

            except Exception as e:
                self.logger.error(
                    f"❌ Erro ao inicializar navegador (tentativa {attempt + 1}): {e}"
                )
                if attempt < max_attempts - 1:
                    time.sleep(2)
                else:
                    return False

        return False

    def safe_driver_quit(self) -> None:
        """Encerra o driver de forma segura"""
        if self.driver:
            try:
                self.logger.info("🔄 Encerrando navegador...")
                self.driver.quit()
                self.logger.info("✅ Navegador encerrado com sucesso")
            except Exception as e:
                self.logger.warning(f"⚠️ Aviso ao encerrar navegador: {e}")
            finally:
                self.driver = None

    def add_human_delay(
        self, min_delay: Optional[float] = None, max_delay: Optional[float] = None
    ) -> None:
        """Adiciona delay aleatório para simular comportamento humano"""
        min_d = min_delay or self.config.scraping.delay_min
        max_d = max_delay or self.config.scraping.delay_max
        delay = random.uniform(min_d, max_d)  # nosec B311
        time.sleep(delay)

    def retry_on_failure(
        self, func: Any, max_retries: Optional[int] = None, *args: Any, **kwargs: Any
    ) -> Any:
        """Executa uma função com retry automático em caso de falha"""
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
                        f"Aguardando {wait_time}s antes da próxima tentativa..."
                    )
                    time.sleep(wait_time)
                else:
                    break
            except Exception as e:
                self.logger.error(f"Erro não recuperável: {e}")
                raise e

        raise (
            last_exception
            if last_exception
            else Exception("Falha após todas as tentativas")
        )

    def extract_doctor_name(self) -> Optional[str]:
        """Extrai o nome do médico da página com um seletor robusto."""
        css_selector = '[data-test-id="doctor-header-fullname"] span[itemprop="name"]'

        def _extract_name() -> Optional[str]:
            if self.driver is None:
                raise Exception("Driver não inicializado")
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
        except Exception as e:
            self.logger.error(f"Erro ao extrair nome do médico: {e}")
            return None

    def click_load_more_button(self) -> int:
        """Clica no botão 'Veja Mais' até carregar todos os comentários."""
        if self.driver is None:
            self.logger.error("Driver não inicializado")
            return 0

        clicks_realizados = 0
        max_clicks = 50
        button_selectors = [
            "button[data-id='load-more-opinions']",
            "a[data-test-id='load-more-opinions']",  # More specific than the #id selector
            "#profile-reviews > div > div.card-footer.text-center > button",
            ".text-center button",
        ]

        initial_reviews_count = self._count_current_reviews()
        self.logger.info(f"Comentários iniciais encontrados: {initial_reviews_count}")

        method_start_time = time.time()
        method_timeout = 180  # 3 minutes

        while clicks_realizados < max_clicks:
            if time.time() - method_start_time > method_timeout:
                self.logger.warning(
                    f"Timeout de {method_timeout}s atingido para carregamento de comentários"
                )
                break

            try:
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                self.add_human_delay(1.0, 2.0)

                veja_mais_button = None
                for selector in button_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                veja_mais_button = element
                                self.logger.info(
                                    f"Botão 'Veja Mais' encontrado com seletor: {selector}"
                                )
                                break
                        if veja_mais_button:
                            break
                    except NoSuchElementException:
                        continue

                if not veja_mais_button:
                    self.logger.info(
                        "Botão 'Veja Mais' não encontrado ou não visível. Provavelmente todos os comentários foram carregados."
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
                    f"✅ Clique {clicks_realizados} realizado no botão 'Veja Mais'"
                )

                # Wait for new reviews to load using a reliable explicit wait
                wait = WebDriverWait(self.driver, 15)
                wait.until(lambda d: self._count_current_reviews() > reviews_before)

                reviews_after = self._count_current_reviews()
                self.logger.info(
                    f"Novos comentários carregados: {reviews_before} → {reviews_after}"
                )

                # Wait for page to stabilize after loading new content
                self.add_human_delay(2.0, 4.0)

            except TimeoutException:
                self.logger.warning(
                    f"Timeout esperando por novos comentários após clique {clicks_realizados}. Parando."
                )
                break
            except Exception as e:
                self.logger.warning(f"Erro ao clicar ou carregar mais comentários: {e}")
                break

        final_count = self._count_current_reviews()
        self.logger.info("📊 Carregamento concluído:")
        self.logger.info(f"   - Cliques realizados: {clicks_realizados}")
        self.logger.info(f"   - Comentários iniciais: {initial_reviews_count}")
        self.logger.info(f"   - Comentários finais: {final_count}")
        return clicks_realizados

    def clean_text(self, text: str) -> str:
        """Remove quebras de linha desnecessárias e espaços extras."""
        if not text:
            return ""
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned

    def extract_rating_from_html(self, review_element: Tag) -> Optional[int]:
        # <--- REFACTOR: Switched from regex to BeautifulSoup for more robust parsing.
        """Extrai a nota da avaliação usando BeautifulSoup."""
        if not review_element:
            return None
        try:
            rating_container = review_element.find("div", {"data-score": True})
            if (
                rating_container
                and isinstance(rating_container, Tag)
                and rating_container.has_attr("data-score")
            ):
                data_score = rating_container.get("data-score")
                if isinstance(data_score, str) and data_score.isdigit():
                    return int(data_score)
        except (ValueError, TypeError) as e:
            self.logger.debug(f"Não foi possível extrair nota: {e}")
        return None

    def extract_date_from_html(self, review_element: Tag) -> Optional[str]:
        # <--- REFACTOR: Simplified to use only BeautifulSoup, removing the redundant regex fallback.
        """Extrai a data da avaliação usando BeautifulSoup."""
        if not review_element:
            return None
        try:
            date_element = review_element.find("time", {"itemprop": "datePublished"})
            if (
                date_element
                and isinstance(date_element, Tag)
                and date_element.has_attr("datetime")
            ):
                datetime_attr = date_element.get("datetime")
                if isinstance(datetime_attr, str):
                    return datetime_attr
        except Exception as e:
            self.logger.debug(f"Erro ao parsear data com BS4: {e}")
        return None

    def extract_author_name(self, review_element: Tag) -> Optional[str]:
        # <--- REFACTOR: Changed signature to accept a Tag object for consistency.
        """Extrai o nome do autor da avaliação."""
        if not review_element:
            return None
        try:
            # The author's name is typically inside the review header
            header = review_element.find("div", class_="opinion-header")
            if header and isinstance(header, Tag):
                author_element = header.select_one('span[itemprop="name"]')
                if author_element and isinstance(author_element, Tag):
                    author_name = self.clean_text(author_element.get_text(strip=True))
                    # Heuristic to avoid picking up the doctor's name from a reply
                    if "Dra." not in author_name and "Dr." not in author_name:
                        return author_name
        except Exception as e:
            self.logger.debug(f"Erro ao parsear autor com BS4: {e}")
        return None

    def extract_comment(self, review_element: Tag) -> Optional[str]:
        """Extrai o comentário principal da avaliação usando BeautifulSoup."""
        comment_element = review_element.find("p", {"data-test-id": "opinion-comment"})
        if comment_element:
            return self.clean_text(comment_element.get_text(strip=True))
        return None

    def extract_reply_from_html(self, review_element: Tag) -> Optional[str]:
        """Extrai a resposta do médico ao comentário."""
        if not review_element:
            return None

        reply_element = review_element.find("div", {"data-id": "doctor-answer-content"})
        if reply_element and isinstance(reply_element, Tag):
            paragraphs = reply_element.find_all("p")
            # The first paragraph is often the doctor's name, the second is the reply.
            if len(paragraphs) > 1:
                return self.clean_text(paragraphs[1].get_text(strip=True))
            # Fallback to get all text if structure is different
            return self.clean_text(reply_element.get_text(strip=True))
        return None

    def scrape_reviews(self, url: str) -> Optional[Dict[str, Any]]:
        """Executa o scraping completo com retry e tratamento robusto de erros."""
        for attempt in range(self.config.scraping.max_retries):
            try:
                self.logger.info(
                    f"🚀 Iniciando scraping (tentativa {attempt + 1}/{self.config.scraping.max_retries})..."
                )
                if not self.setup_driver():
                    if attempt < self.config.scraping.max_retries - 1:
                        self.logger.warning(
                            "Falha na inicialização do driver, tentando novamente em 5s..."
                        )
                        time.sleep(5)
                        continue
                    else:
                        self.logger.error(
                            "❌ Falha definitiva na inicialização do navegador"
                        )
                        return None

                try:
                    if not url.startswith("https://www.doctoralia.com.br/"):
                        self.logger.error("URL deve ser do Doctoralia")
                        return None

                    if self.driver is None:  # Should not happen, but a good guard
                        raise Exception("Driver not available after setup")

                    self.logger.info(f"🌐 Acessando página: {url}")
                    self.driver.get(url)
                    WebDriverWait(
                        self.driver, self.config.scraping.explicit_wait
                    ).until(EC.presence_of_element_located((By.ID, "profile-reviews")))
                    self.add_human_delay()

                    self.logger.info("👨‍⚕️ Extraindo nome do médico...")
                    doctor_name = self.extract_doctor_name()
                    if doctor_name:
                        self.logger.info(f"Médico identificado: {doctor_name}")
                    else:
                        self.logger.warning(
                            "Não foi possível identificar o nome do médico."
                        )

                    self.logger.info("📚 Carregando todos os comentários...")
                    self.click_load_more_button()

                    self.logger.info("🔍 Processando comentários com BeautifulSoup...")
                    reviews_data = self._extract_all_reviews()

                    result = {
                        "url": url,
                        "doctor_name": doctor_name,
                        "extraction_timestamp": datetime.now().isoformat(),
                        "reviews": reviews_data,
                        "total_reviews": len(reviews_data),
                    }

                    self.logger.info(
                        f"✅ Extração concluída: {len(reviews_data)} comentários encontrados."
                    )
                    return result

                except Exception as e:
                    self.logger.error(
                        f"❌ Erro durante scraping (tentativa {attempt + 1}): {e}",
                        exc_info=True,
                    )
                    if attempt < self.config.scraping.max_retries - 1:
                        self.logger.info("🔄 Tentando novamente...")
                        self.safe_driver_quit()
                        time.sleep(5)
                    else:
                        return None
                finally:
                    self.safe_driver_quit()

            except Exception as e:
                self.logger.error(
                    f"❌ Erro crítico na tentativa {attempt + 1}: {e}", exc_info=True
                )
                if attempt < self.config.scraping.max_retries - 1:
                    time.sleep(10)
                else:
                    return None
        return None

    def _extract_all_reviews(self) -> List[Dict]:
        """Extrai dados de todas as avaliações da página atual usando BeautifulSoup."""
        if not self.driver:
            return []

        reviews_data: List[Dict[str, Any]] = []
        page_source = self.driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")

        review_elements = soup.find_all("div", {"data-test-id": "opinion-block"})
        self.logger.info(
            f"Encontrados {len(review_elements)} elementos de review com o seletor principal."
        )

        for i, review_element in enumerate(review_elements):
            try:
                comment = self.extract_comment(review_element)

                if not comment:
                    self.logger.warning(
                        f"Comentário {i + 1} ignorado por falta de texto."
                    )
                    continue

                # <--- REFACTOR: Pass the Tag object directly for consistency
                author = self.extract_author_name(review_element)
                rating = self.extract_rating_from_html(review_element)
                date = self.extract_date_from_html(review_element)
                reply = self.extract_reply_from_html(review_element)

                review_data = {
                    "id": i + 1,
                    "author": author,
                    "comment": comment,
                    "rating": rating,
                    "date": date,
                    "doctor_reply": reply,
                }

                review_data = {k: v for k, v in review_data.items() if v is not None}
                reviews_data.append(review_data)

            except Exception as e:
                self.logger.warning(f"Erro ao processar avaliação {i + 1}: {e}")
                continue

        self.logger.info(f"Extraídos {len(reviews_data)} comentários com sucesso.")
        return reviews_data

    def save_data(self, data: Dict[str, Any]) -> Optional[Path]:
        """Salva os dados extraídos em um arquivo JSON."""
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

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"💾 Dados salvos com sucesso em: {file_path}")
            return file_path
        except Exception as e:
            self.logger.error(f"Erro ao salvar os dados: {e}")
            return None

    def _count_current_reviews(self) -> int:
        """Conta o número atual de comentários na página."""
        if self.driver is None:
            return 0
        try:
            review_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "[data-test-id='opinion-block']"
            )
            return len(review_elements)
        except Exception as e:
            self.logger.debug(f"Erro ao contar comentários: {e}")
            return 0


if __name__ == "__main__":
    # URL do perfil do médico para extrair as avaliações
    target_url = (
        "https://www.doctoralia.com.br/bruna-pinto-gomes/ginecologista/belo-horizonte"
    )

    # Inicializa a configuração e o scraper
    config = MockConfig()
    scraper = DoctoraliaScraper(config=config, logger=logger)

    # Executa o scraping
    scraped_data = scraper.scrape_reviews(target_url)

    if scraped_data:
        logger.info("\n--- RESUMO DA EXTRAÇÃO ---")
        logger.info(f"Médico: {scraped_data.get('doctor_name')}")
        logger.info(
            f"Total de Avaliações Extraídas: {scraped_data.get('total_reviews')}"
        )

        # Salva os dados
        saved_file = scraper.save_data(scraped_data)

        # Imprime as primeiras 3 avaliações como exemplo
        if saved_file and scraped_data.get("reviews"):
            logger.info("\n--- AMOSTRA DAS AVALIAÇÕES ---")
            for i, review in enumerate(scraped_data.get("reviews", [])[:3]):
                logger.info(f"\nReview #{i + 1}:")
                logger.info(f"  Autor: {review.get('author', 'N/A')}")
                logger.info(f"  Nota: {review.get('rating', 'N/A')}")
                logger.info(f"  Data: {review.get('date', 'N/A')}")
                logger.info(f"  Comentário: {review.get('comment', '')[:100]}...")
                if review.get("doctor_reply"):
                    logger.info(
                        f"  Resposta: {review.get('doctor_reply', '')[:100]}..."
                    )
    else:
        logger.error("A extração de dados falhou após todas as tentativas.")

    def scrape_reviews(self, url: str) -> Optional[Dict[str, Any]]:
        """Executa o scraping completo com retry e tratamento robusto de erros"""
        for attempt in range(self.config.scraping.max_retries):
            try:
                self.logger.info(
                    f"🚀 Iniciando scraping (tentativa {attempt + 1}/{self.config.scraping.max_retries})..."
                )

                if not self.setup_driver():
                    if attempt < self.config.scraping.max_retries - 1:
                        self.logger.warning(
                            "Falha na inicialização do driver, tentando novamente em 5s..."
                        )
                        time.sleep(5)
                        continue
                    else:
                        self.logger.error(
                            "❌ Falha definitiva na inicialização do navegador"
                        )
                        return None

                try:
                    if not url.startswith("https://www.doctoralia.com.br/"):
                        self.logger.error("URL deve ser do Doctoralia")
                        return None

                    self.logger.info("🌐 Acessando página...")

                    def _load_page() -> None:
                        if self.driver is None:
                            raise Exception("Driver não inicializado")
                        self.driver.get(url)
                        # Verificar se a página carregou corretamente
                        WebDriverWait(
                            self.driver, self.config.scraping.explicit_wait
                        ).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

                    self.retry_on_failure(_load_page)
                    self.add_human_delay(3.0, 5.0)

                    self.logger.info("👨‍⚕️ Extraindo nome do médico...")
                    doctor_name = self.extract_doctor_name()
                    if doctor_name:
                        self.logger.info(f"Médico identificado: {doctor_name}")

                    self.logger.info("📝 Localizando comentários...")

                    def _find_reviews() -> Any:
                        if self.driver is None:
                            raise Exception("Driver não inicializado")
                        wait = WebDriverWait(
                            self.driver, self.config.scraping.explicit_wait
                        )
                        return wait.until(
                            EC.presence_of_element_located(
                                (
                                    By.CSS_SELECTOR,
                                    "#profile-reviews > div > div.card-body.opinions-list",
                                )
                            )
                        )

                    reviews_element = self.retry_on_failure(_find_reviews)

                    if self.driver is None:
                        raise Exception("Driver não inicializado")
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView(true);", reviews_element
                    )
                    time.sleep(3)

                    self.logger.info("📚 Carregando todos os comentários...")
                    clicks = self.click_load_more_button()
                    if clicks > 0:
                        self.logger.info(
                            f"Carregados comentários adicionais com {clicks} cliques"
                        )

                    # Atualizar elemento após carregar mais comentários
                    if self.driver is None:
                        raise Exception("Driver não inicializado")
                    reviews_element = self.driver.find_element(
                        By.CSS_SELECTOR,
                        "#profile-reviews > div > div.card-body.opinions-list",
                    )

                    self.logger.info("🔍 Processando comentários...")
                    reviews_data = self._extract_all_reviews()

                    result = {
                        "url": url,
                        "doctor_name": doctor_name,
                        "extraction_timestamp": datetime.now().isoformat(),
                        "reviews": reviews_data,
                        "total_reviews": len(reviews_data),
                    }

                    self.logger.info(
                        f"✅ Extração concluída: {len(reviews_data)} comentários"
                    )
                    return result

                except Exception as e:
                    self.logger.error(
                        f"❌ Erro durante scraping (tentativa {attempt + 1}): {e}"
                    )
                    if attempt < self.config.scraping.max_retries - 1:
                        self.logger.info("🔄 Tentando novamente...")
                        self.safe_driver_quit()
                        time.sleep(5)
                        continue
                    else:
                        return None

                finally:
                    self.safe_driver_quit()

            except Exception as e:
                self.logger.error(f"❌ Erro crítico na tentativa {attempt + 1}: {e}")
                if attempt < self.config.scraping.max_retries - 1:
                    time.sleep(10)
                    continue
                else:
                    return None

        return None

    def _extract_all_reviews(self) -> List[Dict]:
        """Extrai dados de todas as avaliações"""
        reviews_data: List[Dict[str, Any]] = []

        # Usar os mesmos seletores do método de contagem
        selectors = [
            "[data-test-id='opinion-block']",
            ".opinion.d-block",
            ".opinion-item",
            ".review-item",
            ".opinion",
        ]

        review_items = []
        selector_used = None

        for selector in selectors:
            if self.driver is None:
                break
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                # Filtrar elementos que realmente têm conteúdo de comentário
                valid_elements = []
                for element in elements:
                    try:
                        text = element.text.strip()
                        if (
                            len(text) > 50
                        ):  # Comentários válidos devem ter texto substancial
                            valid_elements.append(element)
                    except Exception:  # nosec B112
                        continue

                if valid_elements:
                    review_items = valid_elements
                    selector_used = selector
                    self.logger.info(
                        f"✅ Encontrados {len(valid_elements)} comentários válidos com seletor: {selector}"
                    )
                    break

        if not review_items:
            self.logger.warning(
                "❌ Nenhum comentário encontrado com os seletores padrão"
            )
            # Tentar seletores alternativos mais genéricos
            fallback_selectors = [
                "div[class*='opinion']",
                "div[class*='review']",
                "div[class*='comment']",
                ".card .card-body",
                ".review-content",
            ]

            for selector in fallback_selectors:
                if self.driver is None:
                    break
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    valid_elements = []
                    for element in elements:
                        try:
                            text = element.text.strip()
                            # Critério mais flexível para fallback
                            if len(text) > 30 and any(
                                keyword in text.lower()
                                for keyword in [
                                    "estrela",
                                    "recomendo",
                                    "consulta",
                                    "tratamento",
                                    "médic",
                                    "doutor",
                                ]
                            ):
                                valid_elements.append(element)
                        except Exception:  # nosec B112
                            continue

                    if valid_elements:
                        review_items = valid_elements
                        selector_used = f"{selector} (fallback)"
                        self.logger.info(
                            f"⚠️  Encontrados {len(valid_elements)} comentários com seletor fallback: {selector}"
                        )
                        break

            if not review_items:
                self.logger.error(
                    "❌ Nenhum comentário encontrado mesmo com seletores fallback"
                )
                return reviews_data

        self.logger.info(
            f"🔍 Processando {len(review_items)} comentários encontrados..."
        )
        self.logger.info(f"📋 Seletor utilizado: {selector_used}")
        successful_extractions = 0

        for i, review in enumerate(review_items):
            try:
                html = review.get_attribute("outerHTML")
                text = review.text.strip()

                self.logger.debug(
                    f"Processando comentário {i + 1}/{len(review_items)}..."
                )
                comment = self.extract_comment(text, html or "")

                if comment and len(comment) > 10:
                    author = self.extract_author_name(html or "")
                    rating = self.extract_rating_from_html(html or "")
                    date = self.extract_date_from_html(html or "")

                    # Log detalhado para debug da resposta
                    self.logger.debug(
                        f"Comentário {i + 1} - Autor: {author}, Data: {date}"
                    )
                    self.logger.debug(
                        f"Comentário {i + 1} - Buscando resposta do médico..."
                    )

                    reply = self.extract_reply_from_html(html or "")

                    if reply:
                        self.logger.debug(
                            f"Comentário {i + 1} - Resposta encontrada: {reply[:50]}..."
                        )
                    else:
                        self.logger.debug(
                            f"Comentário {i + 1} - Nenhuma resposta encontrada"
                        )
                        # Log adicional do HTML para debug (apenas primeiros 500 chars)
                        if html:
                            self.logger.debug(
                                f"HTML do comentário {i + 1}: {html[:500]}..."
                            )

                    review_data = {
                        "id": i + 1,
                        "author": author,
                        "comment": comment,
                        "rating": rating,
                        "date": date,
                        "doctor_reply": reply,
                    }

                    # Remove campos None
                    review_data = {
                        k: v for k, v in review_data.items() if v is not None
                    }
                    reviews_data.append(review_data)
                    successful_extractions += 1

                    self.logger.info(
                        f"✅ Comentário {i + 1} processado - Autor: {author}, Tem resposta: {'Sim' if reply else 'Não'}"
                    )
                else:
                    self.logger.debug(
                        f"❌ Comentário {i + 1} ignorado - conteúdo insuficiente"
                    )

            except Exception as e:
                self.logger.warning(f"Erro ao processar avaliação {i + 1}: {e}")
                continue

        self.logger.info(
            f"📊 Extração concluída: {successful_extractions}/{len(review_items)} comentários processados com sucesso"
        )
        return reviews_data

    def save_data(self, data: Dict[str, Any]) -> Path:
        """Salva dados em estrutura organizada"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        doctor_name = data.get("doctor_name", "unknown")

        if doctor_name and doctor_name != "unknown":
            clean_name = re.sub(r"[^\w\s-]", "", doctor_name)
            clean_name = re.sub(r"[-\s]+", "_", clean_name).lower().strip("_")
        else:
            clean_name = "unknown"

        save_dir = self.config.data_dir / "extractions" / f"{timestamp}_{clean_name}"
        save_dir.mkdir(parents=True, exist_ok=True)

        # Salvar dados completos
        main_file = save_dir / "complete_data.json"
        with open(main_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Separar comentários com e sem respostas
        with_replies = [r for r in data["reviews"] if r.get("doctor_reply")]
        without_replies = [r for r in data["reviews"] if not r.get("doctor_reply")]

        if with_replies:
            replies_file = save_dir / "with_replies.json"
            replies_data = {
                "doctor_name": data.get("doctor_name"),
                "url": data.get("url"),
                "extraction_timestamp": data.get("extraction_timestamp"),
                "reviews": with_replies,
                "total": len(with_replies),
            }
            with open(replies_file, "w", encoding="utf-8") as f:
                json.dump(replies_data, f, ensure_ascii=False, indent=2)

        if without_replies:
            no_replies_file = save_dir / "without_replies.json"
            no_replies_data = {
                "doctor_name": data.get("doctor_name"),
                "url": data.get("url"),
                "extraction_timestamp": data.get("extraction_timestamp"),
                "reviews": without_replies,
                "total": len(without_replies),
            }
            with open(no_replies_file, "w", encoding="utf-8") as f:
                json.dump(no_replies_data, f, ensure_ascii=False, indent=2)

        # Salvar resumo
        summary = {
            "doctor_name": data.get("doctor_name"),
            "url": data.get("url"),
            "extraction_timestamp": data.get("extraction_timestamp"),
            "statistics": {
                "total_reviews": len(data["reviews"]),
                "with_replies": len(with_replies),
                "without_replies": len(without_replies),
                "with_authors": sum(1 for r in data["reviews"] if r.get("author")),
                "with_ratings": sum(1 for r in data["reviews"] if r.get("rating")),
                "with_dates": sum(1 for r in data["reviews"] if r.get("date")),
            },
            "files_created": [
                "complete_data.json",
                "with_replies.json" if with_replies else None,
                "without_replies.json" if without_replies else None,
            ],
        }

        # Filtrar valores None da lista de arquivos criados
        files_created = summary.get("files_created", [])
        if isinstance(files_created, list):
            summary["files_created"] = [f for f in files_created if f is not None]

        summary_file = save_dir / "extraction_summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        self.logger.info(f"💾 Dados salvos em: {save_dir}")
        return Path(save_dir)

    def _count_current_reviews(self) -> int:
        """Conta o número atual de comentários na página"""
        if self.driver is None:
            return 0

        try:
            # Múltiplos seletores para encontrar comentários
            review_selectors = [
                "[data-test-id='opinion-block']",
                ".opinion.d-block",
                ".opinion-item",
                ".review-item",
                ".opinion",
            ]

            for selector in review_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Filtrar elementos que realmente são comentários (com texto suficiente)
                    valid_reviews = []
                    for element in elements:
                        try:
                            text = element.text.strip()
                            if (
                                len(text) > 50
                            ):  # Comentários válidos devem ter texto substancial
                                valid_reviews.append(element)
                        except Exception:  # nosec B112
                            continue

                    if valid_reviews:
                        return len(valid_reviews)

            return 0

        except Exception as e:
            self.logger.debug(f"Erro ao contar comentários: {e}")
            return 0
