from typing import List, Dict, Any, Optional
from copy import deepcopy
from app.core.models import PropertyORM
from app.analytics.portfolio_engine import PortfolioEngine, format_inr

class ScenarioEngine:
    @staticmethod
    def simulate_exclusion(properties: List[PropertyORM], user_id: str, property_ids_to_exclude: List[str]) -> Dict[str, Any]:
        """Simulate excluding one or more properties from the portfolio (What-If analysis)."""
        # Baseline actual metrics
        baseline = PortfolioEngine.calculate_summary(properties, user_id)
        
        # Filtered sandbox list
        excluded_props = [p for p in properties if p.property_id in property_ids_to_exclude]
        remaining_props = [p for p in properties if p.property_id not in property_ids_to_exclude]
        
        # Hypothetical metrics
        hypothetical = PortfolioEngine.calculate_summary(remaining_props, user_id)
        
        # Compute deltas
        val_diff = hypothetical["total_portfolio_value_inr"] - baseline["total_portfolio_value_inr"]
        rent_diff = hypothetical["total_annual_rent_inr"] - baseline["total_annual_rent_inr"]
        yield_diff = hypothetical["overall_rental_yield_pct"] - baseline["overall_rental_yield_pct"]
        
        return {
            "scenario_type": "exclude_properties",
            "is_hypothetical": True,
            "excluded_properties": [
                {
                    "property_id": p.property_id,
                    "location": p.location,
                    "value": format_inr(p.current_estimated_value_inr),
                    "annual_rent": format_inr(p.annual_rent_inr)
                } for p in excluded_props
            ],
            "baseline": {
                "total_properties": baseline["total_properties"],
                "total_value": baseline["total_portfolio_value_formatted"],
                "total_rent": baseline["total_annual_rent_formatted"],
                "yield_pct": f"{baseline['overall_rental_yield_pct']}%",
                "breakdown_by_macro": baseline["breakdown_by_macro_type"]
            },
            "hypothetical": {
                "total_properties": hypothetical["total_properties"],
                "total_value": hypothetical["total_portfolio_value_formatted"],
                "total_rent": hypothetical["total_annual_rent_formatted"],
                "yield_pct": f"{hypothetical['overall_rental_yield_pct']}%",
                "breakdown_by_macro": hypothetical["breakdown_by_macro_type"]
            },
            "impact": {
                "value_change": format_inr(val_diff),
                "value_change_pct": round((val_diff / baseline["total_portfolio_value_inr"] * 100), 2) if baseline["total_portfolio_value_inr"] > 0 else 0.0,
                "rent_change": format_inr(rent_diff),
                "rent_change_pct": round((rent_diff / baseline["total_annual_rent_inr"] * 100), 2) if baseline["total_annual_rent_inr"] > 0 else 0.0,
                "yield_change_points": round(yield_diff, 2)
            }
        }

    @staticmethod
    def simulate_rent_change(properties: List[PropertyORM], user_id: str, property_id: str, new_annual_rent: float) -> Dict[str, Any]:
        """Simulate leasing or changing rent for a property without updating database."""
        baseline = PortfolioEngine.calculate_summary(properties, user_id)
        
        # Clone properties for sandbox
        sandbox_props = []
        target_prop = None
        for p in properties:
            clone = PropertyORM(
                property_id=p.property_id,
                user_id=p.user_id,
                property_type=p.property_type,
                sub_type=p.sub_type,
                location=p.location,
                city=p.city,
                area_sqft=p.area_sqft,
                current_estimated_value_inr=p.current_estimated_value_inr,
                annual_rent_inr=new_annual_rent if p.property_id == property_id else p.annual_rent_inr,
                occupancy_status="Tenanted" if (p.property_id == property_id and new_annual_rent > 0) else p.occupancy_status,
                tenant_status="Yes" if (p.property_id == property_id and new_annual_rent > 0) else p.tenant_status,
                status=p.status
            )
            sandbox_props.append(clone)
            if p.property_id == property_id:
                target_prop = p

        hypothetical = PortfolioEngine.calculate_summary(sandbox_props, user_id)
        rent_diff = hypothetical["total_annual_rent_inr"] - baseline["total_annual_rent_inr"]
        yield_diff = hypothetical["overall_rental_yield_pct"] - baseline["overall_rental_yield_pct"]

        return {
            "scenario_type": "simulate_rent_change",
            "is_hypothetical": True,
            "target_property": target_prop.location if target_prop else property_id,
            "baseline": {
                "total_rent": baseline["total_annual_rent_formatted"],
                "yield_pct": f"{baseline['overall_rental_yield_pct']}%"
            },
            "hypothetical": {
                "total_rent": hypothetical["total_annual_rent_formatted"],
                "yield_pct": f"{hypothetical['overall_rental_yield_pct']}%"
            },
            "impact": {
                "rent_change": format_inr(rent_diff),
                "yield_change_points": round(yield_diff, 2)
            }
        }
