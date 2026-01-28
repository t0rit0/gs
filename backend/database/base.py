"""
Database connection and session management

Supports:
- SQLite (demo/development)
- PostgreSQL (production)
- Easy migration between databases
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ============================================
# Database Configuration
# ============================================

# Environment detection
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DATABASE_URL = os.getenv("DATABASE_URL")

# Data directory
DB_DIR = Path(os.getenv("DB_DIR", "data"))
DB_DIR.mkdir(parents=True, exist_ok=True)

# ============================================
# Database Engine Setup
# ============================================

if ENVIRONMENT == "production":
    # PostgreSQL for production
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set in production")

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using
        pool_size=5,
        max_overflow=10,
        echo=False
    )
else:
    # SQLite for development/demo
    db_path = DB_DIR / "demo.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},  # SQLite specific
        echo=False  # Set to True to see SQL queries
    )

# ============================================
# Session Management
# ============================================

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ============================================
# Base Model
# ============================================

Base = declarative_base()

# ============================================
# Dependency Injection
# ============================================

def get_db():
    """
    Database session dependency for FastAPI

    Usage:
        @app.get("/patients")
        def get_patients(db: Session = Depends(get_db)):
            return db.query(Patient).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================
# Utility Functions
# ============================================

def init_database():
    """
    Initialize database tables

    This will create all tables defined in models.py
    """
    from backend.database.models import Patient, Conversation, Message

    Base.metadata.create_all(bind=engine)

    print(f"✅ Database initialized at: {engine.url}")
    print(f"📊 Tables created:")
    for table_name in Base.metadata.tables.keys():
        print(f"   - {table_name}")

def drop_database():
    """
    Drop all tables (USE WITH CAUTION!)

    This will delete all data in the database
    """
    Base.metadata.drop_all(bind=engine)
    print(f"⚠️  All tables dropped from: {engine.url}")

def reset_database():
    """
    Reset database (drop and recreate)

    Useful for testing/development
    """
    drop_database()
    init_database()

def get_database_info():
    """
    Get database connection information
    """
    return {
        "url": str(engine.url),
        "environment": ENVIRONMENT,
        "driver": engine.dialect.name,
        "tables": list(Base.metadata.tables.keys())
    }

# ============================================
# Main Entry Point
# ============================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database management CLI")
    parser.add_argument("command", choices=["init", "drop", "reset", "info"],
                       help="Command to execute")

    args = parser.parse_args()

    if args.command == "init":
        init_database()
    elif args.command == "drop":
        confirm = input("⚠️  This will delete all data. Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            drop_database()
        else:
            print("Cancelled")
    elif args.command == "reset":
        confirm = input("⚠️  This will delete all data. Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            reset_database()
        else:
            print("Cancelled")
    elif args.command == "info":
        info = get_database_info()
        print("\n📊 Database Information:")
        print(f"   URL: {info['url']}")
        print(f"   Environment: {info['environment']}")
        print(f"   Driver: {info['driver']}")
        print(f"   Tables: {', '.join(info['tables'])}")
