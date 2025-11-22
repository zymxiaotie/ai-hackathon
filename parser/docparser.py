"""
Google Drive Tender Intelligence Assistant v2
Production-ready with proper error recovery, file hashing, and version control

Features:
- File hash-based version control
- Retry failed processing
- Folder-based organization
- Comprehensive error handling
- Processing status tracking

Dependencies:
pip install openai pymupdf sentence-transformers psycopg2-binary pgvector python-dotenv pydantic
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
pip install flask gunicorn
"""

import os
import json
import hashlib
import time
import traceback
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import io
from typing import List, Dict, Optional, Tuple

import fitz  # PyMuPDF
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from psycopg2.extras import Json, execute_batch
import psycopg2
from psycopg2.extras import Json
from pydantic import BaseModel
from dotenv import load_dotenv
from enum import Enum
from psycopg2.pool import ThreadedConnectionPool
from flask import Flask, request, jsonify
# Google Drive imports
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
# Load environment variables
load_dotenv()

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tender_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS
# ============================================================================

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    HASH_UNCHANGED = "hash_unchanged"

class DocumentType(str, Enum):
    ITT = "ITT"  # Invitation to Tender
    ADDENDUM = "addendum"
    CLARIFICATION = "clarification"
    DRAWING = "drawing"
    SPECIFICATION = "specification"
    BOQ = "boq"  # Bill of Quantities
    OTHER = "other"


# ============================================================================
# CONFIGURATION
# ============================================================================

# LLM API Configuration
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL", "https://api-inference.bitdeer.ai/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-120b")

# Database Configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "tender_intelligence"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password")
}

# Google Drive Configuration
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Local storage
LOCAL_DOWNLOAD_DIR = Path(os.getenv("LOCAL_DOWNLOAD_DIR", "./gdrive_downloads"))
LOCAL_DOWNLOAD_DIR.mkdir(exist_ok=True)

# Flask Configuration
FLASK_PORT = int(os.getenv("FLASK_PORT", "5001"))

# ============================================================================
# GLOBAL INITIALIZATION
# ============================================================================

app = Flask(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# Initialize embedding model
logger.info("Loading BAAI/bge-m3 embedding model...")
embedding_model = SentenceTransformer('BAAI/bge-m3')
logger.info("Embedding model loaded successfully!")
# Processing configuration
# Processing Configuration
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "300"))
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
RETRY_DELAY_MINUTES = int(os.getenv("RETRY_DELAY_MINUTES", "30"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_FAILED_FILES = os.getenv("RETRY_FAILED_FILES", "true").lower() == "true"

# Initialize clients
try:
    openai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    logger.info("OpenAI client initialized")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    openai_client = None

# Initialize BAAI embedding model
try:
    logger.info("Loading BAAI/bge-m3 embedding model...")
    embedding_model = SentenceTransformer('BAAI/bge-m3')
    logger.info("OK Embedding model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load embedding model: {e}")
    embedding_model = None
# Database connection pool
db_pool = ThreadedConnectionPool(minconn=1, maxconn=10, **DB_CONFIG)

# ============================================================================
# DATABASE HELPER
# ============================================================================

class DatabaseConnection:
    """Context manager for database connections"""
    
    def __enter__(self):
        self.conn = db_pool.getconn()
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.conn.rollback()
        db_pool.putconn(self.conn)
# ============================================================================
# DATABASE SETUP - COMPLETE SCHEMA
# ============================================================================

def setup_database():
    """
    Create complete database schema following complete_db_architecture.md
    """
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Enable pgvector
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.info("pgvector extension enabled")
        
        # ====================================================================
        # GROUP 1: TENDER MASTER DATA
        # ====================================================================
        
        # Main tenders table - COMPLETE with all columns
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tenders (
                tender_id SERIAL PRIMARY KEY,
                
                -- Basic Information
                tender_title VARCHAR(500) NOT NULL,
                tender_reference_number VARCHAR(100) NOT NULL UNIQUE,
                issuing_authority VARCHAR(200),
                
                -- Key Dates
                submission_deadline TIMESTAMP NOT NULL,
                clarification_closing_date TIMESTAMP,
                tender_validity_period VARCHAR(100),
                
                -- Submission Details
                submission_portal_url VARCHAR(500),
                submission_mode VARCHAR(100),
                number_of_copies_required INTEGER,
                required_signatory_authority VARCHAR(200),
                submission_instructions TEXT,
                
                -- Project Details
                project_name VARCHAR(300),
                site_location VARCHAR(300),
                project_start_date DATE,
                project_completion_date DATE,
                contract_type VARCHAR(100),
                scope_of_works TEXT,
                
                -- Contract Terms
                liquidated_damages VARCHAR(200),
                performance_bond_percentage DECIMAL(5,2),
                retention_percentage DECIMAL(5,2),
                defects_liability_period VARCHAR(100),
                warranty_period VARCHAR(100),
                
                -- Metadata
                document_source VARCHAR(500),
                processing_status VARCHAR(50) DEFAULT 'pending',
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Indexes for tenders
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tender_ref ON tenders(tender_reference_number);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_submission_deadline ON tenders(submission_deadline);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_processing_status ON tenders(processing_status);")
        
              
        # Tender required documents
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tender_required_documents (
                requirement_doc_id SERIAL PRIMARY KEY,
                tender_id INTEGER NOT NULL,
                
                -- Document Details
                document_name VARCHAR(300) NOT NULL,
                document_category VARCHAR(100),
                is_mandatory BOOLEAN DEFAULT TRUE,
                is_received BOOLEAN DEFAULT FALSE,
                description TEXT,
                
                -- Addendum tracking
                source VARCHAR(50) DEFAULT 'original',
                introduced_by_addendum_id INTEGER,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
            );
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tender_req_docs ON tender_required_documents(tender_id);")
        
        # Tender received documents
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tender_received_documents (
                received_doc_id SERIAL PRIMARY KEY,
                tender_id INTEGER NOT NULL,
                document_name VARCHAR(300) NOT NULL,
                file_path VARCHAR(500),
                file_size_kb INTEGER,
                file_hash VARCHAR(64),
                received_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                uploaded_by VARCHAR(200),
                
                FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
            );
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tender_recv_docs ON tender_received_documents(tender_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON tender_received_documents(file_hash);")
        
        # ====================================================================
        # GROUP 2: QUALIFICATION TRACKING
        # ====================================================================
        
        # Tender qualification criteria - COMPLETE
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tender_qualification_criteria (
                criteria_id SERIAL PRIMARY KEY,
                tender_id INTEGER NOT NULL,
                
                -- Requirement Details
                criteria_type VARCHAR(50) NOT NULL,
                criteria_description TEXT NOT NULL,
                criteria_value VARCHAR(200),
                
                -- Matching Results
                is_met BOOLEAN,
                confidence_score DECIMAL(3,2),
                notes TEXT,
                checked_date TIMESTAMP,
                
                -- Tracking
                source VARCHAR(50) DEFAULT 'original',
                introduced_by_addendum_id INTEGER,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                requires_recheck BOOLEAN DEFAULT FALSE,
                
                FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
            );
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tender_criteria ON tender_qualification_criteria(tender_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_requires_recheck ON tender_qualification_criteria(requires_recheck);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_criteria_type ON tender_qualification_criteria(criteria_type);")
        
        # ====================================================================
        # GROUP 3: ADDENDA & CHANGE MANAGEMENT
        # ====================================================================
        
        # Tender addenda
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tender_addenda (
                addendum_id SERIAL PRIMARY KEY,
                tender_id INTEGER NOT NULL,
                
                -- Addendum Details
                addendum_number INTEGER NOT NULL,
                addendum_type VARCHAR(50),
                title VARCHAR(300),
                summary TEXT,
                
                -- Source
                email_source VARCHAR(500),
                attachment_paths TEXT,
                file_hash VARCHAR(64),
                received_date TIMESTAMP NOT NULL,
                
                -- Processing
                processed BOOLEAN DEFAULT FALSE,
                processed_date TIMESTAMP,
                status VARCHAR(50) DEFAULT 'active',
                
                FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
                UNIQUE(tender_id, addendum_number)
            );
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tender_addenda ON tender_addenda(tender_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_addendum_status ON tender_addenda(processed);")
        
        # Addendum changes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS addendum_changes (
                change_id SERIAL PRIMARY KEY,
                addendum_id INTEGER NOT NULL,
                
                -- What changed
                affected_table VARCHAR(100) NOT NULL,
                affected_record_id INTEGER NOT NULL,
                field_name VARCHAR(100) NOT NULL,
                old_value TEXT,
                new_value TEXT,
                change_type VARCHAR(50),
                change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (addendum_id) REFERENCES tender_addenda(addendum_id) ON DELETE CASCADE
            );
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_addendum_changes ON addendum_changes(addendum_id);")
        
        # Tender document versions - VERSION CONTROL
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tender_document_versions (
                document_version_id SERIAL PRIMARY KEY,
                tender_id INTEGER NOT NULL,
                
                -- Document Details
                document_name VARCHAR(300) NOT NULL,
                version_number VARCHAR(50) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size_kb INTEGER,
                file_hash VARCHAR(64) UNIQUE NOT NULL,
                
                -- Version Control
                is_current BOOLEAN DEFAULT TRUE,
                superseded_by INTEGER,
                introduced_by_addendum_id INTEGER,
                uploaded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE,
                FOREIGN KEY (superseded_by) REFERENCES tender_document_versions(document_version_id),
                FOREIGN KEY (introduced_by_addendum_id) REFERENCES tender_addenda(addendum_id)
            );
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_doc_versions ON tender_document_versions(tender_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_current_docs ON tender_document_versions(tender_id, is_current);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_doc_hash ON tender_document_versions(file_hash);")
        
       
        # ====================================================================
        # GROUP 4: PROCESSING COORDINATION
        # ====================================================================
        
        # Processing log - n8n orchestration tracking
        cur.execute("""
            CREATE TABLE IF NOT EXISTS processing_log (
                log_id SERIAL PRIMARY KEY,
                tender_id INTEGER NOT NULL,
                
                -- Workflow Details
                module_name VARCHAR(100) NOT NULL,
                workflow_execution_id VARCHAR(200),
                status VARCHAR(50) NOT NULL,
                
                -- Timing
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                duration_seconds INTEGER,
                
                -- Results
                output_data TEXT,
                error_message TEXT,
                
                FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
            );
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_processing_log ON processing_log(tender_id, module_name);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_processing_status ON processing_log(status);")
        
        # Google Drive processed files tracking - ENHANCED
        cur.execute("""
                CREATE TABLE IF NOT EXISTS gdrive_file_tracking (
                    tracking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    gdrive_file_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    folder_structure TEXT,
                    file_hash VARCHAR(64) NOT NULL,
                    file_size_bytes BIGINT,
                    file_modified_at TIMESTAMP,
                    
                    -- Processing status
                    processing_status VARCHAR(50) DEFAULT 'pending',
                    retry_count INTEGER DEFAULT 0,
                    last_retry_at TIMESTAMP,
                    last_error TEXT,
                    
                    -- Linkage
                    tender_id UUID REFERENCES tenders(tender_id) ON DELETE SET NULL,
                    
                    -- Metadata
                    first_discovered_at TIMESTAMP DEFAULT NOW(),
                    last_checked_at TIMESTAMP DEFAULT NOW(),
                    successfully_processed_at TIMESTAMP,
                    
                    -- Version tracking
                    is_latest_version BOOLEAN DEFAULT TRUE,
                    previous_version_id UUID REFERENCES gdrive_file_tracking(tracking_id),
                    version_number INTEGER DEFAULT 1,
                    
                    UNIQUE(gdrive_file_id, file_hash)
                );
                
                CREATE INDEX IF NOT EXISTS idx_gdrive_file_id ON gdrive_file_tracking(gdrive_file_id);
                CREATE INDEX IF NOT EXISTS idx_file_hash ON gdrive_file_tracking(file_hash);
                CREATE INDEX IF NOT EXISTS idx_processing_status ON gdrive_file_tracking(processing_status);
                CREATE INDEX IF NOT EXISTS idx_tender_id ON gdrive_file_tracking(tender_id);
                CREATE INDEX IF NOT EXISTS idx_is_latest ON gdrive_file_tracking(is_latest_version);
            """)
        # ====================================================================
        # VECTOR DATABASE TABLES
        # ====================================================================
        
        # Tender document chunks - 1024 dimensions for BAAI/bge-m3
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tender_document_chunks (
                chunk_id SERIAL PRIMARY KEY,
                tender_id INTEGER NOT NULL,
                document_name VARCHAR(255),
                document_hash VARCHAR(64),
                chunk_text TEXT NOT NULL,
                chunk_index INTEGER,
                page_number INTEGER,
                section_title VARCHAR(255),
                embedding vector(1024),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (tender_id) REFERENCES tenders(tender_id) ON DELETE CASCADE
            );
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_tender_chunks_embedding 
            ON tender_document_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tender_chunks ON tender_document_chunks(tender_id);")
        
        # Company capabilities chunks
        cur.execute("""
            CREATE TABLE IF NOT EXISTS company_capabilities_chunks (
                capability_chunk_id SERIAL PRIMARY KEY,
                capability_text TEXT NOT NULL,
                chunk_type VARCHAR(100),
                embedding vector(1024),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_chunks_embedding 
            ON company_capabilities_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)
        
        conn.commit()
        logger.info("OK Complete database schema created successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Database setup failed: {e}\n{traceback.format_exc()}")
        raise
    finally:
        cur.close()
        conn.close()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating hash: {e}")
        return None

def safe_db_connect():
    """Safely connect to database"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

def safe_json_parse(text: str) -> dict:
    """Safely parse JSON with cleanup"""
    try:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        raise
# ============================================================================
# FILE HASHING AND VERSION CONTROL
# ============================================================================

def calculate_file_hash(file_path: Path) -> str:
    """Calculate MD5 hash of file"""
    
    md5_hash = hashlib.md5()
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    
    return md5_hash.hexdigest()

def get_file_tracking_info(gdrive_file_id: str, file_hash: str = None) -> Optional[Dict]:
    """Get file tracking information"""
    
    try:
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                if file_hash:
                    # Check by file_id and hash
                    cur.execute("""
                        SELECT tracking_id, processing_status, retry_count, 
                               tender_id, version_number, is_latest_version
                        FROM gdrive_file_tracking
                        WHERE gdrive_file_id = %s AND file_hash = %s
                    """, (gdrive_file_id, file_hash))
                else:
                    # Get latest version by file_id
                    cur.execute("""
                        SELECT tracking_id, processing_status, retry_count, 
                               tender_id, version_number, is_latest_version, file_hash
                        FROM gdrive_file_tracking
                        WHERE gdrive_file_id = %s AND is_latest_version = TRUE
                        ORDER BY version_number DESC
                        LIMIT 1
                    """, (gdrive_file_id,))
                
                result = cur.fetchone()
                
                if result:
                    return {
                        "tracking_id": str(result[0]),
                        "processing_status": result[1],
                        "retry_count": result[2],
                        "tender_id": str(result[3]) if result[3] else None,
                        "version_number": result[4],
                        "is_latest_version": result[5],
                        "file_hash": result[6] if len(result) > 6 else file_hash
                    }
                
                return None
    
    except Exception as e:
        logger.error(f"Error getting file tracking info: {e}")
        return None

def should_process_file(gdrive_file_id: str, file_hash: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Determine if file should be processed
    
    Returns:
        (should_process, reason, tracking_id)
    """
    
    tracking_info = get_file_tracking_info(gdrive_file_id)
    
    if not tracking_info:
        return (True, "new_file", None)
    
    # Check if hash changed (new version)
    if tracking_info['file_hash'] != file_hash:
        return (True, "new_version", tracking_info['tracking_id'])
    
    # Check processing status
    status = tracking_info['processing_status']
    retry_count = tracking_info['retry_count']
    
    if status == ProcessingStatus.COMPLETED:
        return (False, "already_processed", tracking_info['tracking_id'])
    
    if status == ProcessingStatus.FAILED:
        if retry_count < MAX_RETRY_ATTEMPTS:
            return (True, "retry_failed", tracking_info['tracking_id'])
        else:
            return (False, "max_retries_exceeded", tracking_info['tracking_id'])
    
    if status in [ProcessingStatus.PENDING, ProcessingStatus.RETRY]:
        return (True, "pending_retry", tracking_info['tracking_id'])
    
    return (True, "reprocess", tracking_info['tracking_id'])

def create_or_update_tracking(
    gdrive_file_id: str,
    file_name: str,
    file_path: str,
    folder_structure: str,
    file_hash: str,
    file_size: int,
    file_modified: datetime,
    previous_tracking_id: str = None
) -> str:
    """Create or update file tracking record"""
    
    try:
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                # If there's a previous version, mark it as not latest
                if previous_tracking_id:
                    cur.execute("""
                        UPDATE gdrive_file_tracking
                        SET is_latest_version = FALSE
                        WHERE tracking_id = %s
                    """, (previous_tracking_id,))
                    
                    # Get version number
                    cur.execute("""
                        SELECT version_number FROM gdrive_file_tracking
                        WHERE tracking_id = %s
                    """, (previous_tracking_id,))
                    
                    prev_version = cur.fetchone()[0]
                    new_version = prev_version + 1
                else:
                    new_version = 1
                
                # Insert new tracking record
                cur.execute("""
                    INSERT INTO gdrive_file_tracking (
                        gdrive_file_id, file_name, file_path, folder_structure,
                        file_hash, file_size_bytes, file_modified_at,
                        processing_status, version_number, previous_version_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (gdrive_file_id, file_hash) DO UPDATE SET
                        last_checked_at = NOW(),
                        file_path = EXCLUDED.file_path,
                        folder_structure = EXCLUDED.folder_structure
                    RETURNING tracking_id
                """, (
                    gdrive_file_id, file_name, file_path, folder_structure,
                    file_hash, file_size, file_modified,
                    ProcessingStatus.PENDING, new_version, previous_tracking_id
                ))
                
                tracking_id = str(cur.fetchone()[0])
                conn.commit()
                
                return tracking_id
    
    except Exception as e:
        logger.error(f"Error creating tracking record: {e}")
        raise

def update_processing_status(
    tracking_id: str,
    status: ProcessingStatus,
    tender_id: str = None,
    error_message: str = None,
    increment_retry: bool = False
):
    """Update processing status of file"""
    
    try:
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                if increment_retry:
                    cur.execute("""
                        UPDATE gdrive_file_tracking
                        SET processing_status = %s,
                            retry_count = retry_count + 1,
                            last_retry_at = NOW(),
                            last_error = %s,
                            last_checked_at = NOW(),
                            tender_id = COALESCE(%s, tender_id)
                        WHERE tracking_id = %s
                    """, (status, error_message, tender_id, tracking_id))
                else:
                    if status == ProcessingStatus.COMPLETED:
                        cur.execute("""
                            UPDATE gdrive_file_tracking
                            SET processing_status = %s,
                                tender_id = %s,
                                successfully_processed_at = NOW(),
                                last_checked_at = NOW(),
                                last_error = NULL
                            WHERE tracking_id = %s
                        """, (status, tender_id, tracking_id))
                    else:
                        cur.execute("""
                            UPDATE gdrive_file_tracking
                            SET processing_status = %s,
                                last_error = %s,
                                last_checked_at = NOW(),
                                tender_id = COALESCE(%s, tender_id)
                            WHERE tracking_id = %s
                        """, (status, error_message, tender_id, tracking_id))
                
                conn.commit()
    
    except Exception as e:
        logger.error(f"Error updating processing status: {e}")

# ============================================================================
# FILE TRACKING WITH RETRY LOGIC
# ============================================================================

def should_process_file(gdrive_file_id: str, file_hash: str) -> Dict:
    """Determine if file should be processed"""
    try:
        conn = safe_db_connect()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT gdrive_file_id, status, retry_count, should_retry
            FROM gdrive_file_tracking
            WHERE gdrive_file_id = %s AND file_hash = %s
        """, (gdrive_file_id, file_hash))
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            return {'should_process': True, 'reason': 'new_file'}
        
        file_id, status, retry_count, should_retry = result
        
        if status == 'processed':
            return {'should_process': False, 'reason': 'already_processed'}
        
        if status == 'failed' and should_retry and retry_count < MAX_RETRIES:
            return {
                'should_process': True,
                'reason': 'retry',
                'retry_count': retry_count
            }
        
        if status == 'failed' and retry_count >= MAX_RETRIES:
            return {'should_process': False, 'reason': 'max_retries_reached'}
        
        return {'should_process': True, 'reason': 'pending'}
        
    except Exception as e:
        logger.error(f"Error checking file status: {e}")
        return {'should_process': True, 'reason': 'error_checking'}
def update_processing_status(
    tracking_id: str,
    status: ProcessingStatus,
    tender_id: str = None,
    error_message: str = None,
    increment_retry: bool = False
):
    """Update processing status of file"""
    
    try:
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                if increment_retry:
                    cur.execute("""
                        UPDATE gdrive_file_tracking
                        SET processing_status = %s,
                            retry_count = retry_count + 1,
                            last_retry_at = NOW(),
                            last_error = %s,
                            last_checked_at = NOW(),
                            tender_id = COALESCE(%s, tender_id)
                        WHERE tracking_id = %s
                    """, (status, error_message, tender_id, tracking_id))
                else:
                    if status == ProcessingStatus.COMPLETED:
                        cur.execute("""
                            UPDATE gdrive_file_tracking
                            SET processing_status = %s,
                                tender_id = %s,
                                successfully_processed_at = NOW(),
                                last_checked_at = NOW(),
                                last_error = NULL
                            WHERE tracking_id = %s
                        """, (status, tender_id, tracking_id))
                    else:
                        cur.execute("""
                            UPDATE gdrive_file_tracking
                            SET processing_status = %s,
                                last_error = %s,
                                last_checked_at = NOW(),
                                tender_id = COALESCE(%s, tender_id)
                            WHERE tracking_id = %s
                        """, (status, error_message, tender_id, tracking_id))
                
                conn.commit()
    
    except Exception as e:
        logger.error(f"Error updating processing status: {e}")
def mark_file_processing(
    gdrive_file_id: str,
    file_name: str,
    file_path: str,
    file_hash: str,
    file_modified: datetime,
    status: str,
    tender_id: int = None,
    error_message: str = None
):
    """Mark file processing status"""
    try:
        conn = safe_db_connect()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT gdrive_file_id, retry_count FROM gdrive_file_tracking
            WHERE gdrive_file_id = %s AND file_hash = %s
        """, (gdrive_file_id, file_hash))
        
        existing = cur.fetchone()
        
        if existing:
            file_id, current_retry_count = existing
            new_retry_count = current_retry_count + 1 if status == 'failed' else current_retry_count
            should_retry = (status == 'failed' and new_retry_count < MAX_RETRIES and RETRY_FAILED_FILES)
            
            cur.execute("""
                UPDATE gdrive_file_tracking
                SET status = %s,
                    tender_id = COALESCE(%s, tender_id),
                    error_message = %s,
                    retry_count = %s,
                    last_retry_at = NOW(),
                    should_retry = %s,
                    processed_at = CASE WHEN %s = 'processed' THEN NOW() ELSE processed_at END
                WHERE gdrive_file_id = %s
            """, (status, tender_id, error_message, new_retry_count, should_retry, status, file_id))
        else:
            should_retry = (status == 'failed' and RETRY_FAILED_FILES)
            
            cur.execute("""
                INSERT INTO gdrive_file_tracking 
                (gdrive_file_id, file_name, file_path, file_hash, file_modified, 
                 tender_id, status, error_message, retry_count, should_retry)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s)
            """, (gdrive_file_id, file_name, file_path, file_hash, file_modified,
                  tender_id, status, error_message, should_retry))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"File status updated: {status} - {file_name}")
        
    except Exception as e:
        logger.error(f"Error updating file status: {e}")

# ============================================================================
# GOOGLE DRIVE OPERATIONS
# ============================================================================

def connect_to_google_drive():
    """Connect to Google Drive"""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=credentials)
        service.files().list(pageSize=1).execute()
        logger.info("OK Connected to Google Drive")
        return service
    except Exception as e:
        logger.error(f"Google Drive connection failed: {e}")
        raise

def get_all_pdf_files(service, folder_id: str, path_prefix: str = "") -> List[Dict]:
    """Recursively get all PDF files"""
    all_files = []
    
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, modifiedTime, size, md5Checksum)",
            pageSize=1000
        ).execute()
        
        items = results.get('files', [])
        
        for item in items:
            current_path = f"{path_prefix}/{item['name']}" if path_prefix else item['name']
            
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                logger.debug(f"Scanning subfolder: {current_path}")
                subfolder_files = get_all_pdf_files(service, item['id'], current_path)
                all_files.extend(subfolder_files)
            
            elif item['name'].lower().endswith('.pdf'):
                all_files.append({
                    'file_id': item['id'],
                    'file_name': item['name'],
                    'file_path': current_path,
                    'file_modified': item.get('modifiedTime'),
                    'file_size': int(item.get('size', 0)),
                    'md5_checksum': item.get('md5Checksum', '')
                })
        
        return all_files
        
    except Exception as e:
        logger.error(f"Error scanning folder: {e}")
        return []

def download_file_from_gdrive(service, file_id: str, local_path: Path) -> bool:
    """Download file from Google Drive"""
    try:
        request = service.files().get_media(fileId=file_id)
        
        with open(local_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        
        logger.info(f"OK Downloaded: {local_path.name}")
        return True
        
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False
# ============================================================================
# GOOGLE DRIVE FILE OPERATIONS
# ============================================================================

def get_folder_path(service, file_id: str, root_id: str) -> str:
    """Get full folder path for a file"""
    
    try:
        path_parts = []
        current_id = file_id
        
        while current_id and current_id != root_id:
            file = service.files().get(
                fileId=current_id,
                fields='name, parents'
            ).execute()
            
            path_parts.insert(0, file['name'])
            
            parents = file.get('parents', [])
            if not parents:
                break
            
            current_id = parents[0]
        
        return '/'.join(path_parts)
    
    except Exception as e:
        logger.warning(f"Could not determine full path: {e}")
        return ""

def scan_gdrive_folder(service, folder_id: str, path_prefix: str = "") -> List[Dict]:
    """Recursively scan Google Drive folder for PDF files"""
    
    all_files = []
    
    try:
        query = f"'{folder_id}' in parents and trashed=false"
        page_token = None
        
        while True:
            results = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, parents)",
                pageSize=1000,
                pageToken=page_token
            ).execute()
            
            items = results.get('files', [])
            
            for item in items:
                current_path = f"{path_prefix}/{item['name']}" if path_prefix else item['name']
                
                # Recurse into folders
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    logger.info(f"Scanning subfolder: {current_path}")
                    subfolder_files = scan_gdrive_folder(service, item['id'], current_path)
                    all_files.extend(subfolder_files)
                
                # Collect PDF files
                elif item['name'].lower().endswith('.pdf'):
                    all_files.append({
                        'file_id': item['id'],
                        'file_name': item['name'],
                        'file_path': current_path,
                        'folder_structure': path_prefix,
                        'file_modified': item.get('modifiedTime'),
                        'file_size': int(item.get('size', 0)),
                        'parent_folders': item.get('parents', [])
                    })
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        
        return all_files
    
    except HttpError as e:
        logger.error(f"Google Drive API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error scanning folder: {e}")
        return []

def download_file_from_gdrive(service, file_id: str, local_path: Path) -> bool:
    """Download file from Google Drive with retry logic"""
    
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            request = service.files().get_media(fileId=file_id)
            
            with open(local_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"Download {int(status.progress() * 100)}%")
            
            logger.info(f"Downloaded: {local_path.name}")
            return True
        
        except HttpError as e:
            if e.resp.status in [403, 429]:  # Rate limit
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
            logger.error(f"Download failed: {e}")
            return False
        
        except Exception as e:
            logger.error(f"Download error: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False
    
    return False


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TenderMetadata(BaseModel):
    tender_reference_number: str
    issuing_authority: Optional[str] = None
    submission_deadline: Optional[str] = None
    clarification_date: Optional[str] = None
    site_location: Optional[str] = None
    contract_type: Optional[str] = None

class QualificationCriteria(BaseModel):
    criteria_type: str
    criteria_description: str

class RequiredDocument(BaseModel):
    document_name: str
    is_mandatory: bool = True

# ============================================================================
# PDF PROCESSING
# ============================================================================

def extract_text_from_pdf(pdf_path: Path) -> Dict:
    """Extract text from PDF with error handling"""
    
    try:
        doc = fitz.open(str(pdf_path))
        pages_content = []
        full_text = ""
        
        for page_num, page in enumerate(doc, 1):
            text = page.get_text()
            pages_content.append({
                "page_number": page_num,
                "text": text
            })
            full_text += f"\n\n--- Page {page_num} ---\n\n{text}"
        
        doc.close()
        
        return {
            "full_text": full_text,
            "pages": pages_content,
            "total_pages": len(pages_content),
            "success": True
        }
    
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return {
            "full_text": "",
            "pages": [],
            "total_pages": 0,
            "success": False,
            "error": str(e)
        }

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks"""
    
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk.strip()) > 100:
            chunks.append(chunk)
    
    return chunks

# ============================================================================
# LLM EXTRACTION FUNCTIONS
# ============================================================================

def clean_json_response(text: str) -> str:
    """Clean LLM response to extract JSON"""
    
    text = text.strip()
    
    # Remove markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    
    if text.endswith("```"):
        text = text[:-3]
    
    return text.strip()

def call_llm(prompt: str, system_message: str, max_tokens: int = 1500, temperature: float = 0.1) -> Optional[str]:
    """Call LLM with error handling and retry logic"""
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            logger.error(f"LLM call failed after {max_retries} attempts")
            return None
    
    return None

def extract_tender_metadata(text: str) -> Optional[TenderMetadata]:
    """Extract tender metadata using LLM"""
    
    prompt = f"""Extract tender information from this document.

Required fields:
- tender_reference_number: Tender reference/ID
- issuing_authority: Organization issuing tender
- submission_deadline: Deadline date/time
- clarification_date: Last date for clarifications
- site_location: Project location
- contract_type: Contract type (PSSCOC/Lump Sum/etc.)

Return ONLY valid JSON. Use null for missing fields.

Document (first 8000 chars):
{text[:8000]}

JSON Response:"""
    
    try:
        result = call_llm(
            prompt,
            "You are a tender document analyzer. Return valid JSON only.",
            max_tokens=1000
        )
        
        if not result:
            return None
        
        result = clean_json_response(result)
        metadata_dict = json.loads(result)
        
        return TenderMetadata(**metadata_dict)
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in metadata extraction: {e}")
        return None
    except Exception as e:
        logger.error(f"Metadata extraction error: {e}")
        return None

def extract_qualification_criteria(text: str) -> List[QualificationCriteria]:
    """Extract qualification criteria"""
    
    prompt = f"""Extract ALL eligibility and qualification criteria.

Focus on:
- License requirements (BCA grades, registrations)
- Financial requirements (turnover, capital)
- Experience requirements (projects, years)
- Technical requirements (equipment, manpower)

Return JSON array:
[{{"criteria_type": "license/financial/experience/technical", "criteria_description": "description"}}]

Document (first 10000 chars):
{text[:10000]}

JSON Array:"""
    
    try:
        result = call_llm(
            prompt,
            "You are a tender analyzer. Return valid JSON array only.",
            max_tokens=1500
        )
        
        if not result:
            return []
        
        result = clean_json_response(result)
        criteria_list = json.loads(result)
        
        return [QualificationCriteria(**c) for c in criteria_list]
    
    except Exception as e:
        logger.error(f"Criteria extraction error: {e}")
        return []

def extract_required_documents(text: str) -> List[RequiredDocument]:
    """Extract required documents list"""
    
    prompt = f"""Extract list of required documents for submission.

Return JSON array:
[{{"document_name": "name", "is_mandatory": true/false}}]

Document (first 8000 chars):
{text[:8000]}

JSON Array:"""
    
    try:
        result = call_llm(
            prompt,
            "Return valid JSON array only.",
            max_tokens=1000
        )
        
        if not result:
            return []
        
        result = clean_json_response(result)
        docs_list = json.loads(result)
        
        return [RequiredDocument(**d) for d in docs_list]
    
    except Exception as e:
        logger.error(f"Required documents extraction error: {e}")
        return []

def detect_document_type(file_name: str, text: str) -> DocumentType:
    """Detect document type from filename and content"""
    
    name_lower = file_name.lower()
    
    if 'addendum' in name_lower or 'addenda' in name_lower:
        return DocumentType.ADDENDUM
    elif 'clarification' in name_lower:
        return DocumentType.CLARIFICATION
    elif 'drawing' in name_lower or 'dwg' in name_lower:
        return DocumentType.DRAWING
    elif 'specification' in name_lower or 'spec' in name_lower:
        return DocumentType.SPECIFICATION
    elif 'boq' in name_lower or 'bill of quantities' in name_lower:
        return DocumentType.BOQ
    elif 'itt' in name_lower or 'invitation' in name_lower:
        return DocumentType.ITT
    
    # Content-based detection
    text_lower = text[:2000].lower()
    if 'invitation to tender' in text_lower:
        return DocumentType.ITT
    
    return DocumentType.OTHER

# ============================================================================
# VECTOR EMBEDDINGS
# ============================================================================

def create_embeddings_batch(texts: List[str], batch_size: int = 32) -> List[List[float]]:
    """Generate embeddings in batches"""
    
    try:
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            embeddings = embedding_model.encode(batch, show_progress_bar=False)
            all_embeddings.extend(embeddings.tolist())
        
        return all_embeddings
    
    except Exception as e:
        logger.error(f"Embedding generation error: {e}")
        return []

# ============================================================================
# MAIN PROCESSING PIPELINE
# ============================================================================

def process_tender_document(
    local_pdf_path: Path,
    tracking_id: str,
    gdrive_metadata: Dict
) -> Optional[str]:
    """
    Main processing pipeline with comprehensive error handling
    
    Returns:
        tender_id if successful, None otherwise
    """
    
    start_time = datetime.now()
    tender_id = None
    
    logger.info(f"Processing: {gdrive_metadata['file_name']}")
    logger.info(f"Path: {gdrive_metadata['file_path']}")
    logger.info(f"Tracking ID: {tracking_id}")
    
    try:
        # Update status to processing
        update_processing_status(tracking_id, ProcessingStatus.PROCESSING)
        
        # Log processing start
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO processing_log (
                        tracking_id, stage, status, started_at
                    ) VALUES (%s, %s, %s, %s)
                    RETURNING log_id
                """, (tracking_id, 'document_processing', 'started', start_time))
                
                log_id = str(cur.fetchone()[0])
                conn.commit()
        
        # Step 1: Extract PDF text
        logger.info("Step 1: Extracting PDF text...")
        pdf_content = extract_text_from_pdf(local_pdf_path)
        
        if not pdf_content['success']:
            raise Exception(f"PDF extraction failed: {pdf_content.get('error', 'Unknown error')}")
        
        full_text = pdf_content['full_text']
        total_pages = pdf_content['total_pages']
        
        logger.info(f"Extracted {len(full_text)} chars from {total_pages} pages")
        
        if len(full_text.strip()) < 100:
            raise Exception("PDF appears to be empty or unreadable")
        
        # Step 2: Extract metadata
        logger.info("Step 2: Extracting tender metadata...")
        metadata = extract_tender_metadata(full_text)
        
        if not metadata:
            raise Exception("Failed to extract tender metadata")
        
        logger.info(f"Reference: {metadata.tender_reference_number}")
        
        # Step 3: Detect document type
        doc_type = detect_document_type(gdrive_metadata['file_name'], full_text)
        logger.info(f"Document type: {doc_type}")
        
        # Step 4: Store/update tender
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                logger.info("Step 3: Storing tender data...")
                
                # Check if tender exists
                cur.execute("""
                    SELECT tender_id FROM tenders
                    WHERE tender_reference_number = %s
                """, (metadata.tender_reference_number,))
                
                existing = cur.fetchone()
                
                if existing:
                    tender_id = str(existing[0])
                    logger.info(f"Updating existing tender: {tender_id}")
                    
                    cur.execute("""
                        UPDATE tenders SET
                            issuing_authority = COALESCE(%s, issuing_authority),
                            submission_deadline = COALESCE(%s, submission_deadline),
                            clarification_date = COALESCE(%s, clarification_date),
                            site_location = COALESCE(%s, site_location),
                            contract_type = COALESCE(%s, contract_type),
                            updated_at = NOW(),
                            last_processed_at = NOW()
                        WHERE tender_id = %s
                    """, (
                        metadata.issuing_authority,
                        metadata.submission_deadline,
                        metadata.clarification_date,
                        metadata.site_location,
                        metadata.contract_type,
                        tender_id
                    ))
                else:
                    logger.info("Creating new tender...")
                    
                    cur.execute("""
                        INSERT INTO tenders (
                            tender_reference_number, issuing_authority,
                            submission_deadline, clarification_date,
                            site_location, contract_type, last_processed_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        RETURNING tender_id
                    """, (
                        metadata.tender_reference_number,
                        metadata.issuing_authority,
                        metadata.submission_deadline,
                        metadata.clarification_date,
                        metadata.site_location,
                        metadata.contract_type
                    ))
                    
                    tender_id = str(cur.fetchone()[0])
                    logger.info(f"Created tender: {tender_id}")
                
                # Step 5: Store document record
                file_hash = calculate_file_hash(local_pdf_path)
                
                cur.execute("""
                    INSERT INTO tender_documents (
                        tender_id, tracking_id, document_name,
                        document_type, file_hash, version_number
                    ) VALUES (%s, %s, %s, %s, %s, (
                        SELECT COALESCE(MAX(version_number), 0) + 1
                        FROM tender_documents
                        WHERE tender_id = %s AND document_name = %s
                    ))
                    RETURNING doc_id
                """, (
                    tender_id, tracking_id, gdrive_metadata['file_name'],
                    doc_type, file_hash, tender_id, gdrive_metadata['file_name']
                ))
                
                doc_id = str(cur.fetchone()[0])
                
                # Mark previous versions as superseded
                cur.execute("""
                    UPDATE tender_documents
                    SET is_current_version = FALSE,
                        superseded_by = %s,
                        superseded_at = NOW()
                    WHERE tender_id = %s
                      AND document_name = %s
                      AND doc_id != %s
                      AND is_current_version = TRUE
                """, (doc_id, tender_id, gdrive_metadata['file_name'], doc_id))
                
                conn.commit()
        
        # Step 6: Extract qualification criteria
        logger.info("Step 4: Extracting qualification criteria...")
        criteria_list = extract_qualification_criteria(full_text)
        logger.info(f"Found {len(criteria_list)} criteria")
        
        if criteria_list:
            with DatabaseConnection() as conn:
                with conn.cursor() as cur:
                    execute_batch(cur, """
                        INSERT INTO tender_qualification_criteria (
                            tender_id, criteria_type, criteria_description
                        ) VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, [
                        (tender_id, c.criteria_type, c.criteria_description)
                        for c in criteria_list
                    ])
                    conn.commit()
        
        # Step 7: Extract required documents
        logger.info("Step 5: Extracting required documents...")
        required_docs = extract_required_documents(full_text)
        logger.info(f"Found {len(required_docs)} required documents")
        
        if required_docs:
            with DatabaseConnection() as conn:
                with conn.cursor() as cur:
                    execute_batch(cur, """
                        INSERT INTO tender_required_documents (
                            tender_id, document_name, is_mandatory
                        ) VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, [
                        (tender_id, d.document_name, d.is_mandatory)
                        for d in required_docs
                    ])
                    conn.commit()
        
        # Step 8: Create embeddings
        logger.info("Step 6: Creating embeddings...")
        chunks = chunk_text(full_text)
        logger.info(f"Created {len(chunks)} chunks")
        
        if chunks:
            embeddings = create_embeddings_batch(chunks)
            
            if embeddings:
                logger.info(f"Generated {len(embeddings)} embeddings")
                
                with DatabaseConnection() as conn:
                    with conn.cursor() as cur:
                        execute_batch(cur, """
                            INSERT INTO tender_document_chunks (
                                tender_id, doc_id, tracking_id,
                                chunk_text, chunk_index, embedding
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """, [
                            (tender_id, doc_id, tracking_id, chunk, idx, emb)
                            for idx, (chunk, emb) in enumerate(zip(chunks, embeddings))
                        ])
                        conn.commit()
        
        # Step 9: Complete processing
        duration = (datetime.now() - start_time).total_seconds()
        
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                # Update processing log
                cur.execute("""
                    UPDATE processing_log
                    SET status = 'completed',
                        completed_at = NOW(),
                        duration_seconds = %s,
                        message = %s
                    WHERE log_id = %s
                """, (
                    duration,
                    f"Successfully processed {total_pages} pages, {len(chunks)} chunks",
                    log_id
                ))
                
                conn.commit()
        
        # Update tracking status
        update_processing_status(tracking_id, ProcessingStatus.COMPLETED, tender_id)
        
        logger.info(f"Processing completed in {duration:.2f}s")
        logger.info(f"Tender ID: {tender_id}")
        
        return tender_id
    
    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        # Log error
        try:
            with DatabaseConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE processing_log
                        SET status = 'failed',
                            completed_at = NOW(),
                            error_details = %s
                        WHERE log_id = %s
                    """, (traceback.format_exc(), log_id))
                    conn.commit()
        except:
            pass
        
        # Update tracking status
        update_processing_status(
            tracking_id,
            ProcessingStatus.FAILED,
            tender_id,
            error_msg,
            increment_retry=True
        )
        
        return None

# ============================================================================
# MONITORING LOOP
# ============================================================================

def monitor_google_drive():
    """Main monitoring loop"""
    
    logger.info("="*80)
    logger.info("GOOGLE DRIVE TENDER MONITOR v2.0")
    logger.info("="*80)
    logger.info(f"Folder ID: {GOOGLE_DRIVE_FOLDER_ID}")
    logger.info(f"Polling Interval: {POLLING_INTERVAL}s")
    logger.info(f"Max Retries: {MAX_RETRY_ATTEMPTS}")
    logger.info("="*80)
    
    # Setup
    setup_database()
    service = connect_to_google_drive()
    
    logger.info(f"Monitoring started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("Press Ctrl+C to stop")
    logger.info("-"*80)
    
    try:
        while True:
            logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning Google Drive...")
            
            # Scan for files
            all_files = scan_gdrive_folder(service, GOOGLE_DRIVE_FOLDER_ID)
            logger.info(f"Found {len(all_files)} PDF files total")
            
            # Process each file
            processed_count = 0
            skipped_count = 0
            error_count = 0
            
            for file_info in all_files:
                try:
                    # Download file temporarily to calculate hash
                    temp_filename = f"temp_{file_info['file_id']}.pdf"
                    temp_path = LOCAL_DOWNLOAD_DIR / temp_filename
                    
                    if download_file_from_gdrive(service, file_info['file_id'], temp_path):
                        file_hash = calculate_file_hash(temp_path)
                        
                        # Check if should process
                        should_process, reason, prev_tracking_id = should_process_file(
                            file_info['file_id'],
                            file_hash
                        )
                        
                        if should_process:
                            logger.info(f"\n📄 Processing: {file_info['file_path']}")
                            logger.info(f"   Reason: {reason}")
                            
                            # Create/update tracking
                            tracking_id = create_or_update_tracking(
                                gdrive_file_id=file_info['file_id'],
                                file_name=file_info['file_name'],
                                file_path=file_info['file_path'],
                                folder_structure=file_info.get('folder_structure', ''),
                                file_hash=file_hash,
                                file_size=file_info['file_size'],
                                file_modified=datetime.fromisoformat(
                                    file_info['file_modified'].replace('Z', '+00:00')
                                ),
                                previous_tracking_id=prev_tracking_id if reason == "new_version" else None
                            )
                            
                            # Process document
                            tender_id = process_tender_document(
                                temp_path,
                                tracking_id,
                                file_info
                            )
                            
                            if tender_id:
                                logger.info(f"✅ Success: Tender {tender_id}")
                                processed_count += 1
                            else:
                                logger.error(f"❌ Failed: {file_info['file_name']}")
                                error_count += 1
                        else:
                            logger.debug(f"⏭️  Skipped: {file_info['file_path']} ({reason})")
                            skipped_count += 1
                        
                        # Clean up temp file
                        if temp_path.exists():
                            temp_path.unlink()
                    
                except Exception as e:
                    logger.error(f"Error processing {file_info.get('file_name', 'unknown')}: {e}")
                    error_count += 1
            
            logger.info(f"\n{'='*80}")
            logger.info(f"Scan complete: {processed_count} processed, {skipped_count} skipped, {error_count} errors")
            logger.info(f"Next scan in {POLLING_INTERVAL}s")
            logger.info(f"{'='*80}\n")
            
            time.sleep(POLLING_INTERVAL)
    
    except KeyboardInterrupt:
        logger.info("\n" + "="*80)
        logger.info("Monitoring stopped by user")
        logger.info("="*80)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        logger.error(traceback.format_exc())
        raise

# ============================================================================
# MANUAL PROCESSING FUNCTIONS
# ============================================================================

def process_specific_file(file_name: str):
    """Manually process a specific file"""
    
    service = connect_to_google_drive()
    
    try:
        # Search for file
        query = f"name='{file_name}' and trashed=false"
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, modifiedTime, size, parents)"
        ).execute()
        
        files = results.get('files', [])
        
        if not files:
            logger.error(f"File not found: {file_name}")
            return
        
        file = files[0]
        
        # Download
        local_path = LOCAL_DOWNLOAD_DIR / file_name
        
        if not download_file_from_gdrive(service, file['id'], local_path):
            logger.error("Download failed")
            return
        
        # Calculate hash and create tracking
        file_hash = calculate_file_hash(local_path)
        
        tracking_id = create_or_update_tracking(
            gdrive_file_id=file['id'],
            file_name=file['name'],
            file_path=file['name'],
            folder_structure='',
            file_hash=file_hash,
            file_size=int(file.get('size', 0)),
            file_modified=datetime.fromisoformat(file.get('modifiedTime', '').replace('Z', '+00:00'))
        )
        
        # Process
        file_info = {
            'file_id': file['id'],
            'file_name': file['name'],
            'file_path': file['name'],
            'file_size': int(file.get('size', 0)),
            'file_modified': file.get('modifiedTime')
        }
        
        tender_id = process_tender_document(local_path, tracking_id, file_info)
        
        if tender_id:
            logger.info(f"\n✅ Successfully processed: {file_name}")
            logger.info(f"   Tender ID: {tender_id}")
        else:
            logger.error(f"\n❌ Failed to process: {file_name}")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())

def retry_failed_files():
    """Retry all failed files that haven't exceeded max retries"""
    
    try:
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tracking_id, gdrive_file_id, file_name, file_path
                    FROM gdrive_file_tracking
                    WHERE processing_status = %s
                      AND retry_count < %s
                      AND (last_retry_at IS NULL OR last_retry_at < NOW() - INTERVAL '%s minutes')
                """, (ProcessingStatus.FAILED, MAX_RETRY_ATTEMPTS, RETRY_DELAY_MINUTES))
                
                failed_files = cur.fetchall()
        
        logger.info(f"Found {len(failed_files)} files to retry")
        
        service = connect_to_google_drive()
        
        for tracking_id, gdrive_file_id, file_name, file_path in failed_files:
            logger.info(f"\nRetrying: {file_path}")
            
            try:
                # Download file
                local_path = LOCAL_DOWNLOAD_DIR / f"retry_{file_name}"
                
                if download_file_from_gdrive(service, gdrive_file_id, local_path):
                    file_info = {
                        'file_id': gdrive_file_id,
                        'file_name': file_name,
                        'file_path': file_path,
                        'file_size': local_path.stat().st_size,
                        'file_modified': datetime.now().isoformat()
                    }
                    
                    tender_id = process_tender_document(local_path, str(tracking_id), file_info)
                    
                    if tender_id:
                        logger.info(f"✅ Retry successful: {tender_id}")
                    else:
                        logger.error(f"❌ Retry failed: {file_name}")
                    
                    # Clean up
                    if local_path.exists():
                        local_path.unlink()
            
            except Exception as e:
                logger.error(f"Error retrying {file_name}: {e}")
    
    except Exception as e:
        logger.error(f"Error in retry process: {e}")

def show_statistics():
    """Show processing statistics"""
    
    try:
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                # File statistics
                cur.execute("""
                    SELECT 
                        processing_status,
                        COUNT(*) as count,
                        AVG(retry_count) as avg_retries
                    FROM gdrive_file_tracking
                    GROUP BY processing_status
                    ORDER BY processing_status
                """)
                
                file_stats = cur.fetchall()
                
                # Tender statistics
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(DISTINCT tender_reference_number) as unique_tenders,
                        AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_proc_time
                    FROM tenders
                """)
                
                tender_stats = cur.fetchone()
                
                # Recent activity
                cur.execute("""
                    SELECT 
                        t.tender_reference_number,
                        t.issuing_authority,
                        ft.file_name,
                        ft.successfully_processed_at
                    FROM gdrive_file_tracking ft
                    JOIN tenders t ON ft.tender_id = t.tender_id
                    WHERE ft.processing_status = 'completed'
                    ORDER BY ft.successfully_processed_at DESC
                    LIMIT 10
                """)
                
                recent = cur.fetchall()
        
        print("\n" + "="*80)
        print("PROCESSING STATISTICS")
        print("="*80)
        
        print("\nFile Processing Status:")
        print("-"*80)
        for status, count, avg_retry in file_stats:
            print(f"{status:20s}: {count:5d} files (avg retries: {avg_retry:.1f})")
        
        print("\nTender Statistics:")
        print("-"*80)
        print(f"Total tender records: {tender_stats[0]}")
        print(f"Unique tenders: {tender_stats[1]}")
        if tender_stats[2]:
            print(f"Avg processing time: {tender_stats[2]:.1f}s")
        
        print("\nRecent Successful Processing:")
        print("-"*80)
        for ref, auth, fname, proc_time in recent:
            print(f"{ref}: {fname[:40]}")
            print(f"  {auth} | {proc_time.strftime('%Y-%m-%d %H:%M')}")
        
        print("\n" + "="*80 + "\n")
    
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
# ====================================================================
# RAG / SEARCH
# ====================================================================
def vector_similarity_search(query: str, tender_id: str = None, top_k: int = 5) -> List[Dict]:
    try:
        query_embedding = embedding_model.encode([query])[0].tolist()
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                if tender_id:
                    cur.execute("""
                        SELECT chunk_text, document_name, page_number, 1 - (embedding <=> %s::vector) as similarity_score, t.tender_reference_number
                        FROM tender_document_chunks tdc
                        JOIN tenders t ON tdc.tender_id = t.tender_id
                        WHERE tdc.tender_id = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, (query_embedding, tender_id, query_embedding, top_k))
                else:
                    cur.execute("""
                        SELECT chunk_text, document_name, page_number, 1 - (embedding <=> %s::vector) as similarity_score, t.tender_reference_number
                        FROM tender_document_chunks tdc
                        JOIN tenders t ON tdc.tender_id = t.tender_id
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, (query_embedding, query_embedding, top_k))
                results = []
                for row in cur.fetchall():
                    results.append({
                        "text": row[0],
                        "document": row[1],
                        "page": row[2],
                        "similarity": float(row[3]),
                        "tender_ref": row[4]
                    })
                return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

def answer_question_with_rag(question: str, tender_id: str = None) -> str:
    context_chunks = vector_similarity_search(question, tender_id, top_k=5)
    if not context_chunks:
        return "No relevant information found."
    context_text = "\n\n".join([f"[{chunk['document']}, Page {chunk['page']}]\n{chunk['text']}" for chunk in context_chunks])
    prompt = f"""
Answer the question based on the tender document context below.

Context:
{context_text}

Question: {question}

Provide a clear, accurate answer. If unsure, say so.
"""
    try:
        response = openai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "You are a tender document Q&A assistant."}, {"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating answer: {e}"

# ====================================================================
# REPORTING
# ====================================================================
def get_tender_summary(tender_id: str) -> Optional[Dict]:
    try:
        with DatabaseConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tender_id, tender_reference_number, issuing_authority,
                           submission_deadline, clarification_date, site_location,
                           contract_type, created_at
                    FROM tenders WHERE tender_id = %s
                """, (tender_id,))
                tender = cur.fetchone()
                if not tender:
                    return None
                cur.execute("""
                    SELECT criteria_type, criteria_description, is_met, notes
                    FROM tender_qualification_criteria WHERE tender_id = %s
                """, (tender_id,))
                criteria = [{"type": r[0], "description": r[1], "is_met": r[2], "notes": r[3]} for r in cur.fetchall()]
                cur.execute("""
                    SELECT document_name, is_mandatory, is_received FROM tender_required_documents WHERE tender_id = %s
                """, (tender_id,))
                required_docs = [{"name": r[0], "mandatory": r[1], "received": r[2]} for r in cur.fetchall()]
                cur.execute("""
                    SELECT document_name, file_path, received_date, file_size_kb FROM tender_received_documents WHERE tender_id = %s
                """, (tender_id,))
                received_docs = [{"name": r[0], "path": r[1], "received": str(r[2]), "size_kb": r[3]} for r in cur.fetchall()]
        return {
            "tender_id": str(tender[0]),
            "reference_number": tender[1],
            "issuing_authority": tender[2],
            "submission_deadline": str(tender[3]) if tender[3] else None,
            "clarification_date": str(tender[4]) if tender[4] else None,
            "site_location": tender[5],
            "contract_type": tender[6],
            "created_at": str(tender[7]),
            "qualification_criteria": criteria,
            "required_documents": required_docs,
            "received_documents": received_docs
        }
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        return None

def print_tender_report(tender_id: str):
    summary = get_tender_summary(tender_id)
    if not summary:
        print(f"Tender {tender_id} not found!")
        return
    print(f"\n{'='*80}\nTENDER OVERVIEW REPORT\n{'='*80}\n")
    print(f"Reference: {summary['reference_number']}")
    print(f"Authority: {summary['issuing_authority']}")
    print(f"Submission Deadline: {summary['submission_deadline']}")
    print(f"Site Location: {summary['site_location']}")
    print(f"Contract Type: {summary['contract_type']}\n{'-'*80}\n")
    print("QUALIFICATION CRITERIA:")
    for idx, crit in enumerate(summary['qualification_criteria'], 1):
        status = "MET" if crit.get('is_met') else "? UNCHECKED"
        print(f"  {idx}. [{status}] {crit['type']}\n     {crit['description']}\n")
    print(f"{'-'*80}\nREQUIRED DOCUMENTS:")
    for doc in summary['required_documents']:
        status = "OK" if doc['received'] else "Not Received"
        mandatory = "[MANDATORY]" if doc['mandatory'] else "[OPTIONAL]"
        print(f"  {status} {doc['name']} {mandatory}")
    print(f"\n{'-'*80}\nRECEIVED DOCUMENTS:")
    for doc in summary['received_documents']:
        print(f"  • {doc['name']}\n    Path: {doc['path']}\n    Size: {doc['size_kb']} KB\n")
    print(f"{'='*80}\n")

# ====================================================================
# MAIN
# ====================================================================
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "setup":
            setup_database()
            print("Database setup complete")
        elif command == "monitor":
            monitor_google_drive()
        elif command == "list":
            try:
                service = connect_to_google_drive()
                files = scan_gdrive_folder(service, GOOGLE_DRIVE_FOLDER_ID)
                for f in files:
                    print(f"{f['file_path']} ({f['gdrive_file_id']})")
            except Exception as e:
                logger.error(f"Error listing files: {e}")
        elif command == "process" and len(sys.argv) > 2:
            process_specific_file(sys.argv[2])
        elif command == "retry":
            retry_failed_files()
        elif command == "stats":
            show_statistics()
        elif command == "report" and len(sys.argv) > 2:
            print_tender_report(sys.argv[2])
        elif command == "query" and len(sys.argv) > 2:
            if len(sys.argv) > 3:
                tender_id = sys.argv[2]
                question = " ".join(sys.argv[3:])
                print(answer_question_with_rag(question, tender_id))
            else:
                print("Usage: query <tender_id> <question>")
        elif command == "test":
            try:
                service = connect_to_google_drive()
                print("Google Drive connection successful")
            except Exception as e:
                print(f"Connection failed: {e}")
        else:
            print("Unknown command")
    else:
        print("\nUsage:")
        print("  python docparser.py setup")
        print("  python docparser.py monitor")
        print("  python docparser.py list")
        print("  python docparser.py process <filename>")
        print("  python docparser.py retry")
        print("  python docparser.py stats")
        print("  python docparser.py report <tender_id>")
        print("  python docparser.py query <tender_id> <question>")
        
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/query", methods=["POST"])
def api_query():
    payload = request.get_json(silent=True) or {}
    question = payload.get("question")
    tender_id = payload.get("tender_id")
    if not question:
        return jsonify({"error": "question is required"}), 400
    answer = answer_question_with_rag(question, tender_id)
    return jsonify({"answer": answer}), 200

# ...existing code...
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # existing CLI handling...
        ...
    elif os.getenv("RUN_FLASK", "0") == "1":
        app.run(host="0.0.0.0", port=FLASK_PORT)
    else:
        print("Usage: ...")