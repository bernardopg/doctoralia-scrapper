from fastapi import APIRouter, Depends, status

from src.api.schemas.common import GeneratedResponsePreview
from src.api.schemas.requests import GenerateResponseRequest
from src.api.v1._helpers import raise_public_http_error
from src.api.v1._state import increment_generation_metric, load_config
from src.api.v1.deps import require_api_key

router = APIRouter(tags=["Generation"])


@router.post(
    "/v1/generate/response",
    response_model=GeneratedResponsePreview,
    dependencies=[Depends(require_api_key)],
)
async def generate_single_response(request: GenerateResponseRequest):
    from src.response_generator import ResponseGenerator

    config = load_config()
    generator = ResponseGenerator(config, logger=None)
    review = {
        "id": request.review_id,
        "author": request.author,
        "comment": request.comment,
        "rating": request.rating,
        "date": request.date,
    }
    doctor_context = {
        "name": request.doctor_name,
        "specialty": request.doctor_specialty,
        "profile_url": (
            str(request.doctor_profile_url) if request.doctor_profile_url else None
        ),
    }

    try:
        result = generator.generate_response_with_metadata(
            review,
            doctor_context=doctor_context,
            generation_mode=request.generation_mode,
            language=request.language or "pt-BR",
        )
    except ValueError as exc:
        raise_public_http_error(
            status.HTTP_400_BAD_REQUEST,
            "Invalid response generation request",
            exc=exc,
        )
    except Exception as exc:
        raise_public_http_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Failed to generate response",
            exc=exc,
        )

    increment_generation_metric()
    return GeneratedResponsePreview(
        review_id=request.review_id,
        text=result["text"],
        model=result["model"],
    )
