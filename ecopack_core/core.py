import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

CATEGORY_MAP = {
    "Kraft Paper": "Paper & Fibre Based",
    "Corrugated Cardboard": "Paper & Fibre Based",
    "Recycled Paper": "Paper & Fibre Based",
    "Paperboard": "Paper & Fibre Based",
    "Paper Cushioning": "Paper & Fibre Based",
    "Molded Pulp": "Paper & Fibre Based",

    "PET Plastic": "Traditional Plastics",
    "LDPE Plastic Film": "Traditional Plastics",
    "HDPE Plastic": "Traditional Plastics",

    "Air Cushion Film": "Flexible Cushioning & Fillers",
    "Bubble Wrap": "Flexible Cushioning & Fillers",
    "EPE Foam": "Flexible Cushioning & Fillers",
    "EPS Foam": "Flexible Cushioning & Fillers",

    "PLA Bioplastic": "Sustainable & Bio-plastics",
    "Starch-based Bioplastic": "Sustainable & Bio-plastics",

    "Glass Bottle": "Rigid & Heavy Duty",
    "Wooden Crate": "Rigid & Heavy Duty",
    "Aluminum Foil": "Rigid & Heavy Duty",
    "Steel Can": "Rigid & Heavy Duty",
    "Glass Jar": "Rigid & Heavy Duty",
}


# ---------- STEP 1: LOAD & FEATURE ENGINEERING ----------

materials = pd.read_csv("data/materials_generated1.csv")
products = pd.read_csv("data/products_1000_plus.csv")

num_mat = [
    "max_weight_capacity_kg",
    "moisture_resistance_level",
    "recyclable_percent",
    "biodegradable_days",
    "co2_per_kg",
    "cost_per_kg_inr",
    "strength_rating_per_kg",
]
materials[num_mat] = materials[num_mat].apply(
    lambda c: pd.to_numeric(c, errors="coerce")
)
materials[num_mat] = materials[num_mat].fillna(materials[num_mat].median())

num_prod = [
    "length_cm",
    "width_cm",
    "height_cm",
    "weight_in_kg",
    "fragility_level",
]
products[num_prod] = products[num_prod].apply(
    lambda c: pd.to_numeric(c, errors="coerce")
)
products[num_prod] = products[num_prod].fillna(products[num_prod].median())

bool_cols_mat = [
    "suitable_for_fragile",
    "suitable_for_liquid",
    "suitable_for_moisture_sensitive",
    "suitable_for_temperature_sensitive",
]
for c in bool_cols_mat:
    materials[c] = materials[c].astype(bool)

bool_cols_prod = [
    "is_liquid",
    "is_delicate",
    "is_moisture_sensitive",
    "is_temperature_sensitive",
]
for c in bool_cols_prod:
    products[c] = products[c].astype(bool)

materials["co2_impact_index"] = (
    (100 - materials["recyclable_percent"]) * materials["co2_per_kg"]
)
materials["cost_efficiency_index"] = (
    materials["cost_per_kg_inr"] / (materials["strength_rating_per_kg"] + 1e-6)
)
materials["material_suitability_score"] = (
    0.4 * (materials["recyclable_percent"] / 100.0)
    + 0.3 * (1.0 / (1.0 + materials["co2_per_kg"]))
    + 0.3 * (1.0 / (1.0 + materials["cost_efficiency_index"]))
)

products["volume_cm3"] = (
    products["length_cm"] * products["width_cm"] * products["height_cm"]
)
products["density_kg_per_cm3"] = products["weight_in_kg"] / (
    products["volume_cm3"] + 1e-9
)
products["is_liquid_int"] = products["is_liquid"].astype(int)
products["is_delicate_int"] = products["is_delicate"].astype(int)

# ---------- STEP 2: TRAINING DATASET ----------

n_samples = 2000

prod_sample = products.sample(
    n=min(len(products), n_samples), replace=True, random_state=42
).reset_index(drop=True)

mat_sample = materials.sample(
    n=min(len(materials), n_samples), replace=True, random_state=42
).reset_index(drop=True)

train_df = pd.concat(
    [
        prod_sample.add_prefix("prod_"),
        mat_sample.add_prefix("mat_"),
    ],
    axis=1,
)

numeric_features = [
    "prod_length_cm",
    "prod_width_cm",
    "prod_height_cm",
    "prod_weight_in_kg",
    "prod_fragility_level",
    "prod_volume_cm3",
    "prod_density_kg_per_cm3",
    "prod_is_liquid_int",
    "prod_is_delicate_int",
    "mat_max_weight_capacity_kg",
    "mat_moisture_resistance_level",
    "mat_recyclable_percent",
    "mat_biodegradable_days",
    "mat_co2_per_kg",
    "mat_cost_per_kg_inr",
    "mat_strength_rating_per_kg",
    "mat_co2_impact_index",
    "mat_cost_efficiency_index",
    "mat_material_suitability_score",
]

categorical_features = [
    "prod_product_category",
    "mat_material_type",
    "mat_recommended_product_category",
]

X = train_df[numeric_features + categorical_features].copy()
y_cost = train_df["mat_cost_per_kg_inr"]
y_co2 = train_df["mat_co2_per_kg"]

X_train, X_test, y_train_cost, y_test_cost = train_test_split(
    X, y_cost, test_size=0.2, random_state=42
)
_, _, y_train_co2, y_test_co2 = train_test_split(
    X, y_co2, test_size=0.2, random_state=42
)

numeric_transformer = Pipeline(
    steps=[("scaler", StandardScaler())]
)
categorical_transformer = Pipeline(
    steps=[("onehot", OneHotEncoder(handle_unknown="ignore"))]
)
preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features),
    ]
)

_ = preprocessor.fit_transform(X_train[:100])

# ---------- STEP 3: MODELS ----------

rf_cost_model = RandomForestRegressor(
    n_estimators=300,
    n_jobs=-1,
    random_state=42
)
rf_cost_pipeline = Pipeline(steps=[
    ("preprocess", preprocessor),
    ("model", rf_cost_model),
])
rf_cost_pipeline.fit(X_train, y_train_cost)

xgb_co2_model = XGBRegressor(
    n_estimators=400,
    learning_rate=0.05,
    max_depth=6,
    subsample=0.9,
    colsample_bytree=0.9,
    random_state=42,
    n_jobs=-1,
    objective="reg:squarederror"
)
xgb_co2_pipeline = Pipeline(steps=[
    ("preprocess", preprocessor),
    ("model", xgb_co2_model),
])
xgb_co2_pipeline.fit(X_train, y_train_co2)

# ---------- STEP 4: SCORING FUNCTIONS ----------

def compute_product_fit(candidates: pd.DataFrame, product_row: pd.Series) -> pd.Series:
    prod_cat = str(product_row["product_category"])
    prod_weight = float(product_row["weight_in_kg"])
    prod_frag = int(product_row["fragility_level"])

    fit = pd.Series(0.0, index=candidates.index)

    if "material_suitability_score" in candidates.columns:
        fit += candidates["material_suitability_score"] * 0.7

    mat_type = candidates["material_type"].astype(str).str.lower()
    mat_reco = candidates["recommended_product_category"].astype(str).str.lower()
    p = prod_cat.lower()

    fit += (mat_reco == p).astype(float) * 0.4

    if p == "electronics":
        fit += mat_type.str.contains("corrugated|foam|bubble|rigid|padded", na=False) * 0.5
        fit += mat_type.str.contains("cardboard|paper|bio", na=False) * 0.2
    elif p == "apparel & fashion":
        fit += mat_type.str.contains("paper|cardboard|poly mailer|bio", na=False) * 0.6
    elif p == "food & beverages":
        fit += mat_type.str.contains("paper|cardboard|bio|film|tray|foil|laminate", na=False) * 0.7
    elif p == "cosmetics & beauty":
        fit += mat_type.str.contains("bio|paper|cardboard|glass|plastic|jar|tube", na=False) * 0.6
    elif p == "home & living":
        fit += mat_type.str.contains("corrugated|cardboard|paper|foam|pouch|bag", na=False) * 0.5
    elif p == "industrial goods":
        fit += mat_type.str.contains("wooden|pallet|crate|heavy-duty|metal|hdpe", na=False) * 0.7
    elif p == "pharmaceuticals":
        fit += mat_type.str.contains("blister|glass|hdpe|sterile|foil|ampoule", na=False) * 0.7
    else:
        fit += mat_type.str.contains("paper|cardboard|plastic|bio", na=False) * 0.4

    margin = candidates["max_weight_capacity_kg"] - prod_weight
    fit += (margin >= 0).astype(float) * 0.6
    fit += (margin >= prod_weight * 0.5).astype(float) * 0.2
    fit -= (margin < 0).astype(float) * 1.5

    fit += (candidates["suitable_for_fragile"].astype(bool)).astype(float) * (0.3 if prod_frag >= 4 else 0.1)

    strength = candidates["strength_rating_per_kg"]
    ratio = prod_weight / (strength + 1e-6)
    fit -= (ratio > 1.0).astype(float) * 0.4
    fit -= (ratio > 2.0).astype(float) * 0.4
    if prod_frag >= 4:
        fit += (strength > strength.median()).astype(float) * 0.4

    if bool(product_row.get("is_liquid", False)):
        fit += candidates["suitable_for_liquid"].astype(bool).astype(float) * 0.6
    if bool(product_row.get("is_moisture_sensitive", False)):
        fit += candidates["suitable_for_moisture_sensitive"].astype(bool).astype(float) * 0.5
        fit += (candidates["moisture_resistance_level"] >= 4).astype(float) * 0.3
    if bool(product_row.get("is_temperature_sensitive", False)):
        fit += candidates["suitable_for_temperature_sensitive"].astype(bool).astype(float) * 0.5

    fit += (candidates["recyclable_percent"] >= 80).astype(float) * 0.3
    fit += (candidates["biodegradable_days"] <= 365).astype(float) * 0.2

    median_co2 = candidates["co2_per_kg"].median()
    fit -= (candidates["co2_per_kg"] > median_co2).astype(float) * 0.3

    fmin, fmax = float(fit.min()), float(fit.max())
    if fmax - fmin < 1e-9:
        return pd.Series(0.5, index=candidates.index)
    return (fit - fmin) / (fmax - fmin + 1e-9)

def get_preference_weights(sustainability_level: str):
    """
    Map sustainability level to weights for cost vs CO2.
    Higher sustainability => CO2 is weighted more than cost.
    """
    s = str(sustainability_level).lower()
    if s == "very high":
        return {"alpha_cost": 0.3, "alpha_co2": 0.7}
    if s == "high":
        return {"alpha_cost": 0.4, "alpha_co2": 0.6}
    # Standard
    return {"alpha_cost": 0.5, "alpha_co2": 0.5}


def adjust_fit_by_protection(fit_score: float, prior_protection_level: str) -> float:
    """
    Adjust product_fit_score based on how much protection the user wants.
    High protection => emphasize differences between materials with high vs low fit.
    Low protection  => flatten differences so eco/cost matters more.
    """
    lvl = str(prior_protection_level).lower()
    if lvl == "high":
        # curve so high fits stand out more (0.7 < 1, boosts high values)
        return fit_score ** 0.7
    if lvl == "low":
        # flatten differences (1.3 > 1, compresses spread)
        return fit_score ** 1.3
    # medium / default
    return fit_score


def rank_materials_for_product(
    product_row: pd.Series,
    materials_df: pd.DataFrame,
    numeric_features,
    categorical_features,
    rf_cost_pipeline,
    xgb_co2_pipeline,
    alpha_cost=0.5,
    alpha_co2=0.5,
    beta_model=0.5,
    beta_fit=0.5,
    top_k=5,
    prior_protection_level: str="Medium",
):
    candidates = materials_df.copy()

    candidates["prod_length_cm"] = float(product_row["length_cm"])
    candidates["prod_width_cm"] = float(product_row["width_cm"])
    candidates["prod_height_cm"] = float(product_row["height_cm"])
    candidates["prod_weight_in_kg"] = float(product_row["weight_in_kg"])
    candidates["prod_fragility_level"] = int(product_row["fragility_level"])

    volume = (
        float(product_row["length_cm"])
        * float(product_row["width_cm"])
        * float(product_row["height_cm"])
    )
    candidates["prod_volume_cm3"] = volume
    candidates["prod_density_kg_per_cm3"] = float(product_row["weight_in_kg"]) / (volume + 1e-9)

    candidates["prod_is_liquid_int"] = int(bool(product_row.get("is_liquid", False)))
    candidates["prod_is_delicate_int"] = int(bool(product_row.get("is_delicate", False)))
    candidates["prod_product_category"] = product_row["product_category"]

    feature_df = pd.DataFrame(index=candidates.index)

    feature_df["prod_length_cm"] = candidates["prod_length_cm"]
    feature_df["prod_width_cm"] = candidates["prod_width_cm"]
    feature_df["prod_height_cm"] = candidates["prod_height_cm"]
    feature_df["prod_weight_in_kg"] = candidates["prod_weight_in_kg"]
    feature_df["prod_fragility_level"] = candidates["prod_fragility_level"]
    feature_df["prod_volume_cm3"] = candidates["prod_volume_cm3"]
    feature_df["prod_density_kg_per_cm3"] = candidates["prod_density_kg_per_cm3"]
    feature_df["prod_is_liquid_int"] = candidates["prod_is_liquid_int"]
    feature_df["prod_is_delicate_int"] = candidates["prod_is_delicate_int"]

    feature_df["mat_max_weight_capacity_kg"] = candidates["max_weight_capacity_kg"]
    feature_df["mat_moisture_resistance_level"] = candidates["moisture_resistance_level"]
    feature_df["mat_recyclable_percent"] = candidates["recyclable_percent"]
    feature_df["mat_biodegradable_days"] = candidates["biodegradable_days"]
    feature_df["mat_co2_per_kg"] = candidates["co2_per_kg"]
    feature_df["mat_cost_per_kg_inr"] = candidates["cost_per_kg_inr"]
    feature_df["mat_strength_rating_per_kg"] = candidates["strength_rating_per_kg"]
    feature_df["mat_co2_impact_index"] = candidates["co2_impact_index"]
    feature_df["mat_cost_efficiency_index"] = candidates["cost_efficiency_index"]
    feature_df["mat_material_suitability_score"] = candidates["material_suitability_score"]

    feature_df["prod_product_category"] = candidates["prod_product_category"]
    feature_df["mat_material_type"] = candidates["material_type"]
    feature_df["mat_recommended_product_category"] = candidates["recommended_product_category"]

    used_cols = [c for c in (numeric_features + categorical_features) if c in feature_df.columns]
    X_cand = feature_df[used_cols]

    candidates["pred_cost_per_kg_inr"] = rf_cost_pipeline.predict(X_cand)
    candidates["pred_co2_per_kg"] = xgb_co2_pipeline.predict(X_cand)

    for col in ["pred_cost_per_kg_inr", "pred_co2_per_kg"]:
        cmin = float(candidates[col].min())
        cmax = float(candidates[col].max())
        candidates[col + "_norm"] = (candidates[col] - cmin) / (cmax - cmin + 1e-9)

    candidates["eco_cost_score"] = (
        alpha_cost * candidates["pred_cost_per_kg_inr_norm"]
        + alpha_co2 * candidates["pred_co2_per_kg_norm"]
    )

    # 8) Rule-based product fit (higher better, from 0 to 1)
    base_fit = compute_product_fit(candidates, product_row)

    # 8.1) Adjust fit based on user protection preference
    adjusted_fit = base_fit.apply(
        lambda v: adjust_fit_by_protection(float(v), prior_protection_level)
    )
    candidates["product_fit_score"] = adjusted_fit

    # 9) final_score: combine (lower is better overall)
    candidates["final_score"] = (
        beta_model * candidates["eco_cost_score"]
        + beta_fit * (1.0 - candidates["product_fit_score"])
    )


    ranked = candidates.sort_values("final_score", ascending=True)
    return ranked.head(top_k)[[
    "material_id",
    "material_name",
    "material_type",
    "strength_rating_per_kg",   # add this
    "pred_cost_per_kg_inr",
    "pred_co2_per_kg",
    "eco_cost_score",
    "product_fit_score",
    "final_score",
]]


# ---------- PUBLIC API FOR FLASK ----------

def load_models():
    return {
        "materials": materials,
        "rf_cost_pipeline": rf_cost_pipeline,
        "xgb_co2_pipeline": xgb_co2_pipeline,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
    }
def get_base_packaging_ratio(product_category: str) -> float:
    """Return base packaging mass ratio (packaging_mass = ratio * product_mass)."""
    p = product_category.lower()

    if p == "electronics":
        return 0.15   # 8%
    if p == "apparel & fashion":
        return 0.7  # 3%
    if p == "food & beverages":
        return 0.16   # 10%
    if p == "cosmetics & beauty":
        return 0.11   # 7%
    if p == "home & living":
        return 0.10   # 6%
    if p == "industrial goods":
        return 0.09   # 5%
    if p == "pharmaceuticals":
        return 0.12   # 8%

    # default for unknown categories
    return 0.06

def estimate_packaging_mass_kg(product_row, material_row):
    """
    Estimate packaging mass per unit based on:
    - product_category (different base ratios)
    - fragility (more protective packaging)
    - optionally material strength
    """
    ratio = get_base_packaging_ratio(str(product_row["product_category"]))
    base = ratio * float(product_row["weight_in_kg"])

    frag_factor = 1.0 + (int(product_row["fragility_level"]) - 1) * 0.1

    strength = 1.0
    if "strength_rating_per_kg" in material_row.index:
        try:
            val = float(material_row["strength_rating_per_kg"])
            strength = val if val > 0 else 1.0
        except Exception:
            strength = 1.0

    return base * frag_factor / max(0.5, strength)

def get_preset_dimensions(preset_name: str):
    """Map preset names to box dimensions + GSM."""
    presets = {
        "kraft-small": {"l":15, "w":10, "h":10, "gsm":250},
        "kraft-medium": {"l":20, "w":15, "h":10, "gsm":300},
        "kraft-large": {"l":25, "w":20, "h":12, "gsm":350},
        "corrugated-small": {"l":18, "w":12, "h":12, "gsm":400},
        "corrugated-medium": {"l":25, "w":18, "h":12, "gsm":500},
        "corrugated-large": {"l":30, "w":22, "h":15, "gsm":600},
        "recycled-small": {"l":16, "w":11, "h":12, "gsm":280},
    }
    return presets.get(preset_name.lower(), None)

def box_packaging_mass_from_gsm(L_cm, W_cm, H_cm, gsm, allowance_factor=1.35):
    """
    Slightly heavier box estimate so small cartons are in the 50–150 g range.[web:178][web:181]
    """
    padding = 0.5
    Lp, Wp, Hp = L_cm + 2*padding, W_cm + 2*padding, H_cm + 2*padding

    area_cm2 = 2 * (Lp*Wp + Lp*Hp + Wp*Hp)
    area_m2 = area_cm2 / 10000.0

    mass_g = area_m2 * gsm * allowance_factor
    # enforce a reasonable minimum per box for small sizes
    min_mass_g = 20.0   # 20 g
    if mass_g < min_mass_g:
        mass_g = min_mass_g

    return mass_g / 1000.0  # kg


def estimate_packaging_mass_kg(product_row, material_row, packaging_info):
    """
    Hybrid: preset OR custom → geometric mass, slightly adjusted by fragility.
    """
    preset = str(packaging_info.get("preset", "")).lower()

    if preset and preset != "custom":
        preset_dims = get_preset_dimensions(preset)
        if preset_dims:
            L = preset_dims["l"]
            W = preset_dims["w"]
            H = preset_dims["h"]
            gsm = preset_dims["gsm"]
        else:
            L, W, H, gsm = 20.0, 15.0, 10.0, 300.0
    else:
        L = float(packaging_info.get("box_length_cm", 20.0))
        W = float(packaging_info.get("box_width_cm", 15.0))
        H = float(packaging_info.get("box_height_cm", 10.0))
        gsm = float(packaging_info.get("material_gsm", 300.0))

    base_mass = box_packaging_mass_from_gsm(L, W, H, gsm)

    frag = int(product_row.get("fragility_level", 3))
    frag_factor = 1.0 + (frag - 3) * 0.05  # ±10% around fragility 3

    return base_mass * frag_factor


def recommend_materials(request_json, models, top_k=5):
    product = request_json["product"]
    prefs = request_json["preferences"]
    packaging = request_json.get("packaging", {})
    total_units = int(prefs["total_units"])
        # derive weights from sustainability level
    weights = get_preference_weights(prefs.get("sustainability_level", "Standard"))
    alpha_cost = weights["alpha_cost"]
    alpha_co2 = weights["alpha_co2"]

    prior_protection_level = prefs.get("prior_protection_level", "Medium")


    product_row = pd.Series({
        "product_category": product["product_category"],
        "length_cm": float(product["length_cm"]),
        "width_cm": float(product["width_cm"]),
        "height_cm": float(product["height_cm"]),
        "weight_in_kg": float(product["weight_in_kg"]),
        "fragility_level": int(product["fragility_level"]),
        "is_liquid": bool(product["is_liquid"]),
        "is_delicate": bool(product["is_delicate"]),
        "is_moisture_sensitive": bool(product["is_moisture_sensitive"]),
        "is_temperature_sensitive": bool(product["is_temperature_sensitive"]),
    })
    product_row["volume_cm3"] = (
        product_row["length_cm"] * product_row["width_cm"] * product_row["height_cm"]
    )
    product_row["is_liquid_int"] = int(product_row["is_liquid"])
    product_row["is_delicate_int"] = int(product_row["is_delicate"])

    ranked = rank_materials_for_product(
        product_row=product_row,
        materials_df=models["materials"],
        numeric_features=models["numeric_features"],
        categorical_features=models["categorical_features"],
        rf_cost_pipeline=models["rf_cost_pipeline"],
        xgb_co2_pipeline=models["xgb_co2_pipeline"],
        alpha_cost=alpha_cost,
        alpha_co2=alpha_co2,
        top_k=top_k,
        prior_protection_level=prior_protection_level,
    )


    top_materials = []
    for _, row in ranked.iterrows():
        pack_mass_per_unit = estimate_packaging_mass_kg(product_row, row, packaging)

        cost_per_unit = pack_mass_per_unit * float(row["pred_cost_per_kg_inr"])
        co2_per_unit = pack_mass_per_unit * float(row["pred_co2_per_kg"])

        total_pack_mass = pack_mass_per_unit * total_units
        total_cost = total_pack_mass * float(row["pred_cost_per_kg_inr"])
        total_co2 = total_pack_mass * float(row["pred_co2_per_kg"])
        budget_min = float(prefs.get("budget_min_per_unit", 0) or 0)
        budget_max = float(prefs.get("budget_max_per_unit", 0) or 0)

        penalty = 0.0
        if budget_max > 0 and cost_per_unit > budget_max:
            over_ratio = (cost_per_unit - budget_max) / budget_max
            penalty += 0.5 * over_ratio
        if budget_min > 0 and cost_per_unit < budget_min:
            under_ratio = (budget_min - cost_per_unit) / budget_min
            penalty += 0.2 * under_ratio

        adjusted_final_score = float(row["final_score"]) + penalty
        material_type = row["material_type"]
        top_materials.append({
            "material_id": int(row["material_id"]),
            "material_name": row["material_name"],
            "material_type": material_type,
            "parent_type": CATEGORY_MAP.get(material_type, "Other"),
            "cost_per_kg_inr": float(row["pred_cost_per_kg_inr"]),
            "co2_per_kg": float(row["pred_co2_per_kg"]),
            "packaging_mass_per_unit_kg": float(pack_mass_per_unit),
            "cost_per_unit_inr": float(cost_per_unit),
            "co2_per_unit_kg": float(co2_per_unit),
            "total_packaging_mass_kg": float(total_pack_mass),
            "total_packaging_cost_inr": float(total_cost),
            "total_co2_kg": float(total_co2),
            "eco_cost_score": float(row["eco_cost_score"]),
            "product_fit_score": float(row["product_fit_score"]),
            "final_score": float(adjusted_final_score),
        })

    return {
        "total_units": total_units,
        "top_materials": top_materials,
    }



