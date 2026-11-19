from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# SQLite configuration: check_same_thread=False for multi-threaded FastAPI handlers
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def upgrade_schema():
    """Ensure newly introduced columns exist in SQLite database without losing data."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    with engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(expenses)"))
            existing = {row[1] for row in result.fetchall()}
            new_cols = [
                ("paid_by_name", "VARCHAR(100)"),
                ("split_with", "TEXT"),
                ("payment_mode", "VARCHAR(50) DEFAULT 'Cash'"),
                ("reference_id", "VARCHAR(100)"),
                ("is_anomaly", "BOOLEAN DEFAULT 0"),
                ("anomaly_reason", "VARCHAR(255)")
            ]
            for col_name, col_type in new_cols:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE expenses ADD COLUMN {col_name} {col_type}"))
            conn.commit()
        except Exception as e:
            print(f"Schema upgrade notice: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
