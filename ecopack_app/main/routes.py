from flask import Blueprint, render_template, request, jsonify
from sqlalchemy import func
from .. import db
from ..models import UserRequest, RecommendationLog
from ecopack_core.core import load_models, recommend_materials
from . import bp

# cache models once
models_cache = load_models()

@bp.route("/")
def home():
    return render_template("home.html")  # landing page

@bp.route("/app", methods=["GET", "POST"])
def advisor():
    if request.method == "GET":
        # initial load: just show empty form
        return render_template("index.html")

    # POST: form submitted, build request_json for core.recommend_materials
    form = request.form

    product = {
        "product_category": form.get("product_category"),
        "product_name": form.get("product_name"),
        "length_cm": float(form.get("length_cm") or 0),
        "width_cm": float(form.get("width_cm") or 0),
        "height_cm": float(form.get("height_cm") or 0),
        "weight_in_kg": float(form.get("weight_in_kg") or 0),
        "fragility_level": int(form.get("fragility_level") or 3),
        "is_liquid": bool(form.get("is_liquid")),
        "is_delicate": bool(form.get("is_delicate")),
        "is_moisture_sensitive": bool(form.get("is_moisture_sensitive")),
        "is_temperature_sensitive": bool(form.get("is_temperature_sensitive")),
    }

    prefs = {
        "sustainability_level": form.get("sustainability_level") or "Standard",
        "budget_min_per_unit": float(form.get("budget_min_per_unit") or 0),
        "budget_max_per_unit": float(form.get("budget_max_per_unit") or 0),
        "total_units": int(form.get("total_units") or 1),
        "prior_protection_level": form.get("prior_protection_level") or "Medium",
    }

    packaging = {
        "preset": form.get("packaging_preset") or "",
        "box_length_cm": form.get("box_length_cm") or None,
        "box_width_cm": form.get("box_width_cm") or None,
        "box_height_cm": form.get("box_height_cm") or None,
        "material_gsm": form.get("material_gsm") or None,
    }

    request_json = {
        "product": product,
        "preferences": prefs,
        "packaging": packaging,
    }

    # call core.recommend_materials
    result = recommend_materials(request_json, models_cache, top_k=5)
    top_materials = result["top_materials"]
    total_units = result["total_units"]

    # save UserRequest
    user_req = UserRequest(
        product_name=product["product_name"],
        product_category=product["product_category"],
        length_cm=product["length_cm"],
        width_cm=product["width_cm"],
        height_cm=product["height_cm"],
        weight_in_kg=product["weight_in_kg"],
        fragility_level=product["fragility_level"],
        is_liquid=product["is_liquid"],
        is_delicate=product["is_delicate"],
        is_moisture_sensitive=product["is_moisture_sensitive"],
        is_temperature_sensitive=product["is_temperature_sensitive"],
        sustainability_level=prefs["sustainability_level"],
        budget_min_per_unit=prefs["budget_min_per_unit"],
        budget_max_per_unit=prefs["budget_max_per_unit"],
        total_units=prefs["total_units"],
        prior_protection_level=prefs["prior_protection_level"],
    )
    db.session.add(user_req)
    db.session.commit()  # user_req.id is now available

    # log the recommendations for this request
    for m in top_materials:
        rec = RecommendationLog(
            request_id=user_req.id,
            material_id=m["material_id"],
            material_name=m["material_name"],
            material_type=m["material_type"],
            co2_per_kg=m["co2_per_kg"],
            cost_per_kg_inr=m["cost_per_kg_inr"],
            total_co2_kg=m["total_co2_kg"],
            total_packaging_cost_inr=m["total_packaging_cost_inr"],
            final_score=m["final_score"],
        )
        db.session.add(rec)
    db.session.commit()

    # render index with results and request_id (for selection)
    return render_template(
        "index.html",
        top_materials=top_materials,
        total_units=total_units,
        request_id=user_req.id,
    )

@bp.route("/dashboard")
def dashboard():
    total_requests = UserRequest.query.count()

    requests_with_selection = (
        UserRequest.query
        .filter(UserRequest.selected_material_name.isnot(None))
        .count()
    )

    total_selected_cost_inr = (
        db.session.query(func.sum(UserRequest.selected_total_cost_inr))
        .scalar()
        or 0
    )

    total_selected_co2_kg = (
        db.session.query(func.sum(UserRequest.selected_total_co2_kg))
        .scalar()
        or 0
    )

    material_type_counts_raw = (
        db.session.query(
            UserRequest.selected_material_type,
            func.count(UserRequest.id),
        )
        .filter(UserRequest.selected_material_type.isnot(None))
        .group_by(UserRequest.selected_material_type)
        .all()
    )
    material_type_labels = [m[0] for m in material_type_counts_raw]
    material_type_counts = [m[1] for m in material_type_counts_raw]

    product_category_counts_raw = (
        db.session.query(
            UserRequest.product_category,
            func.count(UserRequest.id),
        )
        .group_by(UserRequest.product_category)
        .all()
    )
    product_category_labels = [p[0] or "Unknown" for p in product_category_counts_raw]
    product_category_counts = [p[1] for p in product_category_counts_raw]

    return render_template(
        "dashboard.html",
        total_requests=total_requests,
        requests_with_selection=requests_with_selection,
        total_selected_cost_inr=round(total_selected_cost_inr, 2),
        total_selected_co2_kg=round(total_selected_co2_kg, 2),
        material_type_labels=material_type_labels,
        material_type_counts=material_type_counts,
        product_category_labels=product_category_labels,
        product_category_counts=product_category_counts,
    )

