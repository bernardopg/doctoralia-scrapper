"""Reports blueprint — /api/reports/*"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List

from flask import Blueprint, Response, jsonify

from src.dashboard.services import DashboardServices


def create_blueprint(svc: DashboardServices) -> Blueprint:
    bp = Blueprint("reports", __name__)

    @bp.route("/api/reports/files")
    def get_report_files():
        try:
            files = svc.get_data_files()
            return jsonify({"files": files})
        except FileNotFoundError as e:
            return svc.error_response(
                "Diretório de dados não encontrado", status_code=404, exc=e
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/reports/export/<format_type>")
    def export_data(format_type: str):
        try:
            data = svc.get_export_data()
            if format_type == "json":
                content = json.dumps(data, ensure_ascii=False, indent=2)
                return Response(
                    content,
                    mimetype="application/json",
                    headers={
                        "Content-Disposition": "attachment; filename=doctoralia_export.json"
                    },
                )
            if format_type == "csv":
                content = _convert_to_csv(data)
                return Response(
                    content,
                    mimetype="text/csv; charset=utf-8",
                    headers={
                        "Content-Disposition": "attachment; filename=doctoralia_export.csv"
                    },
                )
            return jsonify({"error": f"Formato '{format_type}' não suportado"}), 400
        except FileNotFoundError as e:
            return svc.error_response(
                "Dados para exportação não encontrados", status_code=404, exc=e
            )
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    @bp.route("/api/reports/summary")
    def get_report_summary():
        try:
            return jsonify(svc.get_report_summary())
        except FileNotFoundError as e:
            return svc.error_response("Dados não encontrados", status_code=404, exc=e)
        except json.JSONDecodeError as e:
            return svc.error_response("Dados corrompidos", exc=e)
        except Exception as e:
            return svc.error_response("Erro interno do dashboard", exc=e)

    return bp


def _convert_to_csv(data: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "doctor_name",
            "extraction_date",
            "review_id",
            "author",
            "rating",
            "date",
            "comment",
            "generated_response",
        ]
    )
    for entry in data:
        doctor_name = entry.get("doctor_name", "")
        extraction_ts = entry.get("extraction_timestamp", "")
        for review in entry.get("reviews", []):
            writer.writerow(
                [
                    doctor_name,
                    extraction_ts,
                    review.get("id", ""),
                    review.get("author", ""),
                    review.get("rating", ""),
                    review.get("date", ""),
                    review.get("comment", ""),
                    review.get("generated_response", ""),
                ]
            )
    return output.getvalue()
