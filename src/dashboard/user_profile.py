"""User profile blueprint — /api/user-profile/*"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from src.dashboard.services import DashboardServices, _clean_optional


def create_blueprint(svc: DashboardServices) -> Blueprint:
    bp = Blueprint("user_profile", __name__)

    @bp.route("/api/user-profile")
    def get_user_profile():
        try:
            return jsonify(svc.get_user_profile_settings())
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/user-profile", methods=["PUT"])
    def update_user_profile():
        try:
            payload = request.get_json(force=True, silent=True) or {}
            updated_settings = svc.update_remote_settings({"user_profile": payload})
            if updated_settings is None:
                return jsonify({"error": "API não disponível"}), 503
            return jsonify(updated_settings.get("user_profile", payload))
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/user-profile/favorites/toggle", methods=["POST"])
    def toggle_favorite_profile():
        try:
            data = request.get_json(force=True, silent=True) or {}
            profile_url = _clean_optional(data.get("profile_url"))
            profile_name = _clean_optional(data.get("name")) or "Perfil favorito"
            if not profile_url:
                return jsonify({"error": "profile_url é obrigatório"}), 400

            user_profile = svc.get_user_profile_settings()
            favorites = user_profile.get("favorite_profiles", [])
            normalized_url = profile_url.lower()
            existing = next(
                (
                    fav
                    for fav in favorites
                    if str(fav.get("profile_url", "")).strip().lower() == normalized_url
                ),
                None,
            )

            if existing:
                favorites = [
                    fav
                    for fav in favorites
                    if str(fav.get("profile_url", "")).strip().lower() != normalized_url
                ]
            else:
                favorites.append(
                    {
                        "name": profile_name,
                        "profile_url": profile_url,
                        "specialty": _clean_optional(data.get("specialty")),
                        "notes": _clean_optional(data.get("notes")),
                    }
                )

            user_profile["favorite_profiles"] = favorites
            updated_settings = svc.update_remote_settings(
                {"user_profile": user_profile}
            )
            if updated_settings is None:
                return jsonify({"error": "API não disponível"}), 503
            return jsonify(
                {
                    "success": True,
                    "favorite": existing is None,
                    "user_profile": updated_settings.get("user_profile", user_profile),
                }
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    return bp
