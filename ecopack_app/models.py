from . import db
from datetime import datetime

class UserRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product_name = db.Column(db.String(120))
    product_category = db.Column(db.String(50))
    length_cm = db.Column(db.Float)
    width_cm = db.Column(db.Float)
    height_cm = db.Column(db.Float)
    weight_in_kg = db.Column(db.Float)
    fragility_level = db.Column(db.Integer)
    is_liquid = db.Column(db.Boolean)
    is_delicate = db.Column(db.Boolean)
    is_moisture_sensitive = db.Column(db.Boolean)
    is_temperature_sensitive = db.Column(db.Boolean)

    sustainability_level = db.Column(db.String(20))
    budget_min_per_unit = db.Column(db.Float)
    budget_max_per_unit = db.Column(db.Float)
    total_units = db.Column(db.Integer)
    prior_protection_level = db.Column(db.String(20))

    recommendations = db.relationship("RecommendationLog", backref="request", lazy=True)
    selected_material_name = db.Column(db.String(120), nullable=True)
    selected_material_type = db.Column(db.String(80), nullable=True)
    selected_total_cost_inr = db.Column(db.Float, nullable=True)
    selected_total_co2_kg = db.Column(db.Float, nullable=True)

class RecommendationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("user_request.id"), nullable=False)

    material_id = db.Column(db.Integer)
    material_name = db.Column(db.String(120))
    material_type = db.Column(db.String(80))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    co2_per_kg = db.Column(db.Float)
    cost_per_kg_inr = db.Column(db.Float)
    total_co2_kg = db.Column(db.Float)
    total_packaging_cost_inr = db.Column(db.Float)
    final_score = db.Column(db.Float)


    