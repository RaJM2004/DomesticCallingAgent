import os
import secrets
import bcrypt
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./calling_campaign.db")

# Normalize Railway's legacy postgres:// prefix to postgresql:// for SQLAlchemy
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# For SQLite, enable WAL mode and configure connect args
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

# Optimize SQLite performance for 30,000+ records (Write-Ahead Logging & Foreign Keys)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=15000")  # 15s wait if locked
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# -------------------------------------------------------------
# Security & Auth Helpers
# -------------------------------------------------------------
def hash_password(password: str) -> str:
    """Generate secure bcrypt password hash (max 72 bytes)."""
    if not password:
        return ""
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain text password against bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


def generate_api_token() -> str:
    """Generate a high-entropy secret bearer token for API/user sessions."""
    return f"vobiz_tok_{secrets.token_urlsafe(32)}"


# -------------------------------------------------------------
# Models
# -------------------------------------------------------------
class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), default="Client Account")
    email = Column(String(100), default="client@example.com")
    username = Column(String(50), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    api_token = Column(String(100), unique=True, index=True, nullable=True)
    role = Column(String(20), default="client")  # 'admin' or 'client'
    credits = Column(Float, default=30000.0)     # Allocated call credits/tokens
    total_calls_made = Column(Integer, default=0)
    vobiz_wallet_balance = Column(Float, default=500.0) # Vobiz carrier recharge balance in INR
    is_active = Column(Integer, default=1)       # 1 = active, 0 = disabled
    created_at = Column(DateTime, default=datetime.utcnow)

    campaigns = relationship("Campaign", back_populates="account", cascade="all, delete-orphan")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True)
    name = Column(String(150), default="Excel Calling Campaign")
    file_name = Column(String(255), default="")
    course_type = Column(String(50), default="bca_internship") # 'bca_internship', 'distance_education', 'deep_courses'
    language = Column(String(20), default="en")                # 'en', 'hi', 'kn'
    total_numbers = Column(Integer, default=0)
    completed_numbers = Column(Integer, default=0)
    status = Column(String(30), default="idle")  # 'idle', 'running', 'paused', 'completed'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship("Account", back_populates="campaigns")
    calls = relationship("CallRecord", back_populates="campaign", cascade="all, delete-orphan")


class CallRecord(Base):
    __tablename__ = "call_records"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), index=True)
    phone_number = Column(String(30), index=True)
    customer_name = Column(String(100), default="")
    course_type = Column(String(50), default="bca_internship")
    language = Column(String(20), default="en")
    status = Column(String(30), default="pending")  # 'pending', 'dialing', 'answered', 'completed', 'busy', 'no-answer', 'failed'
    dtmf_digit = Column(String(10), default="")     # '1', '2', etc.
    audio_flow = Column(String(150), default="")    # Flow played (e.g. welcome.wav -> audio_1.wav)
    response_note = Column(Text, default="")         # Human-readable annotated response
    duration_sec = Column(Float, default=0.0)
    carrier_cost_inr = Column(Float, default=0.0)
    tokens_used = Column(Float, default=0.0)         # 1.0 for answered, 0.3 for unanswered/failed/declined
    vobiz_call_uuid = Column(String(100), index=True, default="")
    called_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="calls")


# -------------------------------------------------------------
# Database Initialization & Auto-Migration
# -------------------------------------------------------------
def init_db():
    Base.metadata.create_all(bind=engine)

    # Auto-migration for existing SQLite / PostgreSQL database to add columns if missing
    with engine.connect() as conn:
        from sqlalchemy import text
        for col_sql in [
            "ALTER TABLE call_records ADD COLUMN tokens_used REAL DEFAULT 0.0",
            "ALTER TABLE call_records ADD COLUMN course_type VARCHAR(50) DEFAULT 'bca_internship'",
            "ALTER TABLE call_records ADD COLUMN language VARCHAR(20) DEFAULT 'en'",
            "ALTER TABLE campaigns ADD COLUMN course_type VARCHAR(50) DEFAULT 'bca_internship'",
            "ALTER TABLE campaigns ADD COLUMN language VARCHAR(20) DEFAULT 'en'",
            "ALTER TABLE accounts ADD COLUMN username VARCHAR(50)",
            "ALTER TABLE accounts ADD COLUMN password_hash VARCHAR(255)",
            "ALTER TABLE accounts ADD COLUMN api_token VARCHAR(100)",
            "ALTER TABLE accounts ADD COLUMN is_active INTEGER DEFAULT 1"
        ]:
            try:
                conn.execute(text(col_sql))
                conn.commit()
            except Exception:
                pass

    db = SessionLocal()
    try:
        # Seed or backfill default admin account
        admin = db.query(Account).filter((Account.role == "admin") | (Account.username == "admin")).first()
        if not admin:
            admin = Account(
                name="Super Admin",
                email="admin@vobiz.ai",
                username="admin",
                password_hash=hash_password("admin123"),
                api_token=generate_api_token(),
                role="admin",
                credits=100000.0,
                is_active=1
            )
            db.add(admin)
        else:
            if not admin.username:
                admin.username = "admin"
            if not admin.password_hash:
                admin.password_hash = hash_password("admin123")
            if not admin.api_token:
                admin.api_token = generate_api_token()
            if admin.is_active is None:
                admin.is_active = 1

        # Seed or backfill default client account
        client = db.query(Account).filter((Account.role == "client") | (Account.username == "user")).first()
        if not client:
            client = Account(
                name="Main Client",
                email="client@vobiz.ai",
                username="user",
                password_hash=hash_password("user123"),
                api_token=generate_api_token(),
                role="client",
                credits=30000.0,
                is_active=1
            )
            db.add(client)
        else:
            if not client.username:
                client.username = "user"
            if not client.password_hash:
                client.password_hash = hash_password("user123")
            if not client.api_token:
                client.api_token = generate_api_token()
            if client.is_active is None:
                client.is_active = 1

        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
