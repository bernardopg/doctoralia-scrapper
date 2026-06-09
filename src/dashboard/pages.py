"""Page-rendering blueprint — HTML routes only."""

from __future__ import annotations

from flask import Blueprint, render_template

from src.dashboard.services import DashboardServices


def create_blueprint(svc: DashboardServices) -> Blueprint:
    bp = Blueprint("pages", __name__)

    @bp.route("/")
    def index():
        return render_template("dashboard.html")

    @bp.route("/settings")
    def settings():
        return render_template("settings.html")

    @bp.route("/profiles")
    def profiles():
        return render_template("profiles.html")

    @bp.route("/responses")
    def responses():
        return render_template("responses.html")

    @bp.route("/me")
    def me():
        return render_template("user_profile.html")

    @bp.route("/history")
    def history():
        return render_template("history.html")

    @bp.route("/reports")
    def reports():
        return render_template("reports.html")

    @bp.route("/notifications/telegram/schedule")
    def notifications_telegram_schedule():
        return render_template("telegram_schedule.html")

    @bp.route("/health-check")
    def health_check_page():
        return render_template("health.html")

    return bp
