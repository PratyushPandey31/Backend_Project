import os
import csv
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.core.models import Base, UserORM, PropertyORM, ConversationSessionORM

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def extract_city(location_str: str) -> str:
    """Extract city from free text 'Locality, City'"""
    if not location_str:
        return "Unknown"
    parts = [p.strip() for p in location_str.split(",")]
    if len(parts) >= 2:
        return parts[-1]
    return parts[0]

def seed_database_if_empty(force_reset: bool = False):
    """Seed SQLite database from dataset/users.csv and dataset/properties.csv"""
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        if force_reset:
            db.query(PropertyORM).delete()
            db.query(UserORM).delete()
            db.commit()
            logger.info("Existing database tables cleared for reset.")

        user_count = db.query(UserORM).count()
        if user_count > 0 and not force_reset:
            logger.info(f"Database already seeded with {user_count} users.")
            return

        users_csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "dataset", "users.csv")
        properties_csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "dataset", "properties.csv")

        # Fallback if running from root
        if not os.path.exists(users_csv_path):
            users_csv_path = "dataset/users.csv"
            properties_csv_path = "dataset/properties.csv"

        if os.path.exists(users_csv_path):
            with open(users_csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    user = UserORM(
                        user_id=row["user_id"],
                        name=row["name"],
                        city=row.get("city"),
                        preferences=row.get("preferences"),
                        preferred_locations=row.get("preferred_locations"),
                        portfolio_value_preference_inr=row.get("portfolio_value_preference_inr"),
                    )
                    db.merge(user)
            db.commit()
            logger.info("Users seeded successfully.")

        if os.path.exists(properties_csv_path):
            with open(properties_csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    loc = row["location"]
                    city = extract_city(loc)
                    val = float(row["current_estimated_value_inr"]) if row.get("current_estimated_value_inr") else 0.0
                    rent = float(row["annual_rent_inr"]) if row.get("annual_rent_inr") else 0.0
                    area = float(row["area_sqft"]) if row.get("area_sqft") else 0.0
                    purchase = float(row["purchase_price_inr"]) if row.get("purchase_price_inr") else None
                    own_pct = float(row["ownership_percent"]) if row.get("ownership_percent") else 100.0

                    prop = PropertyORM(
                        property_id=row["property_id"],
                        user_id=row["user_id"],
                        property_type=row["property_type"],
                        sub_type=row.get("sub_type"),
                        location=loc,
                        city=city,
                        area_sqft=area,
                        current_estimated_value_inr=val,
                        purchase_price_inr=purchase,
                        annual_rent_inr=rent,
                        occupancy_status=row.get("occupancy_status", "Vacant"),
                        tenant_status=row.get("tenant_status", "No"),
                        ownership_percent=own_pct,
                        status=row.get("status", "Active"),
                    )
                    db.merge(prop)
            db.commit()
            logger.info("Properties seeded successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()
