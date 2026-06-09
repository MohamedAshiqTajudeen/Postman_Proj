"""
SQLite Database Initializer, Connection Manager, and Transaction-Safe CRUD Utilities.
Enforces PEP-8 guidelines, transaction safety, error handling, and SQLite foreign keys.
"""

import os
import sqlite3
import json
from flask import g

DATABASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database.db"
)


def get_db():
    """
    Returns an active database connection stored in the application context.
    Ensures foreign key relations are strictly checked and returns sqlite3.Row objects.
    """
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_PATH)
        db.row_factory = sqlite3.Row
        # Enable foreign key support (SQLite requires explicitly turning this on)
        db.execute("PRAGMA foreign_keys = ON;")
    return db


def init_db():
    """
    Bootstraps the SQLite tables if they do not yet exist.
    Reflects the exact DB tables from the Backend Schema, including conversion audits.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        # Enable foreign keys during table setup
        cursor.execute("PRAGMA foreign_keys = ON;")

        # 1. uploaded_collections
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_name TEXT NOT NULL,
                file_name TEXT NOT NULL,
                uploaded_by TEXT DEFAULT 'User',
                uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_apis INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending'
            );
        """)

        # 2. api_details
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER NOT NULL,
                api_name TEXT NOT NULL,
                method TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                headers TEXT, -- JSON String
                request_body TEXT,
                query_params TEXT, -- JSON String
                raw_json_chunk TEXT, -- Raw original postman definitions schema
                FOREIGN KEY (collection_id) REFERENCES uploaded_collections(id) ON DELETE CASCADE
            );
        """)

        # Safe schema migration check to add raw_json_chunk column to any existing sqlite DB
        cursor.execute("PRAGMA table_info(api_details);")
        existing_cols = [row[1] for row in cursor.fetchall()]
        if "raw_json_chunk" not in existing_cols:
            cursor.execute("ALTER TABLE api_details ADD COLUMN raw_json_chunk TEXT;")

        # 3. generated_testcases
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generated_testcases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_id INTEGER NOT NULL,
                testcase_name TEXT NOT NULL,
                testcase_type TEXT CHECK(testcase_type IN ('positive', 'negative', 'boundary')) NOT NULL,
                expected_result TEXT NOT NULL,
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_id) REFERENCES api_details(id) ON DELETE CASCADE
            );
        """)

        # 4. generated_scripts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generated_scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_id INTEGER NOT NULL,
                script_name TEXT NOT NULL,
                script_content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_id) REFERENCES api_details(id) ON DELETE CASCADE
            );
        """)

        # 5. ai_recommendations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_id INTEGER NOT NULL,
                recommendation TEXT NOT NULL,
                recommendation_type TEXT CHECK(recommendation_type IN ('Functional', 'Security', 'Performance')) NOT NULL,
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (api_id) REFERENCES api_details(id) ON DELETE CASCADE
            );
        """)

        # 6. conversion_reports (Correction 3 - Persistent reports in database)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversion_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER NOT NULL,
                assertions_converted INTEGER DEFAULT 0,
                failed_conversions INTEGER DEFAULT 0,
                unsupported_assertions INTEGER DEFAULT 0,
                warnings TEXT, -- JSON array string
                success_percentage REAL DEFAULT 0.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (collection_id) REFERENCES uploaded_collections(id) ON DELETE CASCADE
            );
        """)

        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error initializing SQLite database tables: {e}")
        raise e
    finally:
        conn.close()


# =====================================================================
# TRANSACTION-SAFE CRUD UTILITIES (Error handling, auto commit/rollback)
# =====================================================================

def execute_write(query: str, params: tuple = ()) -> int:
    """
    Executes a single write action (INSERT, UPDATE, DELETE) inside a transaction.
    Returns the lastrowid on INSERT, or the number of rows affected.
    Automatically rolls back on operational/integrity failures.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        # Use connection context manager for auto commit / rollback on error
        with conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            last_id = cursor.lastrowid
            affected = cursor.rowcount
            return last_id if last_id is not None and last_id > 0 else affected
    except sqlite3.Error as e:
        print(f"Database write transaction error: {e}. Executed Query: {query}")
        raise e
    finally:
        conn.close()


def execute_read_all(query: str, params: tuple = ()) -> list:
    """
    Executes a read query and returns all matching records as a list of sqlite3.Row objects.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database read query error: {e}. Executed Query: {query}")
        return []
    finally:
        conn.close()


def execute_read_one(query: str, params: tuple = ()):
    """
    Executes a read query and returns the first matching record as a Row object, or None if empty.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"Database read one query error: {e}. Executed Query: {query}")
        return None
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Collection Model CRUD Operations
# ---------------------------------------------------------------------

def create_collection(collection_name: str, file_name: str, total_apis: int = 0, status: str = "pending") -> int:
    """Inserts a new collection log into SQLite."""
    query = """
        INSERT INTO uploaded_collections (collection_name, file_name, total_apis, status)
        VALUES (?, ?, ?, ?);
    """
    return execute_write(query, (collection_name, file_name, total_apis, status))


def get_all_collections() -> list:
    """Returns all recorded collections in SQLite."""
    return execute_read_all("SELECT * FROM uploaded_collections ORDER BY uploaded_at DESC;")


def get_collection(collection_id: int):
    """Returns a single collection metadata details."""
    return execute_read_one("SELECT * FROM uploaded_collections WHERE id = ?;", (collection_id,))


def update_collection_status(collection_id: int, status: str, total_apis: int = None) -> bool:
    """Updates the migration stage and API tally of a collection."""
    if total_apis is not None:
        query = "UPDATE uploaded_collections SET status = ?, total_apis = ? WHERE id = ?;"
        params = (status, total_apis, collection_id)
    else:
        query = "UPDATE uploaded_collections SET status = ? WHERE id = ?;"
        params = (status, collection_id)
    return execute_write(query, params) > 0


def delete_collection(collection_id: int) -> bool:
    """Deletes a collection. Cascading deletes clear APIs, testcases, and files."""
    return execute_write("DELETE FROM uploaded_collections WHERE id = ?;", (collection_id,)) > 0


# ---------------------------------------------------------------------
# API Details CRUD Operations
# ---------------------------------------------------------------------

def create_api(collection_id: int, api_name: str, method: str, endpoint: str,
               headers: str = None, request_body: str = None, query_params: str = None,
               raw_json_chunk: str = None) -> int:
    """Saves details of a specific parsed API endpoint belonging to a collection."""
    query = """
        INSERT INTO api_details (collection_id, api_name, method, endpoint, headers, request_body, query_params, raw_json_chunk)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """
    return execute_write(query, (collection_id, api_name, method.upper(), endpoint, headers, request_body, query_params, raw_json_chunk))


def get_apis_for_collection(collection_id: int) -> list:
    """Returns all endpoint rules resolved within a uploaded suite folder."""
    return execute_read_all("SELECT * FROM api_details WHERE collection_id = ? ORDER BY id ASC;", (collection_id,))


# ---------------------------------------------------------------------
# Generated Testcases CRUD Operations
# ---------------------------------------------------------------------

def create_testcase(api_id: int, testcase_name: str, testcase_type: str, expected_result: str) -> int:
    """Saves an isolated test metadata assertion detail."""
    query = """
         INSERT INTO generated_testcases (api_id, testcase_name, testcase_type, expected_result)
         VALUES (?, ?, ?, ?);
    """
    return execute_write(query, (api_id, testcase_name, testcase_type, expected_result))


def get_testcases_for_collection(collection_id: int) -> list:
    """Retrieves all generated testcases associated with a collection."""
    query = """
        SELECT gt.*, ad.api_name, ad.method, ad.endpoint
        FROM generated_testcases gt
        JOIN api_details ad ON gt.api_id = ad.id
        WHERE ad.collection_id = ?
        ORDER BY gt.id ASC;
    """
    return execute_read_all(query, (collection_id,))


# ---------------------------------------------------------------------
# Generated Scripts CRUD Operations
# ---------------------------------------------------------------------

def create_script(api_id: int, script_name: str, script_content: str) -> int:
    """Persists a complete executable Python Pytest script to SQLite."""
    query = """
        INSERT INTO generated_scripts (api_id, script_name, script_content)
        VALUES (?, ?, ?);
    """
    return execute_write(query, (api_id, script_name, script_content))


def get_scripts_for_collection(collection_id: int) -> list:
    """Returns all executable pytest code files for a given package."""
    query = """
        SELECT gs.*, ad.api_name
        FROM generated_scripts gs
        JOIN api_details ad ON gs.api_id = ad.id
        WHERE ad.collection_id = ?
        ORDER BY gs.id ASC;
    """
    return execute_read_all(query, (collection_id,))


def get_script(script_id: int):
    """Retrieves a single generated script from the store."""
    return execute_read_one("SELECT * FROM generated_scripts WHERE id = ?;", (script_id,))


# ---------------------------------------------------------------------
# AI Recommendations CRUD Operations
# ---------------------------------------------------------------------

def create_recommendation(api_id: int, recommendation: str, recommendation_type: str) -> int:
    """Stores visual tips, performance constraints or security audits from Gemini."""
    query = """
        INSERT INTO ai_recommendations (api_id, recommendation, recommendation_type)
        VALUES (?, ?, ?);
    """
    return execute_write(query, (api_id, recommendation, recommendation_type))


def get_recommendations_for_collection(collection_id: int) -> list:
    """Fetches recommendation notes across all APIs of a project."""
    query = """
        SELECT ar.*, ad.api_name, ad.endpoint
        FROM ai_recommendations ar
        JOIN api_details ad ON ar.api_id = ad.id
        WHERE ad.collection_id = ?
        ORDER BY ar.id ASC;
    """
    return execute_read_all(query, (collection_id,))


# ---------------------------------------------------------------------
# Conversion Reports CRUD Operations (Correction 3)
# ---------------------------------------------------------------------

def create_conversion_report(collection_id: int, assertions_converted: int = 0,
                             failed_conversions: int = 0, unsupported_assertions: int = 0,
                             warnings_list: list = None, success_percentage: float = 0.0) -> int:
    """Persists a complete conversion summary evaluation into SQLite for audit logs."""
    warnings_json = json.dumps(warnings_list if warnings_list else [])
    query = """
        INSERT INTO conversion_reports (collection_id, assertions_converted, failed_conversions,
                                        unsupported_assertions, warnings, success_percentage)
        VALUES (?, ?, ?, ?, ?, ?);
    """
    return execute_write(query, (collection_id, assertions_converted, failed_conversions,
                                 unsupported_assertions, warnings_json, success_percentage))


def get_report_for_collection(collection_id: int):
    """Retrieves a persistent conversion audit report from SQLite store."""
    return execute_read_one("SELECT * FROM conversion_reports WHERE collection_id = ?;", (collection_id,))
