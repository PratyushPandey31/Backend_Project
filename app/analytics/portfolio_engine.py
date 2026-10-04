from typing import List, Dict, Any, Optional
from app.core.models import PropertyORM

def format_inr(val: Optional[float]) -> str:
    """Format numeric values into standard Indian Wealth Management denominations (Cr/Lakh)."""
    if val is None:
        return "N/A"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 10000000:  # 1 Crore = 10,000,000
        return f"{sign}₹{abs_val / 10000000:.2f} Cr"
    elif abs_val >= 100000:  # 1 Lakh = 100,000
        return f"{sign}₹{abs_val / 100000:.2f} L"
    else:
        return f"{sign}₹{abs_val:,.0f}"

def canonical_macro_category(prop_type: str) -> str:
    """Normalize inconsistent property types into macro asset classes."""
    pt = prop_type.strip().lower() if prop_type else ""
    if "retail" in pt:
        return "Retail"
    elif "office" in pt or "commercial" in pt:
        return "Commercial / Office"
    elif "resident" in pt or "apartment" in pt or "villa" in pt:
        return "Residential"
    return "Other"

class PortfolioEngine:
    @staticmethod
    def calculate_summary(properties: List[PropertyORM], user_id: str) -> Dict[str, Any]:
        """Compute full deterministic portfolio metrics from a list of properties."""
        total_props = len(properties)
        if total_props == 0:
            return {
                "user_id": user_id,
                "total_properties": 0,
                "total_portfolio_value_inr": 0.0,
                "total_portfolio_value_formatted": "₹0",
                "total_annual_rent_inr": 0.0,
                "total_annual_rent_formatted": "₹0",
                "overall_rental_yield_pct": 0.0,
                "total_area_sqft": 0.0,
                "occupancy_rate_pct": 0.0,
                "breakdown_by_type": {},
                "breakdown_by_macro_type": {},
                "breakdown_by_city": {},
                "occupancy_breakdown": {},
                "properties": []
            }

        total_value = sum(p.current_estimated_value_inr for p in properties)
        total_rent = sum(p.annual_rent_inr for p in properties)
        total_area = sum(p.area_sqft for p in properties)
        
        # Calculate yield: only on tenanted properties or overall
        overall_yield = (total_rent / total_value * 100) if total_value > 0 else 0.0

        # Detailed Breakdowns
        by_type: Dict[str, Dict[str, Any]] = {}
        by_macro: Dict[str, Dict[str, Any]] = {}
        by_city: Dict[str, Dict[str, Any]] = {}
        by_occupancy: Dict[str, int] = {"Tenanted": 0, "Vacant": 0, "Self-occupied": 0}

        tenanted_area = 0.0
        for p in properties:
            # Breakdown by specific property_type
            pt = p.property_type
            if pt not in by_type:
                by_type[pt] = {"count": 0, "value": 0.0, "rent": 0.0, "area": 0.0}
            by_type[pt]["count"] += 1
            by_type[pt]["value"] += p.current_estimated_value_inr
            by_type[pt]["rent"] += p.annual_rent_inr
            by_type[pt]["area"] += p.area_sqft

            # Breakdown by macro category (Commercial/Office vs Retail vs Residential)
            macro = canonical_macro_category(pt)
            if macro not in by_macro:
                by_macro[macro] = {"count": 0, "value": 0.0, "rent": 0.0, "area": 0.0}
            by_macro[macro]["count"] += 1
            by_macro[macro]["value"] += p.current_estimated_value_inr
            by_macro[macro]["rent"] += p.annual_rent_inr
            by_macro[macro]["area"] += p.area_sqft

            # Breakdown by city
            city = p.city or "Unknown"
            if city not in by_city:
                by_city[city] = {"count": 0, "value": 0.0, "rent": 0.0}
            by_city[city]["count"] += 1
            by_city[city]["value"] += p.current_estimated_value_inr
            by_city[city]["rent"] += p.annual_rent_inr

            # Occupancy
            occ = p.occupancy_status or "Vacant"
            if occ in by_occupancy:
                by_occupancy[occ] += 1
            else:
                by_occupancy[occ] = 1

            if occ.lower() == "tenanted":
                tenanted_area += p.area_sqft

        # Calculate percentages
        for k, v in by_type.items():
            v["value_share_pct"] = round((v["value"] / total_value * 100), 2) if total_value > 0 else 0.0
            v["yield_pct"] = round((v["rent"] / v["value"] * 100), 2) if v["value"] > 0 else 0.0
            v["value_formatted"] = format_inr(v["value"])
            v["rent_formatted"] = format_inr(v["rent"])

        for k, v in by_macro.items():
            v["value_share_pct"] = round((v["value"] / total_value * 100), 2) if total_value > 0 else 0.0
            v["yield_pct"] = round((v["rent"] / v["value"] * 100), 2) if v["value"] > 0 else 0.0
            v["value_formatted"] = format_inr(v["value"])
            v["rent_formatted"] = format_inr(v["rent"])

        for k, v in by_city.items():
            v["value_share_pct"] = round((v["value"] / total_value * 100), 2) if total_value > 0 else 0.0
            v["value_formatted"] = format_inr(v["value"])
            v["rent_formatted"] = format_inr(v["rent"])

        # Occupancy rate based on area
        occupancy_rate = (tenanted_area / total_area * 100) if total_area > 0 else 0.0

        # Detailed property items
        prop_items = []
        for p in properties:
            p_yield = (p.annual_rent_inr / p.current_estimated_value_inr * 100) if p.current_estimated_value_inr > 0 else 0.0
            rate_sqft = (p.current_estimated_value_inr / p.area_sqft) if p.area_sqft > 0 else 0.0
            rent_sqft_mo = (p.annual_rent_inr / (12 * p.area_sqft)) if p.area_sqft > 0 else 0.0
            
            prop_items.append({
                "property_id": p.property_id,
                "property_type": p.property_type,
                "sub_type": p.sub_type,
                "location": p.location,
                "city": p.city,
                "area_sqft": p.area_sqft,
                "current_estimated_value_inr": p.current_estimated_value_inr,
                "current_estimated_value_formatted": format_inr(p.current_estimated_value_inr),
                "purchase_price_inr": p.purchase_price_inr,
                "purchase_price_formatted": format_inr(p.purchase_price_inr) if p.purchase_price_inr else "Not Recorded",
                "annual_rent_inr": p.annual_rent_inr,
                "annual_rent_formatted": format_inr(p.annual_rent_inr),
                "rental_yield_pct": round(p_yield, 2),
                "occupancy_status": p.occupancy_status,
                "tenant_status": p.tenant_status,
                "rate_per_sqft": round(rate_sqft, 1),
                "rent_per_sqft_month": round(rent_sqft_mo, 1),
                "status": p.status
            })

        # Find extremes
        highest_val_prop = max(prop_items, key=lambda x: x["current_estimated_value_inr"]) if prop_items else None
        lowest_val_prop = min(prop_items, key=lambda x: x["current_estimated_value_inr"]) if prop_items else None
        highest_rent_prop = max(prop_items, key=lambda x: x["annual_rent_inr"]) if prop_items else None

        return {
            "user_id": user_id,
            "total_properties": total_props,
            "total_portfolio_value_inr": total_value,
            "total_portfolio_value_formatted": format_inr(total_value),
            "total_annual_rent_inr": total_rent,
            "total_annual_rent_formatted": format_inr(total_rent),
            "overall_rental_yield_pct": round(overall_yield, 2),
            "total_area_sqft": total_area,
            "occupancy_rate_pct": round(occupancy_rate, 1),
            "highest_value_property": highest_val_prop,
            "lowest_value_property": lowest_val_prop,
            "highest_annual_rent_property": highest_rent_prop,
            "breakdown_by_type": by_type,
            "breakdown_by_macro_type": by_macro,
            "breakdown_by_city": by_city,
            "occupancy_breakdown": by_occupancy,
            "properties": prop_items
        }
