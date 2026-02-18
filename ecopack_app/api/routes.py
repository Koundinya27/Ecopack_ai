from flask import request, jsonify, render_template, send_file, url_for
from . import bp
from .. import db
from ..models import UserRequest, RecommendationLog
from ecopack_core.core import CATEGORY_MAP, load_models, recommend_materials
from io import BytesIO
from sqlalchemy import func
import matplotlib.pyplot as plt
import base64
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF


models = load_models()


@bp.route("/recommend", methods=["POST"])
def recommend():
    data = request.get_json() or {}
    product = data.get("product", {})
    prefs = data.get("preferences", {})
    packaging = data.get("packaging", {})

    if not product or not prefs:
        return jsonify({"error": "Missing product or preferences"}), 400

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
    baselines = rec.get("traditional_baselines", [])
    total_units = prefs["total_units"]

    # budget filter (per-unit)
    budget_min = prefs.get("budget_min_per_unit") or 0
    budget_max = prefs.get("budget_max_per_unit") or float("inf")

    filtered_materials = []
    for m in top_materials:
        per_unit_cost = (
            m["total_packaging_cost_inr"] / total_units if total_units else 0
        )

        if budget_min == 0 and budget_max == float("inf"):
            keep = True
        else:
            keep = budget_min <= per_unit_cost <= budget_max

        if keep:
            filtered_materials.append(m)

    top_materials = filtered_materials

    # compute average reduction vs traditional for this request (using selected = top-1)
    avg_cost_reduction_pct = None
    avg_co2_reduction_pct = None

    if top_materials and baselines:
        selected = top_materials[0]

        reductions_cost = []
        reductions_co2 = []

        for b in baselines:
            # expect b has keys: name, cost_per_unit_inr, co2_per_unit_kg
            if b.get("cost_per_unit_inr"):
                cost_red = (
                    (b["cost_per_unit_inr"] - selected["cost_per_unit_inr"])
                    / b["cost_per_unit_inr"]
                    * 100
                )
                reductions_cost.append(cost_red)
            if b.get("co2_per_unit_kg"):
                co2_red = (
                    (b["co2_per_unit_kg"] - selected["co2_per_unit_kg"])
                    / b["co2_per_unit_kg"]
                    * 100
                )
                reductions_co2.append(co2_red)

        if reductions_cost:
            avg_cost_reduction_pct = sum(reductions_cost) / len(reductions_cost)
        if reductions_co2:
            avg_co2_reduction_pct = sum(reductions_co2) / len(reductions_co2)

        # store on request for dashboard aggregation
        user_req.avg_cost_reduction_pct = avg_cost_reduction_pct
        user_req.avg_co2_reduction_pct = avg_co2_reduction_pct
        db.session.add(user_req)

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
            "traditional_baselines": baselines,
            "avg_cost_reduction_pct": avg_cost_reduction_pct,
            "avg_co2_reduction_pct": avg_co2_reduction_pct,
        }
    ), 200


@bp.route("/report_pdf/<int:request_id>", methods=["GET"])
def report_pdf(request_id):
    user_request = UserRequest.query.get_or_404(request_id)
    recs = (
        RecommendationLog.query.filter_by(request_id=request_id)
        .order_by(RecommendationLog.final_score.asc())
        .all()
    )

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)

    # Page setup
    y = 800
    left = 50

    pdf.setTitle("EcoPack Recommendation Report")

    # Header
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(left, y, "Packaging Recommendation Report")
    y -= 30

    pdf.setFont("Helvetica", 10)
    pdf.drawString(left, y, f"Request ID: {user_request.id}")
    y -= 15
    pdf.drawString(left, y, f"Product: {user_request.product_name}")
    y -= 15
    pdf.drawString(left, y, f"Category: {user_request.product_category}")
    y -= 15
    pdf.drawString(
        left,
        y,
        f"Total units: {user_request.total_units}    "
        f"Budget/unit (₹): {user_request.budget_min_per_unit} – {user_request.budget_max_per_unit}",
    )
    y -= 25

    # Summary card
    total_cost = sum(r.total_packaging_cost_inr for r in recs) if recs else 0.0
    total_co2 = sum(r.total_co2_kg for r in recs) if recs else 0.0

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, "Summary")
    y -= 18
    pdf.setFont("Helvetica", 10)
    pdf.drawString(left, y, f"Estimated total cost (₹): {total_cost:.2f}")
    y -= 15
    pdf.drawString(left, y, f"Estimated total CO₂ (kg): {total_co2:.2f}")
    y -= 25

    # Selected material section
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, "Selected material")
    y -= 18
    pdf.setFont("Helvetica", 10)

    if user_request.selected_material_name:
        pdf.drawString(left, y, f"Material: {user_request.selected_material_name}")
        y -= 15
        pdf.drawString(left, y, f"Type: {user_request.selected_material_type}")
        y -= 15
        pdf.drawString(
            left,
            y,
            f"Total cost (₹): {float(user_request.selected_total_cost_inr or 0):.2f}",
        )
        y -= 15
        pdf.drawString(
            left,
            y,
            f"Total CO₂ (kg): {float(user_request.selected_total_co2_kg or 0):.2f}",
        )
        y -= 25
    else:
        pdf.drawString(left, y, "No material has been selected yet.")
        y -= 25

    # New page if needed
    if y < 150:
        pdf.showPage()
        y = 800
        pdf.setFont("Helvetica", 10)

    # Recommended materials table header
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, "Recommended materials")
    y -= 18
    pdf.setFont("Helvetica-Bold", 9)

    pdf.drawString(left, y, "Rank")
    pdf.drawString(left + 40, y, "Material")
    pdf.drawString(left + 190, y, "Type")
    pdf.drawString(left + 280, y, "Total CO₂ (kg)")
    pdf.drawString(left + 380, y, "Total cost (₹)")
    pdf.drawString(left + 480, y, "Score")
    y -= 12
    pdf.line(left, y, left + 540, y)
    y -= 10

    # Table rows
    pdf.setFont("Helvetica", 9)
    for idx, r in enumerate(recs, start=1):
        if y < 80:
            pdf.showPage()
            y = 800
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(left, y, "Rank")
            pdf.drawString(left + 40, y, "Material")
            pdf.drawString(left + 190, y, "Type")
            pdf.drawString(left + 280, y, "Total CO₂ (kg)")
            pdf.drawString(left + 380, y, "Total cost (₹)")
            pdf.drawString(left + 480, y, "Score")
            y -= 12
            pdf.line(left, y, left + 540, y)
            y -= 10
            pdf.setFont("Helvetica", 9)

        pdf.drawString(left, y, str(idx))
        pdf.drawString(left + 40, y, r.material_name[:25])
        pdf.drawString(left + 190, y, r.material_type[:18])
        pdf.drawRightString(
            left + 340,
            y,
            f"{float(r.total_co2_kg):.2f}",
        )
        pdf.drawRightString(
            left + 440,
            y,
            f"{float(r.total_packaging_cost_inr):.2f}",
        )
        pdf.drawRightString(
            left + 540,
            y,
            f"{float(r.final_score):.3f}",
        )
        y -= 14

    # Charts page (only if we have data)
    if recs:
        pdf.showPage()

        labels = [r.material_name[:10] for r in recs]
        cost_values = [float(r.total_packaging_cost_inr) for r in recs]
        co2_values = [float(r.total_co2_kg) for r in recs]

        # Cost chart
        d1 = Drawing(500, 200)
        d1.add(String(0, 185, "Total packaging cost by material", fontSize=12))
        bc1 = VerticalBarChart()
        bc1.x = 40
        bc1.y = 40
        bc1.width = 420
        bc1.height = 120
        bc1.data = [cost_values]
        bc1.categoryAxis.categoryNames = labels
        bc1.categoryAxis.labels.angle = 45
        bc1.categoryAxis.labels.dy = -15
        bc1.valueAxis.valueMin = 0
        d1.add(bc1)
        renderPDF.draw(d1, pdf, 50, 520)

        # CO2 chart
        d2 = Drawing(500, 200)
        d2.add(String(0, 185, "Total CO₂ by material", fontSize=12))
        bc2 = VerticalBarChart()
        bc2.x = 40
        bc2.y = 40
        bc2.width = 420
        bc2.height = 120
        bc2.data = [co2_values]
        bc2.categoryAxis.categoryNames = labels
        bc2.categoryAxis.labels.angle = 45
        bc2.categoryAxis.labels.dy = -15
        bc2.valueAxis.valueMin = 0
        d2.add(bc2)
        renderPDF.draw(d2, pdf, 50, 280)

    # Footer
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawCentredString(
        300,
        40,
        "Generated by Ecopack – Sustainable Packaging Advisor",
    )

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    filename = f"ecopack_report_{request_id}.pdf"
    return send_file(
        buffer,
        mimetype="application/pdf",
        download_name=filename,
        as_attachment=True,
    )

@bp.route("/confirm_selection", methods=["POST"])
def confirm_selection():
    data = request.get_json() or {}

    print("data:", data)
    request_id = data.get("request_id")
    material_id = data.get("material_id")

    if not request_id or not material_id:
        return jsonify({"error": "request_id and material_id required"}), 400

    user_req = UserRequest.query.get_or_404(request_id)

    rec = (
        RecommendationLog.query.filter_by(
            request_id=request_id, material_id=material_id
        )
        .first_or_404()
    )

    user_req.selected_material_name = rec.material_name
    user_req.selected_material_type = rec.material_type
    user_req.selected_total_cost_inr = rec.total_packaging_cost_inr
    user_req.selected_total_co2_kg = rec.total_co2_kg

    db.session.commit()

    # dashboard aggregates
    sel_rows = (
        db.session.query(
            UserRequest.selected_material_name,
            func.count(UserRequest.id).label("cnt"),
        )
        .filter(UserRequest.selected_material_name.isnot(None))
        .group_by(UserRequest.selected_material_name)
        .all()
    )

    selected_counts = [
        {"material_name": name, "count": cnt} for name, cnt in sel_rows
    ]

    cat_rows = (
        db.session.query(
            UserRequest.product_category,
            func.count(UserRequest.id).label("cnt"),
        )
        .group_by(UserRequest.product_category)
        .all()
    )

    category_counts = [
        {"category": category, "count": cnt} for category, cnt in cat_rows
    ]

    # last 5 requests with reduction values
    subq = (
        UserRequest.query.filter(
            UserRequest.avg_co2_reduction_pct.isnot(None),
            UserRequest.avg_cost_reduction_pct.isnot(None),
        )
        .order_by(UserRequest.id.desc())
        .limit(5)
        .subquery()
    )

    # overall average reductions vs traditional baselines (last 5)
    avg_co2, avg_cost = (
        db.session.query(
            func.avg(subq.c.avg_co2_reduction_pct),
            func.avg(subq.c.avg_cost_reduction_pct),
        )
        .one()
    )
    avg_co2_reduction_overall, avg_cost_reduction_overall = avg_co2, avg_cost

    pdf_url = url_for("api.report_pdf", request_id=request_id)

    return jsonify(
        {
            "status": "ok",
            "selected_counts": selected_counts,
            "category_counts": category_counts,
            "avg_co2_reduction_overall": avg_co2_reduction_overall,
            "avg_cost_reduction_overall": avg_cost_reduction_overall,
            "pdf_url": pdf_url,
        }
    )


@bp.route("/dashboard", methods=["GET"])
def dashboard():
    # basic counts
    total_requests = UserRequest.query.count()
    requests_with_selection = (
        UserRequest.query.filter(UserRequest.selected_material_name.isnot(None))
        .count()
    )

    # totals for selected cost and CO₂
    total_selected_cost_inr, total_selected_co2_kg = (
        db.session.query(
            func.coalesce(func.sum(UserRequest.selected_total_cost_inr), 0.0),
            func.coalesce(func.sum(UserRequest.selected_total_co2_kg), 0.0),
        )
        .one()
    )

    # material_type_labels, material_type_counts from RecommendationLog
    mat_rows = (
        db.session.query(
            RecommendationLog.material_type,
            func.count(RecommendationLog.id).label("cnt"),
        )
        .group_by(RecommendationLog.material_type)
        .all()
    )
    material_type_labels = [r[0] for r in mat_rows]
    material_type_counts = [r[1] for r in mat_rows]

    # product_category_labels, product_category_counts from UserRequest
    cat_rows = (
        db.session.query(
            UserRequest.product_category,
            func.count(UserRequest.id).label("cnt"),
        )
        .group_by(UserRequest.product_category)
        .all()
    )
    product_category_labels = [r[0] for r in cat_rows]
    product_category_counts = [r[1] for r in cat_rows]

    # last 5 requests with reduction values
    subq = (
        UserRequest.query.filter(
            UserRequest.avg_co2_reduction_pct.isnot(None),
            UserRequest.avg_cost_reduction_pct.isnot(None),
        )
        .order_by(UserRequest.id.desc())
        .limit(5)
        .subquery()
    )

    # overall average reductions vs traditional baselines (last 5)
    avg_co2, avg_cost = (
        db.session.query(
            func.avg(subq.c.avg_co2_reduction_pct),
            func.avg(subq.c.avg_cost_reduction_pct),
        )
        .one()
    )
    print("DASH DEBUG avg_co2, avg_cost =", avg_co2, avg_cost)

    return render_template(
        "dashboard.html",
        total_requests=total_requests,
        requests_with_selection=requests_with_selection,
        total_selected_cost_inr=total_selected_cost_inr,
        total_selected_co2_kg=total_selected_co2_kg,
        material_type_labels=material_type_labels,
        material_type_counts=material_type_counts,
        product_category_labels=product_category_labels,
        product_category_counts=product_category_counts,
        avg_co2_reduction_overall=avg_co2,
        avg_cost_reduction_overall=avg_cost,
    )
