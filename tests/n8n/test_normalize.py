from src.integrations.n8n.normalize import extract_scraper_result, normalize_reviews


def test_extract_scraper_result_stringifies_review_ids():
    doctor, reviews = extract_scraper_result(
        {
            "doctor_name": "Dra. Ana",
            "url": "https://example.com/dra-ana",
            "reviews": [
                {
                    "id": 1,
                    "author": "Maria",
                    "comment": "Excelente atendimento",
                    "rating": 5,
                    "date": "2026-03-14",
                }
            ],
        }
    )

    assert doctor["name"] == "Dra. Ana"
    assert reviews[0]["id"] == "1"


def test_normalize_reviews_generates_missing_ids_and_accepts_numeric_ids():
    reviews = normalize_reviews(
        [
            {
                "id": 42,
                "author": "Joao",
                "comment": "Muito bom",
                "rating": 5,
                "date": "2026-03-13",
            },
            {
                "author": "Paula",
                "comment": "Gostei bastante",
                "rating": 4,
                "date": "2026-03-12",
            },
        ]
    )

    assert reviews[0].id == "42"
    assert reviews[1].id
