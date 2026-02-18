from django.test import SimpleTestCase

from apps.visual_search.domain.value_objects import SimilarityScore


class SimilarityScoreTests(SimpleTestCase):
    def test_score_in_range_passes(self):
        score = SimilarityScore(0.75)
        self.assertEqual(score.value, 0.75)

    def test_score_out_of_range_fails(self):
        with self.assertRaises(ValueError):
            SimilarityScore(1.2)
