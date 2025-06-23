import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from bs4.element import PageElement
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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class DoctoraliaScraper:
    def __init__(self, config: Any, logger: Any) -> None:
        self.config = config
        self.logger = logger
        self.driver: Optional[webdriver.Chrome] = None
        self.skip_keywords = [
            "CONSULTA VERIFICADA",
            "Local:",
            "Solicitar revisão",
            "de maio de",
            "de junho de",
            "de janeiro de",
            "de fevereiro de",
            "de março de",
            "de abril de",
            "de julho de",
            "de agosto de",
            "de setembro de",
            "de outubro de",
            "de novembro de",
            "de dezembro de",
        ]

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

                # Use webdriver-manager to automatically manage ChromeDriver
                chromedriver_binary = ChromeDriverManager().install()

                options = Options()

                # Configurações básicas
                if self.config.scraping.headless:
                    options.add_argument("--headless=new")  # Usar novo modo headless

                # Configurações de estabilidade aprimoradas
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-software-rasterizer")
                options.add_argument("--window-size=1920,1080")
                options.add_argument(f"--user-agent={self.get_random_user_agent()}")

                # Configurações de memória e performance
                options.add_argument("--memory-pressure-off")
                options.add_argument("--max_old_space_size=4096")
                options.add_argument("--disable-background-timer-throttling")
                options.add_argument("--disable-renderer-backgrounding")
                options.add_argument("--disable-backgrounding-occluded-windows")

                # Suprimir logs
                options.add_argument("--disable-logging")
                options.add_argument("--log-level=3")
                options.add_argument("--silent")
                options.add_experimental_option("excludeSwitches", ["enable-logging"])
                options.add_experimental_option("useAutomationExtension", False)

                # Configurações de estabilidade
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--disable-extensions")
                options.add_argument("--disable-plugins")
                options.add_argument("--disable-images")
                options.add_argument("--disable-web-security")
                options.add_argument("--allow-running-insecure-content")

                # Configurações de rede
                options.add_argument("--aggressive-cache-discard")
                options.add_argument("--disable-background-networking")

                service = Service(chromedriver_binary)
                self.driver = webdriver.Chrome(service=service, options=options)

                # Configurar timeouts
                self.driver.set_page_load_timeout(
                    self.config.scraping.page_load_timeout
                )
                self.driver.implicitly_wait(self.config.scraping.implicit_wait)

                # Remover indicadores de automação
                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

                self.logger.info("✅ Navegador inicializado com sucesso")
                return True

            except SessionNotCreatedException as e:
                self.logger.warning(f"Erro de sessão na tentativa {attempt + 1}: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    continue
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
                    continue
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
                try:
                    # Tentar forçar encerramento
                    if self.driver and hasattr(self.driver, "service"):
                        service = self.driver.service
                        if service and hasattr(service, "process") and service.process:
                            service.process.terminate()
                except Exception:
                    pass
            finally:
                self.driver = None

    def add_human_delay(
        self, min_delay: Optional[float] = None, max_delay: Optional[float] = None
    ) -> None:
        """Adiciona delay aleatório para simular comportamento humano"""
        min_d = min_delay or self.config.scraping.delay_min
        max_d = max_delay or self.config.scraping.delay_max
        delay = random.uniform(min_d, max_d)
        time.sleep(delay)

    def retry_on_failure(
        self, func: Any, max_retries: Optional[int] = None, *args: Any, **kwargs: Any
    ) -> Any:
        """Executa uma função com retry automático em caso de falha"""
        max_retries_value = max_retries or self.config.scraping.max_retries or 3
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
                    f"Tentativa {attempt + 1}/{max_retries_value} falhou: {e}"
                )

                if attempt < max_retries_value - 1:
                    wait_time = (attempt + 1) * 2  # Backoff exponencial
                    self.logger.info(
                        f"Aguardando {wait_time}s antes da próxima tentativa..."
                    )
                    time.sleep(wait_time)
                    continue
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
        """Extrai o nome do médico da página"""
        css_selector = (
            "#object-profile > div.wrapper > div:nth-child(5) > main > "
            "div:nth-child(2) > div.row.unified-doctor-content > "
            "div.unified-doctor-content-column.col-md-8.col-lg-7.order-md-first "
            "> section.card.card-shadow-1.section-hero.pt-sm-2 > div > div > "
            "div.unified-doctor-header-info > div > "
            "div.d-flex.flex-column.align-items-left.justify-content-center."
            "w-100.pt-1-5.pt-sm-0.pl-sm-1 > div.d-flex.justify-content-between."
            "mb-0-5 > h1 > div > span:nth-child(2)"
        )

        def _extract_name() -> str:
            if self.driver is None:
                raise Exception("Driver não inicializado")
            wait = WebDriverWait(self.driver, self.config.scraping.explicit_wait)
            name_element = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector))
            )
            doctor_name = name_element.text.strip()
            return self.clean_text(doctor_name)

        try:
            doctor_name = self.retry_on_failure(_extract_name)
            return str(doctor_name) if doctor_name is not None else None
        except (TimeoutException, NoSuchElementException):
            self.logger.warning("Nome do médico não encontrado")
            return None
        except Exception as e:
            self.logger.error(f"Erro ao extrair nome do médico: {e}")
            return None

    def click_load_more_button(self) -> int:
        """Clica no botão 'Veja Mais' até carregar todos os comentários"""
        if self.driver is None:
            self.logger.error("Driver não inicializado")
            return 0

        clicks_realizados = 0
        max_clicks = 20  # Limite para evitar loops infinitos

        while clicks_realizados < max_clicks:
            try:
                if clicks_realizados > 0:
                    self.add_human_delay(2.0, 4.0)

                # Tentar encontrar o botão
                try:
                    veja_mais_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable(
                            (
                                By.CSS_SELECTOR,
                                "#profile-reviews > div > div.card-footer.text-center > a",
                            )
                        )
                    )
                except TimeoutException:
                    # Botão não encontrado ou não clicável
                    break

                if veja_mais_button.is_displayed() and veja_mais_button.is_enabled():
                    # Scroll para o botão
                    try:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                            veja_mais_button,
                        )
                        time.sleep(2)

                        # Tentar clicar
                        self.driver.execute_script(
                            "arguments[0].click();", veja_mais_button
                        )
                        clicks_realizados += 1
                        self.logger.info(
                            f"Clique {clicks_realizados} no botão 'Veja Mais'"
                        )

                        # Aguardar carregamento
                        time.sleep(4)

                        # Verificar se há novos comentários carregando
                        WebDriverWait(self.driver, 10).until(
                            lambda driver: driver.execute_script(
                                "return document.readyState"
                            )
                            == "complete"
                        )

                    except Exception as e:
                        self.logger.warning(f"Erro ao clicar no botão: {e}")
                        break
                else:
                    break

            except NoSuchElementException:
                # Botão não existe mais
                break
            except Exception as e:
                self.logger.warning(f"Erro no carregamento de comentários: {e}")
                if clicks_realizados < 2:
                    continue
                else:
                    break

        if clicks_realizados > 0:
            self.logger.info(f"Total de {clicks_realizados} cliques realizados")

        return clicks_realizados

    def clean_text(self, text: str) -> str:
        """Remove quebras de linha desnecessárias e espaços extras"""
        if not text:
            return ""

        cleaned = re.sub(r"\s+", " ", text.strip())
        cleaned = re.sub(
            r"[^\w\s.,!?áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ()-]", "", cleaned
        )
        return cleaned

    def extract_rating_from_html(self, html: str) -> Optional[int]:
        """Extrai a nota da avaliação do HTML"""
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")

            rating_element = soup.find(
                "div", attrs={"data-score": True, "itemprop": "ratingValue"}
            )
            if rating_element and isinstance(rating_element, Tag):
                data_score = rating_element.get("data-score")
                if data_score and str(data_score).isdigit():
                    return int(str(data_score))

            rating_element = soup.find(attrs={"data-score": True})
            if rating_element and isinstance(rating_element, Tag):
                data_score = rating_element.get("data-score")
                if data_score and str(data_score).isdigit():
                    return int(str(data_score))

        except Exception:
            pass

        # Fallback com regex
        rating_match = re.search(r'data-score="(\d+)"', html)
        if rating_match:
            return int(rating_match.group(1))

        return None

    def extract_date_from_html(self, html: str) -> Optional[str]:
        """Extrai a data da avaliação do HTML"""
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")

            date_element = soup.find(
                "time", attrs={"itemprop": "datePublished", "datetime": True}
            )
            if date_element and isinstance(date_element, Tag):
                datetime_value = date_element.get("datetime")
                if datetime_value:
                    return str(datetime_value)

        except Exception:
            pass

        # Fallback com regex
        date_match = re.search(r'datetime="([^"]+)"', html)
        if date_match:
            return date_match.group(1)

        return None

    def extract_author_name(self, html: str) -> Optional[str]:
        """Extrai o nome do autor da avaliação"""
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")

            author_element = soup.find("h4", attrs={"itemprop": "author"})
            if author_element and isinstance(author_element, Tag):
                span_element = author_element.find("span")
                if span_element and isinstance(span_element, Tag):
                    author_name = span_element.get_text(strip=True)
                    if author_name and len(author_name) > 1:
                        return self.clean_text(author_name)

        except Exception:
            pass

        return None

    def extract_comment(self, text: str, html: str) -> Optional[str]:
        """Extrai o comentário principal da avaliação"""
        if html:
            try:
                soup = BeautifulSoup(html, "html.parser")

                comment_element = soup.find("p", {"data-test-id": "opinion-comment"})
                if comment_element and isinstance(comment_element, Tag):
                    comment = comment_element.get_text(strip=True)
                    if len(comment) > 10:
                        return self.clean_text(comment)

            except Exception:
                pass

        # Processa o texto se não encontrou no HTML
        if not text:
            return None

        lines = text.split("\n")
        comment_lines = []

        for line in lines:
            line = line.strip()
            line_checks = [
                line and len(line) > 15,
                not any(keyword in line for keyword in self.skip_keywords),
                not re.match(r"^[A-Z]\.?$", line),
                not re.match(r"^\d+\s*de\s*\w+\s*de\s*\d+", line),
                not line.isupper(),
                "•" not in line,
                not re.match(r"^\d+\s*estrelas?", line, re.IGNORECASE),
            ]

            if all(line_checks):
                comment_lines.append(line)

        if comment_lines:
            return self.clean_text(" ".join(comment_lines))

        return None

    def extract_reply_from_html(self, html: str) -> Optional[str]:
        """Extrai a resposta do médico ao comentário"""
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Lista de seletores possíveis para respostas do médico
            reply_selectors = [
                'div[data-id="doctor-answer-content"]',
                ".doctor-answer",
                ".doctor-reply",
                ".professional-answer",
                ".response-content",
                '[data-test-id="doctor-answer"]',
                '[data-test-id="professional-response"]',
                ".opinion-response",
                ".reply-content",
                ".answer-content",
                ".professional-response",
                'div[class*="answer"]',
                'div[class*="reply"]',
                'div[class*="response"]',
            ]

            reply_element: Optional[PageElement] = None

            # Tenta encontrar o elemento da resposta com diferentes seletores
            for selector in reply_selectors:
                reply_element = soup.select_one(selector)
                if reply_element:
                    self.logger.debug(f"Resposta encontrada com seletor: {selector}")
                    break

            # Se não encontrou com seletores específicos, procura por padrões de texto
            if not reply_element:
                self.logger.debug("Procurando resposta por padrões de texto...")
                # Procura por divs que contenham texto típico de resposta médica
                potential_replies = soup.find_all(["div", "p", "span"])
                for element in potential_replies:
                    text = element.get_text(strip=True)
                    if (
                        text
                        and len(text) > 20
                        and any(
                            keyword in text.lower()
                            for keyword in [
                                "agradeço",
                                "obrigad",
                                "atenciosamente",
                                "dra.",
                                "dr.",
                                "fico feliz",
                                "conte comigo",
                                "à disposição",
                                "grata",
                                "muito obrigada",
                                "feliz que",
                                "saber que você",
                                "bruna",
                            ]
                        )
                    ):
                        reply_element = element
                        self.logger.debug(
                            f"Resposta encontrada por padrão de texto: {text[:50]}..."
                        )
                        break

                # Busca adicional por estrutura HTML específica
                if not reply_element:
                    # Procura por qualquer div que contenha "Dra. Bruna" ou similar
                    for element in soup.find_all(["div", "p"]):
                        text = element.get_text(strip=True)
                        dra_bruna_check = (
                            "dra." in text.lower() and "bruna" in text.lower()
                        )
                        atenciosamente_check = "atenciosamente" in text.lower()
                        agradeco_check = "agradeço" in text.lower() and len(text) > 30

                        if dra_bruna_check or atenciosamente_check or agradeco_check:
                            reply_element = element
                            self.logger.debug(
                                f"Resposta encontrada por nome do médico: {text[:50]}..."
                            )
                            break

            if reply_element and isinstance(reply_element, Tag):
                # Extrai texto de parágrafos
                paragraphs = reply_element.find_all("p")
                reply_text_parts = []

                for p in paragraphs:
                    if isinstance(p, Tag):
                        p_classes = p.get("class")
                        if p_classes and isinstance(p_classes, list):
                            if "small" in p_classes and "text-muted" in p_classes:
                                continue

                        text = p.get_text(strip=True)
                        if text and len(text) > 5:
                            reply_text_parts.append(text)

                # Se não encontrou parágrafos, pega o texto direto do elemento
                if not reply_text_parts:
                    direct_text = reply_element.get_text(strip=True)
                    if direct_text and len(direct_text) > 20:
                        reply_text_parts.append(direct_text)

                if reply_text_parts:
                    reply = " ".join(reply_text_parts)
                    cleaned_reply = self.clean_text(reply)

                    # Validação adicional para garantir que é realmente uma resposta médica
                    if len(cleaned_reply) > 15 and any(
                        keyword in cleaned_reply.lower()
                        for keyword in [
                            "agradeço",
                            "obrigad",
                            "atenciosamente",
                            "dra",
                            "dr",
                            "fico",
                            "conte",
                            "disposição",
                            "feliz",
                            "grata",
                            "bruna",
                        ]
                    ):
                        self.logger.debug(
                            f"Resposta extraída com sucesso: {cleaned_reply[:50]}..."
                        )
                        return cleaned_reply
                    else:
                        self.logger.debug(
                            f"Texto rejeitado (não parece resposta médica): {cleaned_reply[:50]}..."
                        )
                else:
                    self.logger.debug("Nenhum texto encontrado no elemento de resposta")
            else:
                self.logger.debug("Nenhum elemento de resposta encontrado no HTML")

        except Exception as e:
            self.logger.warning(f"Erro ao extrair resposta do médico: {e}")

        return None

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

        selectors = [
            "[data-test-id='opinion-block']",
            ".opinion.d-block",
            ".opinion-item",
            ".review-item",
            ".opinion",
        ]

        review_items = []
        for selector in selectors:
            if self.driver is None:
                break
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                review_items = elements
                self.logger.info(
                    f"Encontrados {len(elements)} comentários com seletor: {selector}"
                )
                break

        if not review_items:
            self.logger.warning("Nenhum comentário encontrado com os seletores padrão")
            return reviews_data

        for i, review in enumerate(review_items):
            try:
                html = review.get_attribute("outerHTML")
                text = review.text.strip()

                self.logger.debug(f"Processando comentário {i + 1}...")
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

                    self.logger.info(
                        f"Comentário {i + 1} processado - Autor: {author}, Tem resposta: {'Sim' if reply else 'Não'}"
                    )

            except Exception as e:
                self.logger.warning(f"Erro ao processar avaliação {i + 1}: {e}")
                continue

        self.logger.info(f"Total de comentários processados: {len(reviews_data)}")
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
