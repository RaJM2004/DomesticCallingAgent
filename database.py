import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./calling_campaign.db")

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


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), default="Client Account")
    email = Column(String(100), default="client@example.com")
    role = Column(String(20), default="client")  # 'admin' or 'client'
    credits = Column(Float, default=30000.0)     # Default 30,000 credits allocated (supports decimal deductions like 0.3)
    total_calls_made = Column(Integer, default=0)
    vobiz_wallet_balance = Column(Float, default=500.0) # Vobiz carrier recharge balance in INR
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


def init_db():
    Base.metadata.create_all(bind=engine)

    # Auto-migration for existing SQLite database to add columns if missing
    with engine.connect() as conn:
        from sqlalchemy import text
        for col_sql in [
            "ALTER TABLE call_records ADD COLUMN tokens_used REAL DEFAULT 0.0",
            "ALTER TABLE call_records ADD COLUMN course_type VARCHAR(50) DEFAULT 'bca_internship'",
            "ALTER TABLE call_records ADD COLUMN language VARCHAR(20) DEFAULT 'en'",
            "ALTER TABLE campaigns ADD COLUMN course_type VARCHAR(50) DEFAULT 'bca_internship'",
            "ALTER TABLE campaigns ADD COLUMN language VARCHAR(20) DEFAULT 'en'"
        ]:
            try:
                conn.execute(text(col_sql))
                conn.commit()
            except Exception:
                pass

    db = SessionLocal()
    try:
        # Seed default admin and client account if not present
        admin = db.query(Account).filter(Account.role == "admin").first()
        if not admin:
            admin = Account(name="Super Admin", email="admin@vobiz.ai", role="admin", credits=100000.0)
            db.add(admin)

        client = db.query(Account).filter(Account.role == "client").first()
        if not client:
            client = Account(name="Main Client", email="client@vobiz.ai", role="client", credits=30000.0)
            db.add(client)

        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
