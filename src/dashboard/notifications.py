"""Telegram notification blueprint — /api/notifications/telegram/*"""

from __future__ import annotations

from flask import Blueprint, request

from src.dashboard.services import DashboardServices


def create_blueprint(svc: DashboardServices) -> Blueprint:
    bp = Blueprint("notifications", __name__)

    @bp.route("/api/notifications/telegram/schedules")
    def get_schedules():
        try:
            return svc.proxy_api_response("/v1/notifications/telegram/schedules")
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/notifications/telegram/schedules", methods=["POST"])
    def create_schedule():
        try:
            data = request.get_json(force=True, silent=True) or {}
            return svc.proxy_api_response(
                "/v1/notifications/telegram/schedules", method="POST", json=data
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/notifications/telegram/schedules/<schedule_id>", methods=["PUT"])
    def update_schedule(schedule_id):
        try:
            data = request.get_json(force=True, silent=True) or {}
            return svc.proxy_api_response(
                f"/v1/notifications/telegram/schedules/{schedule_id}",
                method="PUT",
                json=data,
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/notifications/telegram/schedules/<schedule_id>", methods=["DELETE"])
    def delete_schedule(schedule_id):
        try:
            return svc.proxy_api_response(
                f"/v1/notifications/telegram/schedules/{schedule_id}",
                method="DELETE",
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route(
        "/api/notifications/telegram/schedules/<schedule_id>/run", methods=["POST"]
    )
    def run_schedule(schedule_id):
        try:
            return svc.proxy_api_response(
                f"/v1/notifications/telegram/schedules/{schedule_id}/run?wait=false",
                method="POST",
                json={},
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/notifications/telegram/history")
    def get_history():
        try:
            limit = request.args.get("limit", default=50, type=int)
            return svc.proxy_api_response(
                f"/v1/notifications/telegram/history?limit={limit}"
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/notifications/telegram/test", methods=["POST"])
    def send_test():
        try:
            data = request.get_json(force=True, silent=True) or {}
            return svc.proxy_api_response(
                "/v1/notifications/telegram/test", method="POST", json=data
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    return bp
