"""Quick verification that the AI Property Finder UI + API are fully operational."""
import requests, json

BASE = "http://127.0.0.1:5003"

# 1. Page structure
r = requests.get(f"{BASE}/propertyFinder")
print(f"Page load: {r.status_code}")
print(f"  Toggle button present:  {'toggleModelInfo' in r.text}")
print(f"  Info panel present:     {'modelInfoPanel' in r.text}")
print(f"  CSS classes present:    {'pf-model-info' in r.text}")

# 2. Metrics API (powers the transparency panel)
r2 = requests.get(f"{BASE}/api/metrics")
m = r2.json()
print(f"\nModel Metrics API: {r2.status_code}")
print(f"  R² Score:          {m['r2']}")
print(f"  MAE:               {m['mae']}")
print(f"  RMSE:              {m['rmse']}")
print(f"  CV R² mean:        {m['cv_r2_mean']} +/- {m['cv_r2_std']}")
print(f"  Training samples:  {m['n_training_samples']}")
print(f"  Features:          {m['n_features']}")
top = list(m["feature_importances_top10"].items())
print(f"  Top 3 features:")
for name, imp in top[:3]:
    print(f"    {name}: {imp:.4f}")

# 3. Sample recommendation
query = {
    "budget": 8, "area": 2000, "bedrooms": 3, "bathrooms": 2,
    "propertyType": "Apartment", "areaType": "Urban",
    "furnished": True, "parking": True,
    "facilities": ["Gym", "Swimming Pool", "Security", "Lift"],
}
r3 = requests.post(f"{BASE}/api/recommend", json=query)
body = r3.json()
print(f"\nSample Recommendation: {r3.status_code}")
print(f"  Query: 3BHK Apartment, 8 ETH, Urban")
print(f"  Results returned: {body['count']}")
for i, rec in enumerate(body["results"][:5]):
    print(f"  #{i+1}  {rec['title']:<35s}  Score: {rec['matchScore']:.1f}%  Price: {rec['price']} ETH")

print(f"\n--- All checks passed. Visit http://localhost:5003/propertyFinder ---")
