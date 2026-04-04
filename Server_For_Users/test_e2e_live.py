"""End-to-end tests against the LIVE running server on localhost:5003."""
import requests
import sys

BASE = "http://localhost:5003"

def main():
    passed = 0
    total = 0

    # 1. Page loads
    total += 1
    r = requests.get(f"{BASE}/propertyFinder")
    assert r.status_code == 200
    assert "toggleModelInfo" in r.text, "Missing model info JS"
    print(f"[1] GET /propertyFinder -> {r.status_code} (page loads, model panel present)  PASS")
    passed += 1

    # 2. Metrics endpoint
    total += 1
    r = requests.get(f"{BASE}/api/metrics")
    m = r.json()
    assert m["r2"] > 0.65, f"R2 too low: {m['r2']}"
    print(f"[2] GET /api/metrics -> R2={m['r2']:.4f}, MAE={m['mae']:.2f}, RMSE={m['rmse']:.2f}  PASS")
    passed += 1

    # 3. Listings
    total += 1
    r = requests.get(f"{BASE}/api/listings")
    data = r.json()
    assert data["count"] >= 1
    print(f"[3] GET /api/listings -> {data['count']} properties on-sale  PASS")
    passed += 1

    # 4. Recommendation - urban apartment
    total += 1
    query1 = {
        "budget": 5, "area": 1200, "bedrooms": 2, "bathrooms": 2,
        "propertyType": "Apartment", "areaType": "Urban",
        "furnished": True, "parking": True,
        "facilities": ["Gym", "Swimming Pool", "Security"],
    }
    r = requests.post(f"{BASE}/api/recommend", json=query1)
    body1 = r.json()
    recs1 = body1.get("results", body1 if isinstance(body1, list) else [])
    assert len(recs1) > 0, f"No results: {body1}"
    assert recs1[0]["matchScore"] > 30
    print(f"[4] Recommend(apartment, 5ETH) -> {len(recs1)} results, top='{recs1[0]['title']}' ({recs1[0]['matchScore']:.1f}%)  PASS")
    passed += 1

    # 5. Recommendation - luxury villa
    total += 1
    query2 = {
        "budget": 20, "area": 5000, "bedrooms": 5, "bathrooms": 4,
        "propertyType": "Villa", "areaType": "Suburban",
        "furnished": True, "parking": True,
        "facilities": ["Garden", "Swimming Pool", "Security", "Power Backup"],
    }
    r = requests.post(f"{BASE}/api/recommend", json=query2)
    body2 = r.json()
    recs2 = body2.get("results", body2 if isinstance(body2, list) else [])
    assert len(recs2) > 0, f"No results: {body2}"
    print(f"[5] Recommend(villa, 20ETH) -> {len(recs2)} results, top='{recs2[0]['title']}' ({recs2[0]['matchScore']:.1f}%)  PASS")
    passed += 1

    # 6. Different queries -> different rankings
    total += 1
    different = recs1[0]["title"] != recs2[0]["title"] or abs(recs1[0]["matchScore"] - recs2[0]["matchScore"]) > 1
    assert different, "Different queries produced identical results"
    print(f"[6] Different queries produce different rankings  PASS")
    passed += 1

    # 7. Missing body returns 400
    total += 1
    r = requests.post(f"{BASE}/api/recommend")
    assert r.status_code == 400, f"Expected 400, got {r.status_code}"
    assert "error" in r.json()
    print(f"[7] POST /api/recommend (no body) -> {r.status_code} with error msg  PASS")
    passed += 1

    print(f"\n{'='*50}")
    print(f"  ALL {passed}/{total} LIVE E2E TESTS PASSED")
    print(f"{'='*50}")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
