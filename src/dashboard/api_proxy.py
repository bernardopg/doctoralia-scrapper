"""API proxy blueprint — /api/health, /api/stats, /api/performance, /api/scrape, etc."""

from __future__ import annotations

from datetime import datetime

import requests
from flask import Blueprint, jsonify, request

from src.dashboard.services import DashboardServices
from src.multi_site_scraper import ScraperFactory


def create_blueprint(svc: DashboardServices) -> Blueprint:
    bp = Blueprint("api_proxy", __name__)

    @bp.route("/api/health")
    def health_check():
        return jsonify(
            {
                "dashboard": {
                    "status": "healthy",
                    "timestamp": datetime.now().isoformat(),
                    "version": "2.1.0",
                },
                "api": svc.get_api_health(),
            }
        )

    @bp.route("/api/ready")
    def proxy_ready():
        try:
            url = f"{svc.get_api_base_url()}/v1/ready"
            headers = {}
            api_key = svc.get_api_key()
            if api_key:
                headers["X-API-Key"] = api_key
            resp = requests.get(url, headers=headers, timeout=svc.api_timeout)
            if resp.status_code in (200, 503):
                return jsonify(resp.json()), resp.status_code
            return jsonify({"error": "API não disponível"}), 503
        except requests.exceptions.ConnectionError:
            return jsonify({"error": "API não está acessível"}), 503
        except Exception as e:
            return svc.error_response(
                "Falha ao consultar a API", status_code=503, exc=e
            )

    @bp.route("/api/stats")
    def get_stats():
        try:
            api_stats = svc.get_api_statistics()
            if api_stats:
                return jsonify({"source": "api", "data": api_stats})
            return jsonify({"source": "local", "data": svc.get_scraper_stats()})
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/performance")
    def get_performance():
        try:
            api_metrics = svc.get_api_metrics()
            if api_metrics:
                return jsonify({"source": "api", "data": api_metrics})
            if svc.performance_monitor:
                summary = svc.performance_monitor.get_summary()
                return jsonify({"source": "local", "data": summary})
            return jsonify(
                {
                    "source": "none",
                    "message": "No performance data available. Start the API with 'make api'",
                }
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/trends")
    def get_trends():
        try:
            return jsonify({"source": "local", "data": svc.get_trend_data()})
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/recent-activity")
    def get_recent_activity():
        try:
            return jsonify(svc.get_recent_activities())
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/quality-analysis", methods=["POST"])
    def analyze_quality():
        try:
            data = request.get_json(force=True, silent=True)
            if data is None:
                return jsonify({"error": "Invalid JSON in request body"}), 400
            response_text = data.get("response", "")
            original_review = data.get("original_review", "")
            if not response_text:
                return jsonify({"error": "Response text is required"}), 400
            if svc.quality_analyzer:
                analysis = svc.quality_analyzer.analyze_response(
                    response_text, original_review
                )
                return jsonify(
                    {
                        "score": analysis.score.to_dict(),
                        "strengths": analysis.strengths,
                        "weaknesses": analysis.weaknesses,
                        "suggestions": analysis.suggestions,
                        "keywords": analysis.keywords,
                        "sentiment": analysis.sentiment,
                        "readability_score": analysis.readability_score,
                    }
                )
            return jsonify({"error": "Quality analyzer not available"}), 503
        except Exception as e:
            return svc.error_response(
                "Falha ao analisar a qualidade da resposta", exc=e
            )

    @bp.route("/api/platforms")
    def get_platforms():
        try:
            if hasattr(ScraperFactory, "get_supported_platforms"):
                platforms = ScraperFactory.get_supported_platforms()
                return jsonify({"platforms": platforms})
            return jsonify({"platforms": ["doctoralia"]})
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/logs")
    def get_logs():
        try:
            lines = request.args.get("lines", default=50, type=int)
            return jsonify({"logs": svc.get_recent_logs(lines)})
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/scrape", methods=["POST"])
    def proxy_scrape():
        try:
            data = request.get_json(force=True, silent=True)
            if not data:
                return jsonify({"error": "Corpo da requisição inválido ou vazio"}), 400
            doctor_url = data.get("doctor_url") or data.get("url")
            if not doctor_url:
                return (
                    jsonify({"error": "Campo 'doctor_url' (ou 'url') é obrigatório"}),
                    400,
                )
            payload = {
                "doctor_url": doctor_url,
                "include_analysis": data.get("include_analysis", True),
                "include_generation": data.get("include_generation", False),
                "response_template_id": data.get("response_template_id"),
                "language": data.get("language", "pt"),
                "meta": data.get("meta"),
                "mode": "async",
                "callback_url": data.get("callback_url"),
                "idempotency_key": data.get("idempotency_key"),
            }
            result = svc.call_api("/v1/jobs", method="POST", json=payload)
            if result is not None:
                return jsonify(result)
            return (
                jsonify(
                    {"error": "API não disponível. Execute 'make api' para iniciar."}
                ),
                503,
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/tasks/<task_id>")
    def proxy_task_status(task_id: str):
        try:
            result = svc.call_api(f"/v1/jobs/{task_id}")
            if result is not None:
                return jsonify(result)
            return jsonify({"error": "API não disponível"}), 503
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/tasks")
    def proxy_list_tasks():
        try:
            task_status = request.args.get("status")
            endpoint = "/v1/jobs"
            if task_status:
                endpoint += f"?status={task_status}"
            result = svc.call_api(endpoint)
            if result is not None:
                return jsonify(result)
            return jsonify({"error": "API não disponível"}), 503
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/settings")
    def proxy_get_settings():
        try:
            result = svc.call_api("/v1/settings")
            if result is not None:
                return jsonify(result)
            return jsonify({"error": "API não disponível"}), 503
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/settings", methods=["PUT"])
    def proxy_update_settings():
        try:
            data = request.get_json(force=True, silent=True)
            result = svc.call_api("/v1/settings", method="PUT", json=data)
            if result is not None:
                return jsonify(result)
            return jsonify({"error": "API não disponível"}), 503
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/settings/validate", methods=["POST"])
    def proxy_validate_settings():
        try:
            data = request.get_json(force=True, silent=True)
            result = svc.call_api("/v1/settings/validate", method="POST", json=data)
            if result is not None:
                return jsonify(result)
            return jsonify({"error": "API não disponível"}), 503
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/generate/response", methods=["POST"])
    def proxy_generate_response():
        try:
            data = request.get_json(force=True, silent=True)
            result = svc.call_api("/v1/generate/response", method="POST", json=data)
            if result is not None:
                return jsonify(result)
            return jsonify({"error": "API não disponível"}), 503
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    return bp
