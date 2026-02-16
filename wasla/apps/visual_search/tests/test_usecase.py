from decimal import Decimal

from django.test import SimpleTestCase

from apps.visual_search.application.dto.visual_search_dto import VisualSearchQueryDTO
from apps.visual_search.application.usecases.visual_search_usecase import VisualSearchUseCase
from apps.visual_search.domain.entities import VisualSearchResult
from apps.visual_search.domain.value_objects import SimilarityScore


class _FakeRepository:
    def __init__(self, rows):
        self.rows = rows

    def find_similar_products(self, *, tenant_id: int, embedding_vector: list[float], limit: int):
        return self.rows[:limit]


class VisualSearchUseCaseTests(SimpleTestCase):
    def test_execute_maps_and_sorts_by_similarity(self):
        rows = [
            VisualSearchResult(
                product_id=2,
                similarity_score=SimilarityScore(0.60),
                extracted_attributes={"title": "B", "price": Decimal("20"), "image_url": ""},
            ),
            VisualSearchResult(
                product_id=1,
                similarity_score=SimilarityScore(0.91),
                extracted_attributes={"title": "A", "price": Decimal("10"), "image_url": ""},
            ),
        ]
        use_case = VisualSearchUseCase(repository=_FakeRepository(rows))
        result = use_case.execute(
            VisualSearchQueryDTO(tenant_id=1, image_url="https://example.com/x.jpg", max_results=10)
        )
        self.assertEqual(result[0].product_id, 1)

    def test_execute_returns_empty_fallback(self):
        use_case = VisualSearchUseCase(repository=_FakeRepository([]))
        result = use_case.execute(
            VisualSearchQueryDTO(tenant_id=1, image_url="https://example.com/x.jpg", max_results=10)
        )
        self.assertEqual(result, [])
