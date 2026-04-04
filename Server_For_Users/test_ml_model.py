"""
Tests for the ML Property Recommendation Model.

Run with:   py -m pytest test_ml_model.py -v
"""

import sys, os, json, shutil, tempfile, pathlib
import numpy as np
import pytest

# ── Ensure the module is importable ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from ml_recommender import (
    build_features,
    generate_training_data,
    train_model,
    recommend,
    get_model_metrics,
    seed_sample_data,
    _compute_relevance,
    _random_property,
    _random_query,
    FEATURE_COLS,
    MODEL_DIR,
    MODEL_PATH,
    SCALER_PATH,
    METRICS_PATH,
)


# ═════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ═════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def trained_metrics():
    """Train the model once for the whole test module."""
    metrics = train_model(n_samples=5000, verbose=False)
    return metrics


@pytest.fixture
def sample_query():
    return {
        "budget": 5, "minArea": 1000, "bedrooms": 3, "bathrooms": 2,
        "propertyType": "apartment", "areaType": "urban",
        "furnished": "semi-furnished",
        "facilities": ["school", "hospital", "metro"],
        "yearBuilt": 2020, "parking": True,
    }


@pytest.fixture
def sample_property():
    return {
        "price": 5.0, "area": 1500, "bedrooms": 3, "bathrooms": 2,
        "propertyType": "apartment", "areaType": "urban",
        "furnished": "semi-furnished",
        "facilities": ["school", "hospital", "metro", "park"],
        "yearBuilt": 2020, "parking": True,
    }


# ═════════════════════════════════════════════════════════════════════════
#  1.  TRAINING DATA GENERATION
# ═════════════════════════════════════════════════════════════════════════

class TestDataGeneration:
    def test_generates_correct_shape(self):
        X, y, df = generate_training_data(n_samples=100, seed=1)
        assert X.shape == (100, len(FEATURE_COLS))
        assert y.shape == (100,)
        assert len(df) == 100

    def test_labels_in_range(self):
        _, y, _ = generate_training_data(n_samples=500, seed=2)
        assert y.min() >= 0.0
        assert y.max() <= 100.0

    def test_no_nan_values(self):
        X, y, _ = generate_training_data(n_samples=200, seed=3)
        assert not np.isnan(X).any(), "Features contain NaN"
        assert not np.isnan(y).any(), "Labels contain NaN"

    def test_features_have_variance(self):
        X, _, _ = generate_training_data(n_samples=500, seed=4)
        # At least 80% of features should have non-zero variance
        variances = X.var(axis=0)
        assert (variances > 0).sum() / len(variances) > 0.8

    def test_deterministic_with_same_seed(self):
        X1, y1, _ = generate_training_data(n_samples=50, seed=99)
        X2, y2, _ = generate_training_data(n_samples=50, seed=99)
        np.testing.assert_array_equal(X1, X2)
        np.testing.assert_array_equal(y1, y2)


# ═════════════════════════════════════════════════════════════════════════
#  2.  FEATURE ENGINEERING
# ═════════════════════════════════════════════════════════════════════════

class TestFeatureEngineering:
    def test_feature_vector_length(self, sample_query, sample_property):
        vec = build_features(sample_query, sample_property)
        assert len(vec) == len(FEATURE_COLS)

    def test_perfect_match_flags(self, sample_query, sample_property):
        vec = build_features(sample_query, sample_property)
        # type_match, area_type_match, furnished_match, parking_match => indices 4,5,6,7
        assert vec[4] == 1.0  # type_match
        assert vec[5] == 1.0  # area_type_match
        assert vec[6] == 1.0  # furnished_match
        assert vec[7] == 1.0  # parking_match

    def test_price_ratio_correct(self, sample_query, sample_property):
        vec = build_features(sample_query, sample_property)
        expected_ratio = sample_property["price"] / sample_query["budget"]
        assert abs(vec[0] - expected_ratio) < 1e-6

    def test_area_ratio_correct(self, sample_query, sample_property):
        vec = build_features(sample_query, sample_property)
        expected_ratio = sample_property["area"] / sample_query["minArea"]
        assert abs(vec[1] - expected_ratio) < 1e-6

    def test_handles_missing_fields(self):
        vec = build_features({}, {})
        assert len(vec) == len(FEATURE_COLS)
        assert not np.isnan(vec).any()


# ═════════════════════════════════════════════════════════════════════════
#  3.  RELEVANCE SCORING (training labels)
# ═════════════════════════════════════════════════════════════════════════

class TestRelevanceScoring:
    def test_perfect_match_scores_high(self):
        """A property that exactly matches should score > 70."""
        query = {
            "budget": 5, "minArea": 1000, "bedrooms": 3, "bathrooms": 2,
            "propertyType": "apartment", "areaType": "urban",
            "furnished": "furnished", "facilities": ["school", "hospital"],
            "parking": True,
        }
        prop = {
            "price": 4.5, "area": 1200, "bedrooms": 3, "bathrooms": 2,
            "propertyType": "apartment", "areaType": "urban",
            "furnished": "furnished", "facilities": ["school", "hospital", "metro"],
            "parking": True,
        }
        scores = [_compute_relevance(query, prop) for _ in range(50)]
        avg = np.mean(scores)
        assert avg > 70, f"Perfect match average score ({avg:.1f}) should be > 70"

    def test_terrible_match_scores_low(self):
        """A completely mismatched pair should score < 40."""
        query = {
            "budget": 2, "minArea": 3000, "bedrooms": 5, "bathrooms": 4,
            "propertyType": "villa", "areaType": "rural",
            "furnished": "furnished", "facilities": ["airport", "railway"],
            "parking": True,
        }
        prop = {
            "price": 20, "area": 500, "bedrooms": 1, "bathrooms": 1,
            "propertyType": "apartment", "areaType": "urban",
            "furnished": "unfurnished", "facilities": ["metro"],
            "parking": False,
        }
        scores = [_compute_relevance(query, prop) for _ in range(50)]
        avg = np.mean(scores)
        assert avg < 40, f"Bad match average score ({avg:.1f}) should be < 40"


# ═════════════════════════════════════════════════════════════════════════
#  4.  MODEL TRAINING & ACCURACY METRICS
# ═════════════════════════════════════════════════════════════════════════

class TestModelTraining:
    def test_model_files_created(self, trained_metrics):
        assert MODEL_PATH.exists(), "Model pkl not saved"
        assert SCALER_PATH.exists(), "Scaler pkl not saved"
        assert METRICS_PATH.exists(), "Metrics JSON not saved"

    def test_r2_above_threshold(self, trained_metrics):
        """R² should be at least 0.65 (decent for synthetic data)."""
        assert trained_metrics["r2"] >= 0.65, (
            f"R² = {trained_metrics['r2']:.4f} is below 0.65 threshold"
        )

    def test_mae_below_threshold(self, trained_metrics):
        """MAE should be below 10 on 0-100 scale."""
        assert trained_metrics["mae"] < 10, (
            f"MAE = {trained_metrics['mae']:.2f} is too high (>10)"
        )

    def test_rmse_below_threshold(self, trained_metrics):
        """RMSE should be below 12 on 0-100 scale."""
        assert trained_metrics["rmse"] < 12, (
            f"RMSE = {trained_metrics['rmse']:.2f} is too high (>12)"
        )

    def test_cross_validation_stable(self, trained_metrics):
        """Cross-validation std should be < 0.05 (stable model)."""
        assert trained_metrics["cv_r2_std"] < 0.05, (
            f"CV R² std = {trained_metrics['cv_r2_std']:.4f} — model is unstable"
        )

    def test_feature_importances_exist(self, trained_metrics):
        top10 = trained_metrics["feature_importances_top10"]
        assert len(top10) == 10
        # price_ratio should be the most important feature
        assert "price_ratio" in top10

    def test_metrics_json_readable(self):
        metrics = get_model_metrics()
        assert metrics is not None
        assert "r2" in metrics
        assert "mae" in metrics
        assert "rmse" in metrics


# ═════════════════════════════════════════════════════════════════════════
#  5.  RECOMMENDATION INFERENCE
# ═════════════════════════════════════════════════════════════════════════

class TestRecommendation:
    def test_returns_list(self, sample_query):
        results = recommend(sample_query, top_n=5)
        assert isinstance(results, list)

    def test_respects_top_n(self, sample_query):
        results = recommend(sample_query, top_n=3)
        assert len(results) <= 3

    def test_results_have_match_score(self, sample_query):
        results = recommend(sample_query, top_n=5)
        for r in results:
            assert "matchScore" in r
            assert 0 <= r["matchScore"] <= 100

    def test_results_sorted_descending(self, sample_query):
        results = recommend(sample_query, top_n=10)
        scores = [r["matchScore"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_ideal_property_ranks_first(self):
        """A query targeting the Modern Downtown Apartment should rank it #1."""
        query = {
            "budget": 5, "minArea": 1000, "bedrooms": 3, "bathrooms": 2,
            "propertyType": "apartment", "areaType": "urban",
            "furnished": "semi-furnished",
            "facilities": ["metro", "hospital", "school"],
            "yearBuilt": 2020, "parking": True,
        }
        results = recommend(query, top_n=5)
        assert results[0]["title"] == "Modern Downtown Apartment", (
            f"Expected 'Modern Downtown Apartment' at #1, got '{results[0]['title']}'"
        )

    def test_budget_sensitive(self):
        """Lower budget should prefer cheaper properties."""
        low_budget = {
            "budget": 2, "minArea": 400, "bedrooms": 1, "bathrooms": 1,
            "propertyType": "apartment", "areaType": "urban",
            "facilities": [], "yearBuilt": 2020, "parking": False,
        }
        results = recommend(low_budget, top_n=3)
        # Top result should be under 4 ETH (budget-sensitive model)
        assert results[0]["price"] <= 4.0, (
            f"Top result price {results[0]['price']} ETH is too expensive for 2 ETH budget"
        )

    def test_empty_listings_returns_empty(self):
        """If no listings match, return empty list gracefully."""
        from pymongo import MongoClient
        db = MongoClient("mongodb://localhost:27017").LandRegistry
        # Temporarily rename the collection
        db.PropertyListings.rename("PropertyListings_backup")
        try:
            results = recommend({"budget": 5}, top_n=5)
            assert results == []
        finally:
            db.PropertyListings_backup.rename("PropertyListings")


# ═════════════════════════════════════════════════════════════════════════
#  6.  FLASK API ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════

class TestFlaskAPI:
    @pytest.fixture(autouse=True)
    def setup_app(self):
        sys.path.insert(0, os.path.dirname(__file__))
        import app as flask_app
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()

    def test_recommend_endpoint(self):
        resp = self.client.post(
            "/api/recommend",
            json={
                "budget": 5, "minArea": 1000, "bedrooms": 3,
                "propertyType": "apartment", "areaType": "urban",
                "facilities": ["school"],
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert "count" in data
        assert data["count"] > 0

    def test_recommend_missing_body(self):
        resp = self.client.post("/api/recommend", content_type="application/json")
        assert resp.status_code in (400, 500), "Should reject missing body"

    def test_listings_endpoint(self):
        resp = self.client.get("/api/listings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "listings" in data
        assert data["count"] >= 12

    def test_metrics_endpoint(self):
        resp = self.client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "r2" in data
        assert "mae" in data
        assert data["r2"] > 0.5

    def test_property_finder_page(self):
        resp = self.client.get("/propertyFinder")
        assert resp.status_code == 200
        assert b"Property Finder" in resp.data or b"propertyFinder" in resp.data


# ═════════════════════════════════════════════════════════════════════════
#  CLI runner
# ═════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
