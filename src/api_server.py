"""
REST API for Doctoralia scraper operations.
Provides programmatic access to scraping, analysis, and monitoring features.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from typing import List
from typing import List as TypingList
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project root is in sys.path for proper imports
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import our modules
try:
    from config.settings import AppConfig
    from src.logger import setup_logger
    from src.multi_site_scraper import ScraperFactory
    from src.performance_monitor import PerformanceMonitor
    from src.response_quality_analyzer import ResponseQualityAnalyzer
    from src.scraper import DoctoraliaScraper
except ImportError:
    # Handle import errors gracefully
    AppConfig = None
    setup_logger = None
    PerformanceMonitor = None
    ResponseQualityAnalyzer = None
    ScraperFactory = None
    DoctoraliaScraper = None


# Pydantic models for API requests/responses
class ScrapeRequest(BaseModel):
    """Request model for scraping operations."""

    doctor_urls: TypingList[str] = Field(
        ..., description="List of doctor profile URLs to scrape"
    )
    platform: str = Field(default="doctoralia", description="Platform to scrape from")
    include_reviews: bool = Field(
        default=True, description="Whether to include reviews"
    )
    max_reviews: Optional[int] = Field(
        default=None, description="Maximum number of reviews to scrape per doctor"
    )


class QualityAnalysisRequest(BaseModel):
    """Request model for quality analysis."""

    response_text: str = Field(..., description="Doctor's response text to analyze")
    original_review: Optional[str] = Field(
        default=None, description="Original patient review for context"
    )


class BatchQualityAnalysisRequest(BaseModel):
    """Request model for batch quality analysis."""

    analyses: TypingList[QualityAnalysisRequest] = Field(
        ..., description="List of quality analysis requests"
    )


class ScrapeResponse(BaseModel):
    """Response model for scraping operations."""

    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status")
    message: str = Field(..., description="Status message")
    estimated_time: Optional[int] = Field(
        default=None, description="Estimated completion time in seconds"
    )


class TaskStatus(BaseModel):
    """Response model for task status."""

    task_id: str
    status: str
    progress: Optional[float] = None
    message: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None


class QualityAnalysisResponse(BaseModel):
    """Response model for quality analysis."""

    score: Dict[str, Any] = Field(..., description="Quality scores")
    strengths: List[str] = Field(..., description="Response strengths")
    weaknesses: List[str] = Field(..., description="Response weaknesses")
    suggestions: List[str] = Field(..., description="Improvement suggestions")
    keywords: List[str] = Field(..., description="Key terms identified")
    sentiment: str = Field(..., description="Overall sentiment")
    readability_score: float = Field(..., description="Readability score")


class StatisticsResponse(BaseModel):
    """Response model for statistics."""

    total_scraped_doctors: int
    total_reviews: int
    average_rating: float
    last_scrape_time: Optional[str]
    data_files: List[str]
    platform_stats: Dict[str, Any]


class TelegramSettingsModel(BaseModel):
    """Telegram configuration model."""

    token: Optional[str] = Field(None, description="Telegram bot token")
    chat_id: Optional[str] = Field(None, description="Telegram chat ID")
    parse_mode: str = Field(default="Markdown", description="Message parse mode")
    attach_responses_auto: bool = Field(
        default=True, description="Auto-attach responses file"
    )
    attachment_format: str = Field(default="txt", description="Attachment format")


class ScrapingSettingsModel(BaseModel):
    """Scraping configuration model."""

    headless: bool = Field(default=True, description="Run browser in headless mode")
    timeout: int = Field(default=60, ge=10, le=300, description="Operation timeout")
    delay_min: float = Field(
        default=2.0, ge=0.1, le=10.0, description="Minimum delay between actions"
    )
    delay_max: float = Field(
        default=4.0, ge=0.1, le=10.0, description="Maximum delay between actions"
    )
    max_retries: int = Field(default=5, ge=1, le=10, description="Maximum retries")
    page_load_timeout: int = Field(
        default=45, ge=10, le=120, description="Page load timeout"
    )
    implicit_wait: int = Field(default=20, ge=5, le=60, description="Implicit wait")
    explicit_wait: int = Field(default=30, ge=5, le=120, description="Explicit wait")


class APISettingsModel(BaseModel):
    """API configuration model."""

    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8080, ge=1024, le=65535, description="API port")
    debug: bool = Field(default=False, description="Debug mode")
    workers: int = Field(default=1, ge=1, le=8, description="Number of workers")


class SettingsModel(BaseModel):
    """Complete settings model."""

    telegram: TelegramSettingsModel = Field(..., description="Telegram settings")
    scraping: ScrapingSettingsModel = Field(..., description="Scraping settings")
    api: APISettingsModel = Field(..., description="API settings")


class SettingsResponse(BaseModel):
    """Response model for settings operations."""

    success: bool
    message: str
    settings: Optional[SettingsModel] = None


class DoctoraliaAPI:
    """
    FastAPI-based REST API for Doctoralia scraper operations.
    """

    def __init__(self, config: Any = None, logger: Any = None) -> None:
        self.config = config
        self.logger = logger or (setup_logger("api", config) if setup_logger else None)
        self.app = FastAPI(
            title="Doctoralia Scraper API",
            description="REST API for Doctoralia scraper operations and analysis",
            version="1.0.0",
        )

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Initialize components
        self.performance_monitor = (
            PerformanceMonitor(self.logger) if PerformanceMonitor else None
        )
        self.quality_analyzer = (
            ResponseQualityAnalyzer() if ResponseQualityAnalyzer else None
        )
        self.scraper_factory = ScraperFactory() if ScraperFactory else None

        # Initialize health checker
        try:
            from src.health_checker import HealthChecker

            self.health_checker = HealthChecker(self.config) if self.config else None
        except ImportError:
            self.health_checker = None

        # In-memory task storage (in production, use a database)
        self.tasks: Dict[str, Dict[str, Any]] = {}

        self.setup_routes()

    def setup_routes(self) -> None:
        """Setup FastAPI routes."""
        self._setup_basic_routes()
        self._setup_scraping_routes()
        self._setup_analysis_routes()
        self._setup_monitoring_routes()
        self._setup_task_management_routes()
        self._setup_settings_routes()

    def _setup_basic_routes(self) -> None:
        """Setup basic API routes."""

        @self.app.get("/")
        async def root():
            """API root endpoint."""
            return {
                "message": "Doctoralia Scraper API",
                "version": "1.0.0",
                "docs": "/docs",
                "health": "/health",
            }

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint com verificações detalhadas."""
            if self.health_checker:
                try:
                    health_status = await self.health_checker.check_all()
                    overall_status = "healthy"

                    if any(
                        status.status == "unhealthy"
                        for status in health_status.values()
                    ):
                        overall_status = "unhealthy"
                    elif any(
                        status.status == "degraded" for status in health_status.values()
                    ):
                        overall_status = "degraded"

                    return {
                        "status": overall_status,
                        "timestamp": datetime.now().isoformat(),
                        "version": "1.0.0",
                        "checks": {
                            name: {
                                "status": check.status,
                                "response_time_ms": check.response_time_ms,
                                "details": check.details,
                            }
                            for name, check in health_status.items()
                        },
                    }
                except Exception as e:
                    return {
                        "status": "unhealthy",
                        "timestamp": datetime.now().isoformat(),
                        "version": "1.0.0",
                        "error": str(e),
                    }

            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "message": "Basic health check (detailed checks not available)",
            }

    def _setup_scraping_routes(self) -> None:
        """Setup scraping-related routes."""

        @self.app.post("/scrape", response_model=ScrapeResponse)
        async def start_scraping(
            request: ScrapeRequest, background_tasks: BackgroundTasks
        ):
            """Start a scraping task."""
            return self._handle_start_scraping(request, background_tasks)

        @self.app.get("/platforms")
        async def get_supported_platforms():
            """Get list of supported platforms."""
            return self._handle_get_platforms()

    def _setup_analysis_routes(self) -> None:
        """Setup analysis-related routes."""

        @self.app.post("/analyze/quality", response_model=QualityAnalysisResponse)
        async def analyze_quality(request: QualityAnalysisRequest):
            """Analyze the quality of a doctor's response."""
            return self._handle_quality_analysis(request)

        @self.app.post(
            "/analyze/quality/batch", response_model=List[QualityAnalysisResponse]
        )
        async def analyze_quality_batch(request: BatchQualityAnalysisRequest):
            """Analyze the quality of multiple doctor's responses."""
            return self._handle_batch_quality_analysis(request)

    def _setup_monitoring_routes(self) -> None:
        """Setup monitoring-related routes."""

        @self.app.get("/statistics", response_model=StatisticsResponse)
        async def get_statistics():
            """Get comprehensive scraping statistics."""
            return self._handle_get_statistics()

        @self.app.get("/performance")
        async def get_performance_metrics():
            """Get performance metrics."""
            return self._handle_get_performance()

    def _setup_task_management_routes(self) -> None:
        """Setup task management routes."""

        @self.app.get("/tasks/{task_id}", response_model=TaskStatus)
        async def get_task_status(task_id: str):
            """Get the status of a task."""
            return self._handle_get_task_status(task_id)

        @self.app.get("/tasks", response_model=List[TaskStatus])
        async def list_tasks(
            status: Optional[str] = Query(None, description="Filter by status")
        ):
            """List all tasks."""
            return self._handle_list_tasks(status)

        @self.app.delete("/tasks/{task_id}")
        async def delete_task(task_id: str):
            """Delete a completed task."""
            return self._handle_delete_task(task_id)

    def _setup_settings_routes(self) -> None:
        """Setup settings management routes."""

        @self.app.get("/settings", response_model=SettingsResponse)
        async def get_settings():
            """Get current application settings."""
            return self._handle_get_settings()

        @self.app.put("/settings", response_model=SettingsResponse)
        async def update_settings(settings: SettingsModel):
            """Update application settings."""
            return self._handle_update_settings(settings)

        @self.app.post("/settings/validate", response_model=SettingsResponse)
        async def validate_settings(settings: SettingsModel):
            """Validate settings without saving."""
            return self._handle_validate_settings(settings)

    def _execute_scraping_task(self, task_id: str, request: ScrapeRequest) -> None:
        """Execute scraping task in background."""
        try:
            self._update_task_status(task_id, "running", "Iniciando scraping...")

            results = []
            total_urls = len(request.doctor_urls)

            for i, url in enumerate(request.doctor_urls):
                base_progress = (i / total_urls) * 100
                url_weight = 100.0 / total_urls
                self.tasks[task_id]["progress"] = base_progress
                self.tasks[task_id]["message"] = f"Processando {i + 1}/{total_urls}: {url}"
                result = self._scrape_single_url(url, request, task_id, base_progress, url_weight)
                if result:
                    results.append(result)

            self._complete_task_successfully(task_id, results)

        except Exception as e:
            self._complete_task_with_error(task_id, str(e))

    def _update_task_status(self, task_id: str, status: str, message: str) -> None:
        """Update task status and message."""
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["message"] = message

    def _update_task_progress(
        self, task_id: str, current: int, total: int, url: str
    ) -> None:
        """Update task progress."""
        progress = (current / total) * 100
        self.tasks[task_id]["progress"] = progress
        self.tasks[task_id]["message"] = f"Processing {current + 1}/{total}: {url}"

    def _scrape_single_url(
        self, url: str, request: ScrapeRequest,
        task_id: Optional[str] = None, base_progress: float = 0.0, url_weight: float = 100.0
    ) -> Optional[Dict[str, Any]]:
        """Scrape a single doctor URL using DoctoraliaScraper."""
        try:
            # Use DoctoraliaScraper directly like main.py does
            if not DoctoraliaScraper:
                if self.logger:
                    self.logger.error("DoctoraliaScraper not available")
                return None

            scraper = DoctoraliaScraper(self.config, self.logger)

            # Set up progress callback if we have a task_id
            if task_id:
                # Progress ranges per phase within the url_weight allocation:
                # page_loading:      5% - 10%
                # extracting_info:  10% - 15%
                # loading_reviews:  15% - 90% (incremental based on clicks)
                # processing_reviews: 90% - 95%
                max_expected_clicks = 20  # Estimate for scaling progress

                def on_progress(phase: str, detail: dict) -> None:
                    if phase == "page_loading":
                        pct = 0.07
                        msg = "Carregando página..."
                    elif phase == "extracting_info":
                        pct = 0.12
                        msg = "Extraindo informações do médico..."
                    elif phase == "loading_reviews":
                        clicks = detail.get("clicks", 0)
                        reviews = detail.get("reviews_loaded", 0)
                        # Scale from 15% to 88% based on clicks
                        click_ratio = min(clicks / max_expected_clicks, 1.0)
                        pct = 0.15 + click_ratio * 0.73
                        msg = f"Carregando reviews... ({reviews} encontrados, {clicks} cliques)"
                    elif phase == "processing_reviews":
                        pct = 0.92
                        msg = "Processando reviews..."
                    else:
                        pct = 0.5
                        msg = "Processando..."

                    progress = base_progress + url_weight * pct
                    self.tasks[task_id]["progress"] = min(progress, base_progress + url_weight * 0.99)
                    self.tasks[task_id]["message"] = msg

                scraper.progress_callback = on_progress

            data = scraper.scrape_reviews(url)

            if not data:
                if self.logger:
                    self.logger.warning(f"No data returned for {url}")
                return None

            # Persist to disk so stats/dashboard can read it
            scraper.save_data(data)

            # Format result matching what dashboard expects
            doctor_name = data.get("doctor", {}).get("name", "Unknown")
            reviews = data.get("reviews", [])

            # Limit reviews if max_reviews specified
            if request.max_reviews and len(reviews) > request.max_reviews:
                reviews = reviews[:request.max_reviews]

            return {
                "doctor": {
                    "name": doctor_name,
                    "specialty": data.get("doctor", {}).get("specialty", ""),
                    "location": data.get("doctor", {}).get("location", ""),
                    "rating": data.get("summary", {}).get("average_rating", 0),
                    "total_reviews": len(reviews),
                    "platform": data.get("platform", "doctoralia"),
                    "profile_url": url,
                    "verified": True,
                },
                "reviews": reviews,
                "summary": data.get("summary", {}),
                "scraped_at": data.get("scraped_at"),
            }

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error scraping {url}: {e}")
            return None

    def _complete_task_successfully(
        self, task_id: str, results: List[Dict[str, Any]]
    ) -> None:
        """Complete task successfully."""
        self.tasks[task_id]["status"] = "completed"
        self.tasks[task_id]["progress"] = 100.0
        self.tasks[task_id]["message"] = f"Completed scraping {len(results)} profiles"
        self.tasks[task_id]["completed_at"] = datetime.now()
        self.tasks[task_id]["result"] = {
            "total_processed": len(results),
            "results": results,
        }

    def _complete_task_with_error(self, task_id: str, error_message: str) -> None:
        """Complete task with error."""
        self.tasks[task_id]["status"] = "failed"
        self.tasks[task_id]["message"] = f"Task failed: {error_message}"
        self.tasks[task_id]["completed_at"] = datetime.now()
        if self.logger:
            self.logger.error(f"Scraping task {task_id} failed: {error_message}")

    def _get_scraper_stats(self) -> Dict[str, Any]:
        """Get comprehensive scraper statistics."""
        stats = self._initialize_stats_structure()

        try:
            if self.config and hasattr(self.config, "data_dir"):
                data_dir = Path(self.config.data_dir)
                if data_dir.exists():
                    json_files = list(data_dir.glob("*.json"))
                    stats["data_files"] = [f.name for f in json_files]

                    self._process_data_files(json_files, stats)

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error getting scraper stats: {e}")

        return stats

    def _initialize_stats_structure(self) -> Dict[str, Any]:
        """Initialize the statistics structure."""
        return {
            "total_scraped_doctors": 0,
            "total_reviews": 0,
            "average_rating": 0.0,
            "last_scrape_time": None,
            "data_files": [],
            "platform_stats": {},
        }

    def _process_data_files(
        self, json_files: List[Path], stats: Dict[str, Any]
    ) -> None:
        """Process JSON data files to extract statistics."""
        total_reviews = 0
        total_rating = 0.0
        doctors_count = 0
        platforms = {}

        for json_file in json_files:
            file_stats = self._process_single_data_file(json_file)
            if file_stats:
                doctors_count += 1
                total_reviews += file_stats["reviews_count"]
                if file_stats["avg_rating"] > 0:
                    total_rating += file_stats["avg_rating"]

                self._update_platform_stats(
                    platforms, file_stats["platform"], file_stats["reviews_count"]
                )

                scraped_at = file_stats["scraped_at"]
                if scraped_at and (
                    not stats["last_scrape_time"]
                    or scraped_at > stats["last_scrape_time"]
                ):
                    stats["last_scrape_time"] = scraped_at

        stats["total_scraped_doctors"] = doctors_count
        stats["total_reviews"] = total_reviews
        stats["average_rating"] = total_rating / max(doctors_count, 1)
        stats["platform_stats"] = platforms

    def _process_single_data_file(self, json_file: Path) -> Optional[Dict[str, Any]]:
        """Process a single JSON data file."""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Support both flat format (from scraper.save_data) and nested format
            reviews = data.get("reviews", [])
            reviews_count = data.get("total_reviews", 0) or len(reviews)

            # Try nested format first, fall back to flat
            if "summary" in data:
                avg_rating = data["summary"].get("average_rating", 0.0)
            else:
                # Calculate from reviews
                ratings = [r.get("rating", 0) for r in reviews if r.get("rating")]
                avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

            platform = data.get("platform", "doctoralia")
            scraped_at = data.get("scraped_at") or data.get("extraction_timestamp")

            return {
                "reviews_count": reviews_count,
                "avg_rating": avg_rating,
                "platform": platform,
                "scraped_at": scraped_at,
            }

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Error reading {json_file}: {e}")
            return None

    def _update_platform_stats(
        self, platforms: Dict[str, Any], platform: str, reviews_count: int
    ) -> None:
        """Update platform statistics."""
        if platform not in platforms:
            platforms[platform] = {"doctors": 0, "reviews": 0}
        platforms[platform]["doctors"] += 1
        platforms[platform]["reviews"] += reviews_count

    def _handle_start_scraping(
        self, request: ScrapeRequest, background_tasks: BackgroundTasks
    ) -> ScrapeResponse:
        """Handle scraping task initiation."""
        try:
            task_id = f"scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(request.doctor_urls)}"

            # Initialize task
            self.tasks[task_id] = {
                "status": "pending",
                "progress": 0.0,
                "message": "Task initialized",
                "created_at": datetime.now(),
                "completed_at": None,
                "result": None,
                "request": request.dict(),
            }

            # Start background task
            background_tasks.add_task(self._execute_scraping_task, task_id, request)

            return ScrapeResponse(
                task_id=task_id,
                status="pending",
                message="Scraping task started",
                estimated_time=len(request.doctor_urls) * 30,  # Rough estimate
            )

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to start scraping: {str(e)}"
            )

    def _handle_get_task_status(self, task_id: str) -> TaskStatus:
        """Handle task status retrieval."""
        if task_id not in self.tasks:
            raise HTTPException(status_code=404, detail="Task not found")

        task = self.tasks[task_id]
        return TaskStatus(task_id=task_id, **task)

    def _handle_list_tasks(self, status: Optional[str]) -> List[TaskStatus]:
        """Handle task listing."""
        tasks = []
        for task_id, task_data in self.tasks.items():
            if status is None or task_data["status"] == status:
                tasks.append(TaskStatus(task_id=task_id, **task_data))

        return tasks

    def _handle_quality_analysis(
        self, request: QualityAnalysisRequest
    ) -> QualityAnalysisResponse:
        """Handle single quality analysis."""
        try:
            if not self.quality_analyzer:
                raise HTTPException(
                    status_code=503, detail="Quality analyzer not available"
                )

            analysis = self.quality_analyzer.analyze_response(
                request.response_text, request.original_review
            )

            return QualityAnalysisResponse(
                score=analysis.score.to_dict(),
                strengths=analysis.strengths,
                weaknesses=analysis.weaknesses,
                suggestions=analysis.suggestions,
                keywords=analysis.keywords,
                sentiment=analysis.sentiment,
                readability_score=analysis.readability_score,
            )

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Quality analysis failed: {str(e)}"
            )

    def _handle_batch_quality_analysis(
        self, request: BatchQualityAnalysisRequest
    ) -> List[QualityAnalysisResponse]:
        """Handle batch quality analysis."""
        try:
            if not self.quality_analyzer:
                raise HTTPException(
                    status_code=503, detail="Quality analyzer not available"
                )

            results = []
            for analysis_request in request.analyses:
                analysis = self.quality_analyzer.analyze_response(
                    analysis_request.response_text, analysis_request.original_review
                )

                results.append(
                    QualityAnalysisResponse(
                        score=analysis.score.to_dict(),
                        strengths=analysis.strengths,
                        weaknesses=analysis.weaknesses,
                        suggestions=analysis.suggestions,
                        keywords=analysis.keywords,
                        sentiment=analysis.sentiment,
                        readability_score=analysis.readability_score,
                    )
                )

            return results

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Batch quality analysis failed: {str(e)}"
            )

    def _handle_get_statistics(self) -> StatisticsResponse:
        """Handle statistics retrieval."""
        try:
            stats = self._get_scraper_stats()
            return StatisticsResponse(**stats)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to get statistics: {str(e)}"
            )

    def _handle_get_platforms(self) -> Dict[str, List[str]]:
        """Handle platforms retrieval."""
        try:
            if self.scraper_factory:
                platforms = self.scraper_factory.get_supported_platforms()
                return {"platforms": platforms}
            return {"platforms": ["doctoralia"]}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to get platforms: {str(e)}"
            )

    def _handle_get_performance(self) -> Dict[str, Any]:
        """Handle performance metrics retrieval."""
        try:
            if self.performance_monitor:
                summary = self.performance_monitor.get_summary()
                return summary
            return {"message": "Performance monitoring not available"}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to get performance metrics: {str(e)}"
            )

    def _handle_delete_task(self, task_id: str) -> Dict[str, str]:
        """Handle task deletion."""
        if task_id not in self.tasks:
            raise HTTPException(status_code=404, detail="Task not found")

        task = self.tasks[task_id]
        if task["status"] not in ["completed", "failed"]:
            raise HTTPException(status_code=400, detail="Cannot delete active task")

        del self.tasks[task_id]
        return {"message": "Task deleted successfully"}

    def _handle_get_settings(self) -> SettingsResponse:
        """Get current settings."""
        try:
            if not self.config or not AppConfig:
                return SettingsResponse(
                    success=False,
                    message="Configuration not available",
                    settings=None,
                )

            # Convert AppConfig to SettingsModel
            settings = SettingsModel(
                telegram=TelegramSettingsModel(
                    token=self.config.telegram.token,
                    chat_id=self.config.telegram.chat_id,
                    parse_mode=self.config.telegram.parse_mode,
                    attach_responses_auto=self.config.telegram.attach_responses_auto,
                    attachment_format=self.config.telegram.attachment_format,
                ),
                scraping=ScrapingSettingsModel(
                    headless=self.config.scraping.headless,
                    timeout=self.config.scraping.timeout,
                    delay_min=self.config.scraping.delay_min,
                    delay_max=self.config.scraping.delay_max,
                    max_retries=self.config.scraping.max_retries,
                    page_load_timeout=self.config.scraping.page_load_timeout,
                    implicit_wait=self.config.scraping.implicit_wait,
                    explicit_wait=self.config.scraping.explicit_wait,
                ),
                api=APISettingsModel(
                    host=self.config.api.host,
                    port=self.config.api.port,
                    debug=self.config.api.debug,
                    workers=self.config.api.workers,
                ),
            )

            return SettingsResponse(
                success=True, message="Settings retrieved successfully", settings=settings
            )

        except Exception as e:
            return SettingsResponse(
                success=False,
                message=f"Failed to get settings: {str(e)}",
                settings=None,
            )

    def _handle_update_settings(self, settings: SettingsModel) -> SettingsResponse:
        """Update and save settings."""
        try:
            if not self.config or not AppConfig:
                return SettingsResponse(
                    success=False,
                    message="Configuration not available",
                    settings=None,
                )

            # Validate settings
            validation_result = self._validate_settings_internal(settings)
            if not validation_result["valid"]:
                return SettingsResponse(
                    success=False,
                    message=f"Validation failed: {', '.join(validation_result['errors'])}",
                    settings=None,
                )

            # Update config object
            self.config.telegram.token = settings.telegram.token
            self.config.telegram.chat_id = settings.telegram.chat_id
            self.config.telegram.parse_mode = settings.telegram.parse_mode
            self.config.telegram.attach_responses_auto = (
                settings.telegram.attach_responses_auto
            )
            self.config.telegram.attachment_format = settings.telegram.attachment_format

            self.config.scraping.headless = settings.scraping.headless
            self.config.scraping.timeout = settings.scraping.timeout
            self.config.scraping.delay_min = settings.scraping.delay_min
            self.config.scraping.delay_max = settings.scraping.delay_max
            self.config.scraping.max_retries = settings.scraping.max_retries
            self.config.scraping.page_load_timeout = settings.scraping.page_load_timeout
            self.config.scraping.implicit_wait = settings.scraping.implicit_wait
            self.config.scraping.explicit_wait = settings.scraping.explicit_wait

            self.config.api.host = settings.api.host
            self.config.api.port = settings.api.port
            self.config.api.debug = settings.api.debug
            self.config.api.workers = settings.api.workers

            # Save to file
            self.config.save()

            if self.logger:
                self.logger.info("Settings updated successfully")

            return SettingsResponse(
                success=True,
                message="Settings updated successfully. Restart required for some changes to take effect.",
                settings=settings,
            )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to update settings: {e}")
            return SettingsResponse(
                success=False,
                message=f"Failed to update settings: {str(e)}",
                settings=None,
            )

    def _handle_validate_settings(self, settings: SettingsModel) -> SettingsResponse:
        """Validate settings without saving."""
        try:
            validation_result = self._validate_settings_internal(settings)

            if validation_result["valid"]:
                return SettingsResponse(
                    success=True,
                    message="Settings are valid",
                    settings=settings,
                )
            else:
                return SettingsResponse(
                    success=False,
                    message=f"Validation failed: {', '.join(validation_result['errors'])}",
                    settings=None,
                )

        except Exception as e:
            return SettingsResponse(
                success=False,
                message=f"Validation error: {str(e)}",
                settings=None,
            )

    def _validate_settings_internal(self, settings: SettingsModel) -> Dict[str, Any]:
        """Internal settings validation."""
        errors = []

        # Validate scraping settings
        if settings.scraping.delay_min > settings.scraping.delay_max:
            errors.append("delay_min cannot be greater than delay_max")

        if settings.scraping.delay_min < 0 or settings.scraping.delay_max < 0:
            errors.append("Delays cannot be negative")

        if settings.scraping.timeout < 10:
            errors.append("Timeout must be at least 10 seconds")

        if settings.scraping.max_retries < 1:
            errors.append("max_retries must be at least 1")

        # Validate API settings
        if settings.api.port < 1024 or settings.api.port > 65535:
            errors.append("API port must be between 1024 and 65535")

        if settings.api.workers < 1:
            errors.append("Workers must be at least 1")

        # Validate Telegram settings (if enabled)
        if settings.telegram.token and not settings.telegram.chat_id:
            errors.append("chat_id is required when telegram token is provided")

        if settings.telegram.parse_mode not in ["", "Markdown", "MarkdownV2", "HTML"]:
            errors.append("Invalid parse_mode")

        if settings.telegram.attachment_format not in ["txt", "json", "csv"]:
            errors.append("Invalid attachment_format")

        return {"valid": len(errors) == 0, "errors": errors}

    def run(self, host: str = None, port: int = None) -> None:
        """Run the API server."""
        import uvicorn

        # Use config values if available, otherwise defaults
        if host is None:
            host = self.config.api.host if self.config and hasattr(self.config, 'api') else "0.0.0.0"
        if port is None:
            port = self.config.api.port if self.config and hasattr(self.config, 'api') else 8000

        if self.logger:
            self.logger.info(f"Starting API server on http://{host}:{port}")
        uvicorn.run(self.app, host=host, port=port)


# Create API instance
def create_api_app(config: Any = None, logger: Any = None) -> DoctoraliaAPI:
    """Create and configure the API application."""
    # Load config if not provided
    if config is None and AppConfig is not None:
        config = AppConfig.load()
    return DoctoraliaAPI(config, logger)


if __name__ == "__main__":
    # Initialize and run API
    config = AppConfig.load() if AppConfig else None
    api = create_api_app(config)
    api.run()
