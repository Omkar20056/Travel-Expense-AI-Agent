from sqlalchemy.orm import Session
from typing import Optional
from app.models.category import Category, CategoryRule

DEFAULT_CATEGORIES = [
    {"name": "food", "icon": "🍔", "description": "Meals, dining, groceries, cafes, snacks"},
    {"name": "transport", "icon": "🚕", "description": "Flights, trains, taxis, metros, fuel, tolls"},
    {"name": "lodging", "icon": "🏨", "description": "Hotels, hostels, Airbnbs, resorts"},
    {"name": "activities", "icon": "🎟️", "description": "Museums, tours, tickets, shows, excursions"},
    {"name": "shopping", "icon": "🛍️", "description": "Souvenirs, clothing, electronics, personal items"},
    {"name": "fees", "icon": "💳", "description": "ATM fees, FX exchange charges, visas, city taxes"},
    {"name": "other", "icon": "📦", "description": "Miscellaneous or uncategorized expenses"},
]

DEFAULT_KEYWORD_RULES = {
    "food": ["restaurant", "cafe", "coffee", "bistro", "trattoria", "pizza", "gelato", "dinner", "lunch", "breakfast", "starbucks", "mcdonalds", "supermarket", "groceries", "bakery", "bar", "pub"],
    "transport": ["uber", "lyft", "taxi", "train", "flight", "airline", "metro", "subway", "bus", "ferry", "trenitalia", "sncf", "easyjet", "ryanair", "delta", "gas", "fuel", "parking"],
    "lodging": ["hotel", "hostel", "airbnb", "resort", "motel", "inn", "booking.com", "marriott", "hilton"],
    "activities": ["museum", "tour", "ticket", "guide", "excursion", "zoo", "palace", "colosseum", "louvre", "concert", "show", "theater"],
    "shopping": ["souvenir", "mall", "clothing", "zara", "h&m", "duty free", "gift", "shoes", "boutique", "market"],
    "fees": ["atm", "fee", "tax", "exchange", "commission", "visa fee", "tip", "surcharge"],
}

class CategorizationService:
    @classmethod
    def seed_categories(cls, db: Session):
        """Ensures default categories exist in database."""
        for cat_data in DEFAULT_CATEGORIES:
            existing = db.query(Category).filter(Category.name == cat_data["name"]).first()
            if not existing:
                cat = Category(
                    name=cat_data["name"],
                    icon=cat_data["icon"],
                    description=cat_data["description"]
                )
                db.add(cat)
        db.commit()

    @classmethod
    def get_category_by_name(cls, db: Session, name: str) -> Optional[Category]:
        return db.query(Category).filter(Category.name == name.lower().strip()).first()

    @classmethod
    def classify(cls, db: Session, text: str, merchant: Optional[str] = None) -> Category:
        """
        Classifies an expense into a category:
        1. Checks learned user CategoryRules first.
        2. Checks keyword heuristics across merchant and description.
        3. Defaults to 'other'.
        """
        search_terms = []
        if merchant:
            search_terms.append(merchant.strip().lower())
        if text:
            search_terms.extend(text.strip().lower().split())

        # 1. Check user-defined rules in database
        learned_rules = db.query(CategoryRule).all()
        for rule in learned_rules:
            pattern = rule.pattern.lower()
            if any(pattern in term or term in pattern for term in search_terms):
                return rule.category

        # 2. Heuristic keyword matching
        full_text = f"{merchant or ''} {text or ''}".lower()
        for cat_name, keywords in DEFAULT_KEYWORD_RULES.items():
            if any(kw in full_text for kw in keywords):
                cat = cls.get_category_by_name(db, cat_name)
                if cat:
                    return cat

        # 3. Fallback to 'other'
        other_cat = cls.get_category_by_name(db, "other")
        if not other_cat:
            cls.seed_categories(db)
            other_cat = cls.get_category_by_name(db, "other")
        return other_cat

    @classmethod
    def learn_rule(cls, db: Session, pattern: str, category_name: str) -> Optional[CategoryRule]:
        """Saves a user correction to category_rules so the agent learns."""
        pattern_clean = pattern.strip().lower()
        if not pattern_clean:
            return None

        category = cls.get_category_by_name(db, category_name)
        if not category:
            return None

        # Check existing rule
        rule = db.query(CategoryRule).filter(CategoryRule.pattern == pattern_clean).first()
        if rule:
            rule.category_id = category.id
            rule.user_corrected = True
        else:
            rule = CategoryRule(
                pattern=pattern_clean,
                category_id=category.id,
                user_corrected=True
            )
            db.add(rule)

        db.commit()
        db.refresh(rule)
        return rule
