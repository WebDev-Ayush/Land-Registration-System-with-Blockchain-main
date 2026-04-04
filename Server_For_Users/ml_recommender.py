"""
ML Property Recommendation Engine
==================================
Uses a **Gradient Boosting Regressor** trained on synthetic buyer–property
interaction data to predict a match score (0–100) for any (query, property)
pair.

Training pipeline
-----------------
1. ``generate_training_data()`` creates 10 000 synthetic (buyer_pref, property,
   relevance_score) rows.  The relevance_score is computed with domain rules
   (budget fit, bedroom match, type match, facility overlap, etc.) plus
   Gaussian noise so the model must *learn* the patterns rather than memorise.
2. ``train_model()`` fits a ``GradientBoostingRegressor`` with 5-fold
   cross-validation, reports **R², MAE, RMSE** on the held-out test set,
   and persists the model + scaler to disk via ``joblib``.
3. ``recommend()`` loads the trained model and scores every on-sale listing
   against the buyer query, returning the top-N ranked results.

The model is trained **once** at startup (or on demand via the API) and
cached on disk at ``model/property_model.pkl``.
"""

import os, json, random, pathlib, warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from pymongo import MongoClient

warnings.filterwarnings("ignore", category=UserWarning)

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

FACILITY_LIST = [
    "school", "hospital", "metro", "park", "mall",
    "gym", "bus_stop", "railway", "airport", "market",
    "bank", "atm", "restaurant", "temple", "playground",
]
PROPERTY_TYPES = ["apartment", "villa", "plot", "independent_house"]
AREA_TYPES     = ["urban", "suburban", "rural"]
FURNISHED_TYPES = ["furnished", "semi-furnished", "unfurnished"]

MODEL_DIR  = pathlib.Path(__file__).parent / "model"
MODEL_PATH = MODEL_DIR / "property_model.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
METRICS_PATH = MODEL_DIR / "metrics.json"

# ═══════════════════════════════════════════════════════════════════════════
#  FEATURE ENGINEERING  (shared between training & inference)
# ═══════════════════════════════════════════════════════════════════════════

def _feature_names():
    """Return ordered list of feature column names."""
    names = [
        # ── delta / ratio features (query vs property) ──
        "price_ratio",          # property_price / buyer_budget
        "area_ratio",           # property_area  / buyer_minArea
        "bedroom_diff",         # abs(prop - query)
        "bathroom_diff",
        # ── match flags ──
        "type_match",           # 1 if same propertyType
        "area_type_match",      # 1 if same areaType
        "furnished_match",      # 1 if same furnished
        "parking_match",        # 1 if both want/have parking
        # ── property raw (so model can learn non-linear effects) ──
        "prop_price", "prop_area", "prop_bedrooms", "prop_bathrooms",
        "prop_yearBuilt", "prop_parking",
        # ── property type one-hot ──
    ]
    names += [f"prop_type_{t}" for t in PROPERTY_TYPES]
    # area type one-hot
    names += [f"prop_atype_{t}" for t in AREA_TYPES]
    # furnished one-hot
    names += [f"prop_furn_{t}" for t in FURNISHED_TYPES]
    # facility overlap count + individual facility matches
    names += ["facility_overlap_count", "facility_overlap_ratio"]
    names += [f"fac_match_{f}" for f in FACILITY_LIST]
    # year built diff
    names += ["year_diff"]
    return names


FEATURE_COLS = _feature_names()


def build_features(query: dict, prop: dict) -> np.ndarray:
    """Build a single feature row for the (query, property) pair."""
    f = []

    budget   = float(query.get("budget", 0)) or 1.0
    min_area = float(query.get("minArea", 0)) or 1.0

    prop_price = float(prop.get("price", 0))
    prop_area  = float(prop.get("area", 0))

    # delta / ratio
    f.append(prop_price / budget)                              # price_ratio
    f.append(prop_area / min_area)                             # area_ratio
    f.append(abs(int(prop.get("bedrooms",0)) - int(query.get("bedrooms",0))))
    f.append(abs(int(prop.get("bathrooms",0)) - int(query.get("bathrooms",0))))

    # match flags
    q_type = query.get("propertyType","").lower()
    p_type = prop.get("propertyType","").lower()
    f.append(1.0 if q_type and q_type == p_type else 0.0)

    q_atype = query.get("areaType","").lower()
    p_atype = prop.get("areaType","").lower()
    f.append(1.0 if q_atype and q_atype == p_atype else 0.0)

    q_furn = str(query.get("furnished","")).lower()
    p_furn = str(prop.get("furnished","")).lower()
    f.append(1.0 if q_furn and q_furn == p_furn else 0.0)

    q_park = bool(query.get("parking"))
    p_park = bool(prop.get("parking"))
    f.append(1.0 if q_park == p_park else 0.0)

    # property raw
    f.append(prop_price)
    f.append(prop_area)
    f.append(float(prop.get("bedrooms", 0)))
    f.append(float(prop.get("bathrooms", 0)))
    f.append(float(prop.get("yearBuilt", 2020)))
    f.append(1.0 if p_park else 0.0)

    # property type one-hot
    for t in PROPERTY_TYPES:
        f.append(1.0 if p_type == t else 0.0)
    for t in AREA_TYPES:
        f.append(1.0 if p_atype == t else 0.0)
    for t in FURNISHED_TYPES:
        f.append(1.0 if p_furn == t else 0.0)

    # facility overlap
    q_facs = set(fac.lower().strip() for fac in query.get("facilities", []))
    p_facs = set(fac.lower().strip() for fac in prop.get("facilities", []))
    overlap = q_facs & p_facs
    f.append(float(len(overlap)))
    f.append(len(overlap) / max(len(q_facs), 1))
    for fac in FACILITY_LIST:
        f.append(1.0 if (fac in q_facs and fac in p_facs) else 0.0)

    # year diff
    q_year = int(query.get("yearBuilt", 2020))
    p_year = int(prop.get("yearBuilt", 2020))
    f.append(float(abs(p_year - q_year)))

    return np.array(f, dtype=np.float64)


# ═══════════════════════════════════════════════════════════════════════════
#  SYNTHETIC TRAINING DATA GENERATION
# ═══════════════════════════════════════════════════════════════════════════

def _random_property():
    pt = random.choice(PROPERTY_TYPES)
    at = random.choice(AREA_TYPES)
    beds = random.choice([0,1,2,3,4,5]) if pt != "plot" else 0
    baths = max(0, beds - random.randint(0, 2)) if pt != "plot" else 0
    area = random.randint(300, 6000)
    price = round(random.uniform(0.5, 30.0), 1)
    furn = random.choice(FURNISHED_TYPES) if pt != "plot" else "unfurnished"
    parking = random.choice([True, False])
    year = random.randint(1990, 2025)
    n_fac = random.randint(1, 8)
    facs = random.sample(FACILITY_LIST, min(n_fac, len(FACILITY_LIST)))
    return {
        "price": price, "area": area, "bedrooms": beds, "bathrooms": baths,
        "propertyType": pt, "areaType": at, "furnished": furn,
        "parking": parking, "yearBuilt": year, "facilities": facs,
    }


def _random_query():
    pt = random.choice(PROPERTY_TYPES + [""])  # "" = any
    at = random.choice(AREA_TYPES + [""])
    beds = random.randint(0, 5)
    baths = random.randint(0, 4)
    budget = round(random.uniform(1.0, 25.0), 1)
    min_area = random.randint(400, 4000)
    furn = random.choice(FURNISHED_TYPES + [""])
    parking = random.choice([True, False])
    year = random.randint(2000, 2025)
    n_fac = random.randint(0, 6)
    facs = random.sample(FACILITY_LIST, min(n_fac, len(FACILITY_LIST)))
    return {
        "budget": budget, "minArea": min_area, "bedrooms": beds,
        "bathrooms": baths, "propertyType": pt, "areaType": at,
        "furnished": furn, "parking": parking, "yearBuilt": year,
        "facilities": facs,
    }


def _compute_relevance(query, prop):
    """
    Domain-rule based relevance score (0-100) used as the training *label*.

    This encodes how a real buyer would rate a property:
      - Within budget?  +25 pts
      - Meets area requirement?  +15 pts
      - Bedrooms match?  +15 pts
      - Property type match?  +15 pts
      - Area type match?  +10 pts
      - Facility overlap?  +10 pts
      - Furnished match?  +5 pts
      - Parking match?  +5 pts
    Plus Gaussian noise (σ=5) to prevent the model from memorising rules.
    """
    score = 0.0

    # Budget fit (25 pts)
    budget = float(query.get("budget", 0))
    price  = float(prop.get("price", 0))
    if budget > 0:
        ratio = price / budget
        if ratio <= 1.0:
            score += 25.0
        elif ratio <= 1.15:
            score += 18.0
        elif ratio <= 1.3:
            score += 10.0
        else:
            score += max(0, 25 - (ratio - 1) * 30)

    # Area fit (15 pts)
    min_area = float(query.get("minArea", 0))
    area     = float(prop.get("area", 0))
    if min_area > 0:
        if area >= min_area:
            score += 15.0
        elif area >= min_area * 0.8:
            score += 10.0
        else:
            score += max(0, 15 - (1 - area / min_area) * 40)

    # Bedroom match (15 pts)
    bed_diff = abs(int(prop.get("bedrooms",0)) - int(query.get("bedrooms",0)))
    score += max(0, 15 - bed_diff * 5)

    # Property type match (15 pts)
    q_type = query.get("propertyType","").lower()
    p_type = prop.get("propertyType","").lower()
    if q_type == "" or q_type == p_type:
        score += 15.0
    else:
        score += 2.0  # small credit for any property

    # Area type match (10 pts)
    q_at = query.get("areaType","").lower()
    p_at = prop.get("areaType","").lower()
    if q_at == "" or q_at == p_at:
        score += 10.0
    else:
        score += 2.0

    # Facility overlap (10 pts)
    q_facs = set(f.lower() for f in query.get("facilities", []))
    p_facs = set(f.lower() for f in prop.get("facilities", []))
    if len(q_facs) > 0:
        overlap_ratio = len(q_facs & p_facs) / len(q_facs)
        score += overlap_ratio * 10.0

    # Furnished match (5 pts)
    q_furn = str(query.get("furnished","")).lower()
    p_furn = str(prop.get("furnished","")).lower()
    if q_furn == "" or q_furn == p_furn:
        score += 5.0

    # Parking match (5 pts)
    if bool(query.get("parking")) == bool(prop.get("parking")):
        score += 5.0

    # Add noise so model learns generalisable patterns
    score += random.gauss(0, 5)
    return max(0.0, min(100.0, round(score, 2)))


def generate_training_data(n_samples=10000, seed=42):
    """
    Generate synthetic training dataset of (buyer_query, property, score) rows.

    Returns
    -------
    X : np.ndarray  (n_samples, n_features)
    y : np.ndarray  (n_samples,)
    df : pd.DataFrame  (the full dataframe for inspection)
    """
    random.seed(seed)
    np.random.seed(seed)

    rows = []
    for _ in range(n_samples):
        query = _random_query()
        prop  = _random_property()
        features = build_features(query, prop)
        score = _compute_relevance(query, prop)
        rows.append((*features, score))

    columns = FEATURE_COLS + ["relevance_score"]
    df = pd.DataFrame(rows, columns=columns)

    X = df[FEATURE_COLS].values
    y = df["relevance_score"].values

    return X, y, df


# ═══════════════════════════════════════════════════════════════════════════
#  MODEL TRAINING & EVALUATION
# ═══════════════════════════════════════════════════════════════════════════

def train_model(n_samples=10000, verbose=True):
    """
    Train a GradientBoostingRegressor, evaluate, and save to disk.

    Returns
    -------
    dict  with keys: r2, mae, rmse, cv_r2_mean, cv_r2_std, feature_importances
    """
    if verbose:
        print("=" * 60)
        print("  PROPERTY RECOMMENDATION MODEL — TRAINING PIPELINE")
        print("=" * 60)

    # 1. Generate data
    if verbose:
        print(f"\n[1/4] Generating {n_samples} synthetic training samples...")
    X, y, df = generate_training_data(n_samples)
    if verbose:
        print(f"       Features per sample : {X.shape[1]}")
        print(f"       Target range        : {y.min():.1f} – {y.max():.1f}")
        print(f"       Target mean         : {y.mean():.1f}")

    # 2. Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    if verbose:
        print(f"\n[2/4] Train/test split     : {len(X_train)} train, {len(X_test)} test")

    # 3. Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)

    # 4. Train
    if verbose:
        print("\n[3/4] Training GradientBoostingRegressor...")
    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        min_samples_split=10,
        random_state=42,
    )
    model.fit(X_train_scaled, y_train)

    # 5. Evaluate
    y_pred = model.predict(X_test_scaled)
    y_pred = np.clip(y_pred, 0, 100)

    r2   = r2_score(y_test, y_pred)
    mae  = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    # 5-fold cross-validation on full dataset
    X_all_scaled = scaler.transform(X)
    cv_scores = cross_val_score(model, X_all_scaled, y, cv=5, scoring="r2")

    if verbose:
        print("\n[4/4] Evaluation Results")
        print("       ─────────────────────────────────────────")
        print(f"       R² Score (test)       : {r2:.4f}")
        print(f"       MAE  (test)           : {mae:.2f}")
        print(f"       RMSE (test)           : {rmse:.2f}")
        print(f"       5-Fold CV R² (mean)   : {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
        print("       ─────────────────────────────────────────")

    # Feature importances
    importances = dict(zip(FEATURE_COLS, model.feature_importances_))
    top10 = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]
    if verbose:
        print("\n       Top-10 Feature Importances:")
        for name, imp in top10:
            bar = "█" * int(imp * 200)
            print(f"         {name:30s} {imp:.4f}  {bar}")

    # 6. Save model
    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)

    metrics = {
        "r2": round(r2, 4),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "cv_r2_mean": round(cv_scores.mean(), 4),
        "cv_r2_std": round(cv_scores.std(), 4),
        "n_training_samples": n_samples,
        "n_features": X.shape[1],
        "feature_importances_top10": {k: round(v, 4) for k, v in top10},
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    if verbose:
        print(f"\n       Model saved to    : {MODEL_PATH}")
        print(f"       Scaler saved to   : {SCALER_PATH}")
        print(f"       Metrics saved to  : {METRICS_PATH}")
        print("=" * 60)

    return metrics


# ═══════════════════════════════════════════════════════════════════════════
#  INFERENCE (loaded model)
# ═══════════════════════════════════════════════════════════════════════════

_model_cache = {}

def _load_model():
    if "model" not in _model_cache:
        if not MODEL_PATH.exists():
            print("No trained model found — training now...")
            train_model()
        _model_cache["model"]  = joblib.load(MODEL_PATH)
        _model_cache["scaler"] = joblib.load(SCALER_PATH)
    return _model_cache["model"], _model_cache["scaler"]


def _get_db():
    client = MongoClient("mongodb://localhost:27017")
    return client.LandRegistry


def recommend(query, top_n=10):
    """
    Score every on-sale listing using the trained model, return top-N.

    Parameters
    ----------
    query : dict   (buyer preferences — budget, minArea, bedrooms, etc.)
    top_n : int

    Returns
    -------
    list[dict]  – property docs + "matchScore" (0-100).
    """
    model, scaler = _load_model()

    db = _get_db()
    listings = list(db.PropertyListings.find({"onSale": True}))
    if not listings:
        return []

    # Build feature matrix: one row per (query, listing)
    X = np.array([build_features(query, prop) for prop in listings])
    X_scaled = scaler.transform(X)

    scores = model.predict(X_scaled)
    scores = np.clip(scores, 0, 100)

    # Rank by predicted score
    ranked = np.argsort(scores)[::-1][:top_n]

    results = []
    for idx in ranked:
        doc = listings[idx]
        doc.pop("_id", None)
        doc["matchScore"] = round(float(scores[idx]), 1)
        results.append(doc)

    return results


def get_model_metrics():
    """Return saved evaluation metrics, or None if model not trained."""
    if METRICS_PATH.exists():
        with open(METRICS_PATH) as f:
            return json.load(f)
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  SEED DATA
# ═══════════════════════════════════════════════════════════════════════════

def seed_sample_data():
    """Insert sample property listings for demo/testing purposes."""
    db = _get_db()
    if db.PropertyListings.count_documents({}) > 0:
        return "Sample data already exists"

    sample = [
        {
            "propertyId": 1, "title": "Modern Downtown Apartment",
            "description": "Spacious 3BHK in the heart of the city with metro connectivity",
            "price": 5.0, "area": 1500, "bedrooms": 3, "bathrooms": 2,
            "propertyType": "apartment", "areaType": "urban", "locationId": 101,
            "city": "Mumbai", "facilities": ["metro", "hospital", "school", "mall", "gym"],
            "yearBuilt": 2020, "parking": True, "furnished": "semi-furnished",
            "onSale": True, "owner": "0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0",
            "imageUrl": ""
        },
        {
            "propertyId": 2, "title": "Suburban Family Villa",
            "description": "Beautiful 4BHK villa with garden and peaceful surroundings",
            "price": 12.0, "area": 3500, "bedrooms": 4, "bathrooms": 3,
            "propertyType": "villa", "areaType": "suburban", "locationId": 102,
            "city": "Pune", "facilities": ["school", "park", "hospital", "playground"],
            "yearBuilt": 2018, "parking": True, "furnished": "furnished",
            "onSale": True, "owner": "0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b",
            "imageUrl": ""
        },
        {
            "propertyId": 3, "title": "Budget Studio Apartment",
            "description": "Cozy 1BHK studio perfect for singles or young professionals",
            "price": 1.5, "area": 550, "bedrooms": 1, "bathrooms": 1,
            "propertyType": "apartment", "areaType": "urban", "locationId": 101,
            "city": "Mumbai", "facilities": ["metro", "bus_stop", "restaurant", "atm"],
            "yearBuilt": 2022, "parking": False, "furnished": "furnished",
            "onSale": True, "owner": "0xE11BA2b4D45Eaed5996Cd0823791E0C93114882d",
            "imageUrl": ""
        },
        {
            "propertyId": 4, "title": "Premium Penthouse",
            "description": "Luxury 5BHK penthouse with rooftop pool and city views",
            "price": 25.0, "area": 5000, "bedrooms": 5, "bathrooms": 4,
            "propertyType": "apartment", "areaType": "urban", "locationId": 103,
            "city": "Delhi", "facilities": ["gym", "mall", "metro", "hospital", "park", "restaurant"],
            "yearBuilt": 2023, "parking": True, "furnished": "furnished",
            "onSale": True, "owner": "0xd03ea8624C8C5987235048901fB614fDcA89b117",
            "imageUrl": ""
        },
        {
            "propertyId": 5, "title": "Rural Farmhouse",
            "description": "Peaceful 3BHK farmhouse with 2 acres of land",
            "price": 8.0, "area": 4000, "bedrooms": 3, "bathrooms": 2,
            "propertyType": "independent_house", "areaType": "rural", "locationId": 104,
            "city": "Nashik", "facilities": ["market", "temple", "school"],
            "yearBuilt": 2015, "parking": True, "furnished": "unfurnished",
            "onSale": True, "owner": "0x95cED938F7991cd0dFcb48F0a06a40FA1aF46EBC",
            "imageUrl": ""
        },
        {
            "propertyId": 6, "title": "Compact 2BHK Near IT Park",
            "description": "Well-connected 2BHK apartment near major tech companies",
            "price": 3.2, "area": 950, "bedrooms": 2, "bathrooms": 1,
            "propertyType": "apartment", "areaType": "suburban", "locationId": 105,
            "city": "Hyderabad", "facilities": ["bus_stop", "restaurant", "atm", "gym", "metro"],
            "yearBuilt": 2021, "parking": True, "furnished": "semi-furnished",
            "onSale": True, "owner": "0x3E5e9111Ae8eB78Fe1CC3bb8915d5D461F3Ef9A9",
            "imageUrl": ""
        },
        {
            "propertyId": 7, "title": "Heritage Independent House",
            "description": "Charming 3BHK house in a heritage neighbourhood",
            "price": 7.0, "area": 2200, "bedrooms": 3, "bathrooms": 2,
            "propertyType": "independent_house", "areaType": "urban", "locationId": 106,
            "city": "Jaipur", "facilities": ["temple", "market", "hospital", "school", "park"],
            "yearBuilt": 2005, "parking": True, "furnished": "unfurnished",
            "onSale": True, "owner": "0x28a8746e75304c0780E011BEd21C72cD78cd535E",
            "imageUrl": ""
        },
        {
            "propertyId": 8, "title": "Affordable Plot in Suburbs",
            "description": "1200 sq-ft residential plot in a developing area",
            "price": 2.0, "area": 1200, "bedrooms": 0, "bathrooms": 0,
            "propertyType": "plot", "areaType": "suburban", "locationId": 107,
            "city": "Bangalore", "facilities": ["bus_stop", "school"],
            "yearBuilt": 2024, "parking": False, "furnished": "unfurnished",
            "onSale": True, "owner": "0xACa94ef8bD5ffEE41947b4585a84BdA5a3d3DA6E",
            "imageUrl": ""
        },
        {
            "propertyId": 9, "title": "Lake View 3BHK",
            "description": "Scenic lake view apartment with premium amenities",
            "price": 6.5, "area": 1800, "bedrooms": 3, "bathrooms": 2,
            "propertyType": "apartment", "areaType": "suburban", "locationId": 108,
            "city": "Udaipur", "facilities": ["park", "gym", "hospital", "restaurant", "playground"],
            "yearBuilt": 2019, "parking": True, "furnished": "semi-furnished",
            "onSale": True, "owner": "0x1dF62f291b2E969fB0849d99D9Ce41e2F137006e",
            "imageUrl": ""
        },
        {
            "propertyId": 10, "title": "Smart Home Villa",
            "description": "Tech-enabled 4BHK villa with solar panels and automation",
            "price": 15.0, "area": 4200, "bedrooms": 4, "bathrooms": 3,
            "propertyType": "villa", "areaType": "suburban", "locationId": 109,
            "city": "Chennai", "facilities": ["school", "hospital", "park", "gym", "mall", "metro"],
            "yearBuilt": 2024, "parking": True, "furnished": "furnished",
            "onSale": True, "owner": "0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0",
            "imageUrl": ""
        },
        {
            "propertyId": 11, "title": "Cozy 2BHK in Gated Community",
            "description": "Family-friendly 2BHK with 24/7 security and clubhouse",
            "price": 4.0, "area": 1100, "bedrooms": 2, "bathrooms": 2,
            "propertyType": "apartment", "areaType": "urban", "locationId": 110,
            "city": "Kolkata", "facilities": ["school", "park", "gym", "playground", "atm"],
            "yearBuilt": 2021, "parking": True, "furnished": "semi-furnished",
            "onSale": True, "owner": "0x22d491Bde2303f2f43325b2108D26f1eAbA1e32b",
            "imageUrl": ""
        },
        {
            "propertyId": 12, "title": "Commercial Plot - Prime Location",
            "description": "2000 sq-ft commercial plot on main road",
            "price": 10.0, "area": 2000, "bedrooms": 0, "bathrooms": 0,
            "propertyType": "plot", "areaType": "urban", "locationId": 101,
            "city": "Mumbai", "facilities": ["bank", "market", "bus_stop", "railway"],
            "yearBuilt": 2024, "parking": False, "furnished": "unfurnished",
            "onSale": True, "owner": "0xE11BA2b4D45Eaed5996Cd0823791E0C93114882d",
            "imageUrl": ""
        },
    ]

    db.PropertyListings.insert_many(sample)
    return f"Inserted {len(sample)} sample listings"


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(seed_sample_data())
    metrics = train_model(n_samples=10000, verbose=True)

    print("\n\n── INFERENCE TEST ──────────────────────────────────────")
    test_query = {
        "budget": 5, "minArea": 1000, "bedrooms": 3, "bathrooms": 2,
        "propertyType": "apartment", "areaType": "urban",
        "furnished": "semi-furnished",
        "facilities": ["school", "hospital", "metro"],
        "yearBuilt": 2020, "parking": True,
    }
    results = recommend(test_query, top_n=5)
    print(f"Query: 3BHK urban apartment, ≤5 ETH, ≥1000 sqft\n")
    for i, r in enumerate(results, 1):
        print(f"  #{i}  [{r['matchScore']:.1f}%] {r['title']}"
              f" — {r['price']} ETH, {r['area']} sqft, {r['city']}")
