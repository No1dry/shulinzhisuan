"""
Database upgrade script - add missing columns to existing SQLite tables.
Run once after model changes.
"""
import sqlite3
import os
from app.config import settings

def upgrade_database():
    """Add missing columns to problem_reports table."""
    db_path = settings.DATABASE_URL.replace("sqlite:////", "/")
    
    if not os.path.exists(db_path):
        print(f"[DB Upgrade] Database not found at {db_path}, will be created by SQLAlchemy.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check existing columns in problem_reports
    cursor.execute("PRAGMA table_info(problem_reports)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # Columns to add: (name, type, default)
    new_columns = [
        ("replies", "TEXT", "'[]'"),
        ("is_negotiation", "BOOLEAN", "0"),
        ("topic", "VARCHAR(500)", "NULL"),
        ("participants", "TEXT", "'[]'"),
    ]
    
    added = 0
    for col_name, col_type, default in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE problem_reports ADD COLUMN {col_name} {col_type} DEFAULT {default}")
                print(f"[DB Upgrade] Added column: {col_name}")
                added += 1
            except Exception as e:
                print(f"[DB Upgrade] Failed to add {col_name}: {e}")
        else:
            print(f"[DB Upgrade] Column already exists: {col_name}")
    
    conn.commit()
    conn.close()
    
    if added > 0:
        print(f"[DB Upgrade] Success! Added {added} new columns.")
    else:
        print("[DB Upgrade] All columns already up to date.")


def create_new_tables():
    """Create new tables that don't exist yet (notices, news, policies, resident_users)."""
    db_path = settings.DATABASE_URL.replace("sqlite:////", "/")
    
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables = {
        "notices": """
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                category VARCHAR(50) DEFAULT '通知',
                is_top BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """,
        "news_items": """
            CREATE TABLE IF NOT EXISTS news_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                summary TEXT,
                content TEXT,
                source VARCHAR(100),
                cover_image VARCHAR(500),
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """,
        "policies": """
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                summary TEXT,
                content TEXT,
                category VARCHAR(50) DEFAULT '综合',
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """,
        "resident_users": """
            CREATE TABLE IF NOT EXISTS resident_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(100),
                avatar VARCHAR(500),
                id_card_last4 VARCHAR(10),
                grid_name VARCHAR(100),
                address VARCHAR(500),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """,
    }
    
    for table_name, create_sql in tables.items():
        try:
            cursor.execute(create_sql)
            print(f"[DB Upgrade] Created table: {table_name}")
        except Exception as e:
            print(f"[DB Upgrade] Table {table_name} may exist: {e}")
    
    conn.commit()
    conn.close()


def run_upgrade():
    """Run all upgrades."""
    print("[DB Upgrade] Starting database upgrade...")
    upgrade_database()
    create_new_tables()
    print("[DB Upgrade] Done.")
