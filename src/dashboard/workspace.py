"""Workspace blueprint — /api/workspace/*"""

from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from src.dashboard.services import DashboardServices, _clean_optional


def create_blueprint(svc: DashboardServices) -> Blueprint:
    bp = Blueprint("workspace", __name__)

    @bp.route("/api/workspace/overview")
    def get_overview():
        try:
            user_profile = svc.get_user_profile_settings()
            overview = svc.workspace_service.get_overview(
                profile_id=request.args.get("profile_id"),
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
                favorite_profiles=user_profile.get("favorite_profiles", []),
            )
            overview["user_profile"] = user_profile
            return jsonify(overview)
        except FileNotFoundError as e:
            return svc.error_response("Dados não encontrados", status_code=404, exc=e)
        except json.JSONDecodeError as e:
            return svc.error_response("Dados corrompidos", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/workspace/profiles")
    def get_profiles():
        try:
            user_profile = svc.get_user_profile_settings()
            profiles = svc.workspace_service.list_profiles(
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
                favorite_profiles=user_profile.get("favorite_profiles", []),
            )
            return jsonify({"profiles": profiles})
        except FileNotFoundError as e:
            return svc.error_response("Dados não encontrados", status_code=404, exc=e)
        except json.JSONDecodeError as e:
            return svc.error_response("Dados corrompidos", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/workspace/profile")
    def get_profile_detail():
        try:
            profile_id = request.args.get("profile_id")
            if not profile_id:
                return jsonify({"error": "profile_id é obrigatório"}), 400
            user_profile = svc.get_user_profile_settings()
            detail = svc.workspace_service.get_profile_detail(
                profile_id=profile_id,
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
                favorite_profiles=user_profile.get("favorite_profiles", []),
            )
            if detail is None:
                return jsonify({"error": "Perfil não encontrado"}), 404
            return jsonify(detail)
        except FileNotFoundError as e:
            return svc.error_response("Dados não encontrados", status_code=404, exc=e)
        except json.JSONDecodeError as e:
            return svc.error_response("Dados corrompidos", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/workspace/responses")
    def get_pending_responses():
        try:
            user_profile = svc.get_user_profile_settings()
            payload = svc.workspace_service.list_pending_responses(
                profile_id=request.args.get("profile_id"),
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
                favorite_profiles=user_profile.get("favorite_profiles", []),
                favorites_only=request.args.get("favorites_only") == "1",
                search=request.args.get("q"),
            )
            return jsonify(payload)
        except FileNotFoundError as e:
            return svc.error_response("Dados não encontrados", status_code=404, exc=e)
        except json.JSONDecodeError as e:
            return svc.error_response("Dados corrompidos", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/workspace/history")
    def get_history():
        try:
            payload = svc.workspace_service.get_history(
                profile_id=request.args.get("profile_id"),
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
                status=request.args.get("status"),
                search=request.args.get("q"),
            )
            return jsonify(payload)
        except FileNotFoundError as e:
            return svc.error_response("Dados não encontrados", status_code=404, exc=e)
        except json.JSONDecodeError as e:
            return svc.error_response("Dados corrompidos", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/workspace/history/delete", methods=["POST"])
    def delete_snapshot():
        try:
            payload = request.get_json(force=True, silent=True) or {}
            filename = _clean_optional(payload.get("filename"))
            if not filename:
                return jsonify({"error": "filename é obrigatório"}), 400
            deleted = svc.workspace_service.delete_snapshot(filename)
            if deleted is None:
                return jsonify({"error": "Snapshot não encontrado"}), 404
            return jsonify({"success": True, "deleted": deleted})
        except FileNotFoundError as e:
            return svc.error_response("Snapshot não encontrado", status_code=404, exc=e)
        except OSError as e:
            return svc.error_response("Erro ao acessar arquivo", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/workspace/history/prune", methods=["POST"])
    def prune_history():
        try:
            payload = request.get_json(force=True, silent=True) or {}
            result = svc.workspace_service.prune_outdated_snapshots(
                profile_id=_clean_optional(payload.get("profile_id")),
                date_from=_clean_optional(payload.get("date_from")),
                date_to=_clean_optional(payload.get("date_to")),
            )
            return jsonify({"success": True, "result": result})
        except OSError as e:
            return svc.error_response("Erro ao acessar arquivos", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/workspace/reports")
    def get_reports():
        try:
            user_profile = svc.get_user_profile_settings()
            payload = svc.workspace_service.get_reports(
                profile_id=request.args.get("profile_id"),
                date_from=request.args.get("date_from"),
                date_to=request.args.get("date_to"),
                favorite_profiles=user_profile.get("favorite_profiles", []),
            )
            return jsonify(payload)
        except FileNotFoundError as e:
            return svc.error_response("Dados não encontrados", status_code=404, exc=e)
        except json.JSONDecodeError as e:
            return svc.error_response("Dados corrompidos", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/workspace/responses/save", methods=["POST"])
    def save_generated_response():
        try:
            data = request.get_json(force=True, silent=True) or {}
            profile_id = _clean_optional(data.get("profile_id"))
            review_id = str(data.get("review_id") or "").strip()
            generated_response = _clean_optional(data.get("generated_response"))
            if not profile_id or not review_id or not generated_response:
                return (
                    jsonify(
                        {
                            "error": "profile_id, review_id e generated_response são obrigatórios"
                        }
                    ),
                    400,
                )
            saved = svc.workspace_service.save_generated_response(
                profile_id=profile_id,
                review_id=review_id,
                generated_response=generated_response,
            )
            if saved is None:
                return jsonify({"error": "Não foi possível salvar a sugestão"}), 404
            return jsonify({"success": True, "saved": saved})
        except FileNotFoundError as e:
            return svc.error_response("Snapshot não encontrado", status_code=404, exc=e)
        except OSError as e:
            return svc.error_response("Erro ao salvar resposta", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    return bp
