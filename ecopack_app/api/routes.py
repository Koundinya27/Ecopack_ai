from flask import request, jsonify, render_template, send_file
from . import bp
from .. import db
from ..models import UserRequest, RecommendationLog
from ecopack_core.core import CATEGORY_MAP, load_models, recommend_materials
from flask import send_file, url_for, jsonify
from xhtml2pdf import pisa
import io


models = load_models()


@bp.route("/recommend", methods=["POST"])
def recommend():
    data = request.get_json() or {}
    product = data.get("product", {})
    prefs = data.get("preferences", {})
    packaging = data.get("packaging", {})

    
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
    if not product or not prefs:
        return jsonify({"error": "Missing product or preferences"}), 400
    
    db.session.add(user_req)
    db.session.commit()

    rec = recommend_materials(
        {
            "product": product,
            "preferences": prefs,
            "packaging": packaging,
        },
        models,
        top_k=5,
    )
    top_materials = rec["top_materials"]
    total_units = prefs["total_units"]
    
    budget_min= prefs.get("budget_min_per_unit") or 0
    budget_max = prefs.get("budget_max_per_unit") or float('inf')

    filtered_materials = []
    for m in top_materials:
    # assume total_packaging_cost_inr is total for all units;
    # if you want per‑unit, divide by total_units
        per_unit_cost = m["total_packaging_cost_inr"] / total_units if total_units else 0

    # if no budget set, keep everything
        if budget_min == 0 and budget_max == float('inf'):
            keep = True
        else:
            keep = (per_unit_cost >= budget_min) and (per_unit_cost <= budget_max)

        if keep:
            filtered_materials.append(m)

# use filtered list from here on
    top_materials = filtered_materials

# log only filtered recommendations
    for m in top_materials:
        log = RecommendationLog(
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
        db.session.add(log)
    db.session.commit()

    return jsonify(
        {
        "request_id": user_req.id,
        "total_units": total_units,
        "top_materials": top_materials,
        }
    ), 200
    

@bp.route("/report_pdf/<int:request_id>", methods=["GET"])
def report_pdf(request_id):
    # Reuse your existing report context
    user_request = UserRequest.query.get_or_404(request_id)
    recs = (
        RecommendationLog.query
        .filter_by(request_id=request_id)
        .order_by(RecommendationLog.final_score.asc())
        .all()
    )
    total_cost = sum(r.total_packaging_cost_inr for r in recs)
    total_co2 = sum(r.total_co2_kg for r in recs)
    labels = [r.material_name for r in recs]
    cost_values = [float(r.total_packaging_cost_inr) for r in recs]
    co2_values = [float(r.total_co2_kg) for r in recs]

    html_str = render_template(
        "report.html",
        user_request=user_request,
        recs=recs,
        total_cost=total_cost,
        total_co2=total_co2,
        labels=labels,
        cost_values=cost_values,
        co2_values=co2_values,
    )

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(
        html_str, dest=pdf_buffer
    )

    if pisa_status.err:
        return jsonify({"error": "Failed to generate PDF"}), 500

    pdf_buffer.seek(0)


    filename = f"ecopack_report_{request_id}.pdf"
    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        download_name=filename,
        as_attachment=True,
    )



@bp.route("/confirm_selection", methods=["POST"])
def confirm_selection():
    data = request.get_json() or {}

    print("data:", data)
    request_id = data.get("request_id")
    material_id = data.get("material_id")  # or material_name

    if not request_id or not material_id:
        return jsonify({"error": "request_id and material_id required"}), 400

    # 1) Update selected material on this request
    user_req = UserRequest.query.get_or_404(request_id)

    rec = (
        RecommendationLog.query
        .filter_by(request_id=request_id, material_id=material_id)
        .first_or_404()
    )

    user_req.selected_material_name = rec.material_name
    user_req.selected_material_type = rec.material_type
    user_req.selected_total_cost_inr = rec.total_packaging_cost_inr
    user_req.selected_total_co2_kg = rec.total_co2_kg

    db.session.commit()

    # 2) Build aggregates for charts

    # a) how many times each material was selected
    sel_rows = (
        db.session.query(
            UserRequest.selected_material_name,
            db.func.count(UserRequest.id).label("cnt")
        )
        .filter(UserRequest.selected_material_name.isnot(None))
        .group_by(UserRequest.selected_material_name)
        .all()
    )

    selected_counts = [
        {
            "material_name": name,
            "count": cnt
        }
        for name, cnt in sel_rows
    ]

    # b) how many requests per product_category
    cat_rows = (
        db.session.query(
            UserRequest.product_category,
            db.func.count(UserRequest.id).label("cnt")
        )
        .group_by(UserRequest.product_category)
        .all()
    )

    category_counts = [
        {
            "category": category,
            "count": cnt
        }
        for category, cnt in cat_rows
    ]
    pdf_url = url_for("api.report_pdf", request_id=request_id)

    return jsonify({
        "status": "ok",
        "selected_counts": selected_counts,
        "category_counts": category_counts,
        "pdf_url" : pdf_url

    })
