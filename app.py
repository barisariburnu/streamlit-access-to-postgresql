from monitoring import report, run_guarded
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import os
import warnings
import traceback
import tempfile
import logging
from typing import List, Dict, Any
from config import config
import psycopg2
import subprocess
from mdb_sync import synchronize_table, validate_source_tables
from upload_audit import (
    UploadInProgress,
    ensure_audit_tables, create_upload, start_upload,
    record_table_result, finish_upload,
)

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_postgresql_connection(*, report_failure=True):
    """Test PostgreSQL connection and log detailed information."""
    try:
        # Try direct psycopg2 connection first
        logger.info("Testing PostgreSQL connection with psycopg2...")
        conn = psycopg2.connect(
            dbname=config.PG_DATABASE,
            user=config.PG_USER,
            password=config.PG_PASSWORD,
            host=config.PG_HOST,
            port=config.PG_PORT
        )
        conn.close()
        logger.info("PostgreSQL connection successful with psycopg2")
        
        # Try SQLAlchemy connection
        logger.info("Testing PostgreSQL connection with SQLAlchemy...")
        engine = create_engine(config.PG_CONNECTION_STRING)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version = result.scalar()
            logger.info(f"PostgreSQL version: {version}")
        engine.dispose()
        logger.info("PostgreSQL connection successful with SQLAlchemy")
        
        return True, "Connection successful"
    
    except Exception as e:
        if report_failure:
            report(e)
        error_msg = f"PostgreSQL connection error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return False, error_msg

def check_file_size(file) -> bool:
    """Check if file size is within limits."""
    try:
        return file.size <= config.MAX_FILE_SIZE
    except Exception as e:
        logger.error(f"Error checking file size: {str(e)}")
        return False

def check_mdb_tools():
    """Check if mdbtools is installed and available."""
    try:
        result = subprocess.run(['mdb-tables', '--version'], 
                              capture_output=True, 
                              text=True)
        if result.returncode != 0:
            raise RuntimeError("MDBTools not found. Please install MDBTools.")
        logger.info("MDBTools found successfully")
        return True
    except FileNotFoundError:
        logger.error("MDBTools not installed")
        raise RuntimeError("MDBTools not installed")
    except Exception as e:
        logger.error(f"Error checking MDBTools: {str(e)}")
        raise

def get_tables(mdb_path: str) -> List[str]:
    """Get list of tables from MDB file using mdb-tables."""
    try:
        result = subprocess.run(['mdb-tables', '-1', mdb_path],
                              capture_output=True,
                              text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Error getting tables: {result.stderr}")
        
        tables = result.stdout.strip().split('\n')
        return [t for t in tables if t]  # Remove empty strings
    except Exception as e:
        logger.error(f"Error getting tables: {str(e)}")
        raise

def export_table_to_csv(mdb_path: str, table: str, output_path: str):
    """Export a single table to CSV using mdb-export."""
    try:
        result = subprocess.run(['mdb-export', mdb_path, table],
                              capture_output=True,
                              text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Error exporting table: {result.stderr}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
        
    except Exception as e:
        logger.error(f"Error exporting table {table}: {str(e)}")
        raise

def register_uploaded_file(uploaded_file, engine) -> str:
    """Log each file selection once, retaining its identity through UI reruns."""
    previous = st.session_state.get("mdb_upload_log")
    if previous and previous["file_id"] == uploaded_file.file_id:
        return previous["upload_id"]
    ensure_audit_tables(engine)
    upload_id = create_upload(engine, uploaded_file.name, uploaded_file.size)
    st.session_state["mdb_upload_log"] = {
        "file_id": uploaded_file.file_id, "upload_id": upload_id,
    }
    return upload_id


def transfer_mdb_to_postgresql(mdb_path: str, upload_id=None) -> List[Dict[str, Any]]:
    """Transfer tables and persist each result atomically with its data."""
    results = []
    pg_engine = None
    active_upload_id = None
    transfer_error = None

    try:
        pg_engine = create_engine(config.PG_CONNECTION_STRING)
        ensure_audit_tables(pg_engine)
        if upload_id is None:
            upload_id = create_upload(
                pg_engine, os.path.basename(mdb_path), os.path.getsize(mdb_path)
            )
        active_upload_id = start_upload(pg_engine, upload_id)

        pg_success, pg_message = test_postgresql_connection(report_failure=False)
        if not pg_success:
            raise RuntimeError(f"PostgreSQL connection test failed: {pg_message}")
        check_mdb_tools()
        tables = get_tables(mdb_path)
        if not tables:
            raise ValueError("No tables found in the database")
        validate_source_tables(tables)

        progress_bar = st.progress(0)
        status_text = st.empty()
        # Separate temporary files for concurrent uploads and arbitrary table names.
        with tempfile.TemporaryDirectory(dir=config.UPLOAD_FOLDER) as work_dir:
            for idx, table in enumerate(tables):
                result = {
                    "table": table, "target_table": table.lower(),
                    "status": "Error", "records": 0, "source_records": 0,
                    "skipped_records": 0, "deactivated_records": 0,
                    "reactivated_records": 0, "message": "",
                }
                try:
                    status_text.text(f"Processing table: {table}")
                    temp_csv = os.path.join(work_dir, f"table_{idx}.csv")
                    export_table_to_csv(mdb_path, table, temp_csv)
                    df = pd.read_csv(temp_csv, low_memory=False)
                    os.remove(temp_csv)
                    result["source_records"] = len(df)

                    with pg_engine.begin() as connection:
                        result.update(synchronize_table(connection, table.lower(), df))
                        record_table_result(connection, active_upload_id, result)
                except Exception as exc:
                    report(exc, 'upload_failed', expected=(ValueError,))
                    # Any insert and its success log have rolled back together.
                    logger.exception("Error processing table %s", table)
                    result.update(
                        status="Error", records=0, deactivated_records=0,
                        reactivated_records=0, message=str(exc),
                    )
                    with pg_engine.begin() as connection:
                        record_table_result(connection, active_upload_id, result)
                results.append(result)
                progress_bar.progress((idx + 1) / len(tables))
        status_text.text("Processing complete!")
    except Exception as exc:
        report(exc, 'upload_failed', expected=(ValueError, UploadInProgress))
        transfer_error = str(exc)
        logger.exception("Transfer error")
        results.append({
            "table": "Unknown", "status": "Error", "records": 0,
            "message": transfer_error,
        })
    finally:
        if pg_engine is not None:
            try:
                if active_upload_id is not None:
                    finish_upload(pg_engine, active_upload_id, transfer_error)
            except Exception as exc:
                report(exc, 'upload_audit_failed')
                logger.exception("Could not finalize upload history")
                results.append({
                    "table": "Upload log", "status": "Error", "records": 0,
                    "message": f"Could not finalize upload history: {exc}",
                })
            finally:
                pg_engine.dispose()
    return results


def main():
    # Set page config
    st.set_page_config(
        page_title="Access to PostgreSQL Transfer",
        page_icon="🔄",
        initial_sidebar_state="collapsed"
    )
    
    # Remove menu button and footer
    hide_menu_style = """
        <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """
    st.markdown(hide_menu_style, unsafe_allow_html=True)
    
    st.title("Access to PostgreSQL Data Transfer")
    
    # Test PostgreSQL connection on startup
    connection_success, connection_message = test_postgresql_connection()
    if not connection_success:
        st.error(f"PostgreSQL Connection Error: {connection_message}")
        return
    
    st.write("Upload an Access database (.mdb) file to transfer its contents to PostgreSQL.")
    
    # File uploader
    uploaded_file = st.file_uploader("Choose an Access database file", type=['mdb'])
    
    if not uploaded_file:
        st.session_state.pop("mdb_upload_log", None)

    if uploaded_file:
        if not check_file_size(uploaded_file):
            st.error("File size exceeds maximum limit (1GB)")
            return
        
        try:
            audit_engine = create_engine(config.PG_CONNECTION_STRING)
            try:
                upload_id = register_uploaded_file(uploaded_file, audit_engine)
            finally:
                audit_engine.dispose()

            # Process file when user clicks the button
            if st.button("Start Transfer"):
                with tempfile.NamedTemporaryFile(
                    dir=config.UPLOAD_FOLDER, suffix=".mdb", delete=False
                ) as file:
                    file_path = file.name
                    file.write(uploaded_file.getbuffer())
                with st.spinner("Processing..."):
                    try:
                        results = transfer_mdb_to_postgresql(file_path, upload_id)
                        
                        # Display results in an expandable section
                        if any(result["status"] == "Error" for result in results):
                            st.error("Transfer completed with errors")
                        else:
                            st.success("Transfer completed successfully!")
                        
                        with st.expander("See detailed results"):
                            for result in results:
                                status_color = {
                                    "Success": "green",
                                    "Error": "red",
                                    "Skipped": "yellow",
                                    "Partial Success": "orange"
                                }.get(result["status"], "white")
                                
                                st.markdown(f"""
                                    <div style='padding: 10px; border-left: 5px solid {status_color}; margin: 5px 0;'>
                                        <strong>Table:</strong> {result.get('table', 'Unknown')}<br>
                                        <strong>Status:</strong> {result.get('status', 'Unknown')}<br>
                                        <strong>Records:</strong> {result.get('records', 0)}<br>
                                        <strong>Moved to passive:</strong> {result.get('deactivated_records', 0)}<br>
                                        <strong>Reactivated:</strong> {result.get('reactivated_records', 0)}<br>
                                        <strong>Message:</strong> {result.get('message', '')}
                                    </div>
                                """, unsafe_allow_html=True)
                    
                    except Exception as e:
                        report(e, 'upload_failed', expected=(ValueError,))
                        st.error(f"Error during transfer: {str(e)}")
                        logger.error(f"Transfer error: {str(e)}\n{traceback.format_exc()}")
                    
                    finally:
                        # Cleanup
                        if os.path.exists(file_path):
                            os.remove(file_path)
        
        except Exception as e:
            report(e, 'upload_failed', expected=(ValueError,))
            st.error(f"Error processing file: {str(e)}")
            logger.error(f"File processing error: {str(e)}\n{traceback.format_exc()}")
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)

if __name__ == "__main__":
    run_guarded(main)
