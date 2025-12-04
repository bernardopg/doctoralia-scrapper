"""
REST API for Doctoralia scraper operations.
Provides programmatic access to scraping, analysis, and monitoring features.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from typing import List
from typing import List as TypingList
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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

    def _execute_scraping_task(self, task_id: str, request: ScrapeRequest) -> None:
        """Execute scraping task in background."""
        try:
            self._update_task_status(task_id, "running", "Starting scraping operation")

            results = []
            total_urls = len(request.doctor_urls)

            for i, url in enumerate(request.doctor_urls):
                self._update_task_progress(task_id, i, total_urls, url)
                result = self._scrape_single_url(url, request)
                if result:
                    results.append(result)

                # Simulate processing time
                import time

                time.sleep(2)

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
        self, url: str, request: ScrapeRequest
    ) -> Optional[Dict[str, Any]]:
        """Scrape a single doctor URL."""
        try:
            if not self.scraper_factory:
                return None

            scraper = self.scraper_factory.create_scraper(url, self.config, self.logger)
            if not scraper:
                return None

            # Navigate to the page
            if not scraper.navigate_to_page(url):
                return None

            # Extract doctor information
            doctor_info = scraper.extract_doctor_info()

            # Extract reviews if requested
            reviews = []
            if request.include_reviews:
                reviews = scraper.extract_reviews()
                if request.max_reviews:
                    reviews = reviews[: request.max_reviews]

            # Combine results
            return {
                "doctor": {
                    "name": doctor_info.name,
                    "specialty": doctor_info.specialty,
                    "location": doctor_info.location,
                    "rating": doctor_info.rating,
                    "total_reviews": len(reviews),
                    "platform": doctor_info.platform,
                    "profile_url": doctor_info.profile_url,
                    "verified": doctor_info.verified,
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
                        "platform": review.platform,
                    }
                    for review in reviews
                ],
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
                data_dir = Path(self.config.data_dir) / "scraped_data"
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

            return {
                "reviews_count": data.get("summary", {}).get("total_reviews", 0),
                "avg_rating": data.get("summary", {}).get("average_rating", 0.0),
                "platform": data.get("platform", "unknown"),
                "scraped_at": data.get("scraped_at"),
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
        return TaskStatus(**task)

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
