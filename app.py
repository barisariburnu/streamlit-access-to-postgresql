import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import os
import warnings
import traceback
import logging
from typing import List, Dict, Any
from config import config
import psycopg2
import subprocess
from sqlalchemy.exc import SQLAlchemyError

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_postgresql_connection():
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
        
        with open(output_path, 'w') as f:
            f.write(result.stdout)
        
    except Exception as e:
        logger.error(f"Error exporting table {table}: {str(e)}")
        raise

def transfer_mdb_to_postgresql(mdb_path: str) -> List[Dict[str, Any]]:
    """Transfer data from Access database to PostgreSQL using MDBTools."""
    results = []
    pg_engine = None
    
    try:
        logger.info(f"Starting transfer from {mdb_path}")
        
        # Test PostgreSQL connection first
        pg_success, pg_message = test_postgresql_connection()
        if not pg_success:
            raise RuntimeError(f"PostgreSQL connection test failed: {pg_message}")
        
        # Check for MDBTools
        check_mdb_tools()
        
        # Get tables
        tables = get_tables(mdb_path)
        logger.info(f"Found {len(tables)} tables: {tables}")
        
        if not tables:
            raise ValueError("No tables found in the database")
        
        # Create PostgreSQL engine
        pg_engine = create_engine(config.PG_CONNECTION_STRING)
        
        # Process each table
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, table in enumerate(tables):
            try:
                status_text.text(f"Processing table: {table}")
                logger.info(f"Starting to process table: {table}")
                
                # Export to CSV temporarily
                temp_csv = f"/tmp/{table}.csv"
                export_table_to_csv(mdb_path, table, temp_csv)
                
                # Read CSV into DataFrame
                df = pd.read_csv(temp_csv, low_memory=False)
                logger.info(f"Read {len(df)} rows from table {table}")
                
                # Remove temporary CSV
                if os.path.exists(temp_csv):
                    os.remove(temp_csv)
                
                if df.empty:
                    results.append({
                        "table": table,
                        "status": "Skipped",
                        "records": 0,
                        "message": "Empty table"
                    })
                    continue
                
                # Write to PostgreSQL
                table_lower = table.lower()
                
                # ID kontrol� yap - e�er ID s�tunu varsa
                if 'ID' in df.columns:
                    # Mevcut ID'leri veritaban�ndan al
                    existing_ids_query = f"SELECT \"ID\" FROM {table_lower}"
                    try:
                        existing_ids = pd.read_sql(existing_ids_query, pg_engine)["ID"].tolist()
                        logger.info(f"Found {len(existing_ids)} existing IDs in table {table_lower}")
                        
                        # Sadece yeni kay�tlar� filtrele
                        original_count = len(df)
                        df = df[~df['ID'].isin(existing_ids)]
                        filtered_count = original_count - len(df)
                        
                        if filtered_count > 0:
                            logger.info(f"Filtered out {filtered_count} existing records from table {table_lower}")
                    except Exception as e:
                        # Tablo hen�z mevcut de�ilse veya ba�ka bir hata olu�ursa, devam et
                        logger.warning(f"Could not check existing IDs in {table_lower}: {str(e)}")
                
                # Verileri ekle
                if not df.empty:
                    df.to_sql(
                        name=table_lower,
                        con=pg_engine,
                        if_exists='append',
                        index=False
                    )
                else:
                    logger.info(f"No new records to add to {table_lower}")
                
                results.append({
                    "table": table,
                    "status": "Success",
                    "records": len(df),
                    "message": "Transferred successfully"
                })
                
                # Update progress
                progress = (idx + 1) / len(tables)
                progress_bar.progress(progress)
                
            except Exception as e:
                error_msg = f"Error processing table {table}: {str(e)}"
                logger.error(error_msg)
                results.append({
                    "table": table,
                    "status": "Error",
                    "records": 0,
                    "message": str(e)
                })
        
        status_text.text("Processing complete!")
        
    except Exception as e:
        error_msg = f"Transfer error: {str(e)}"
        logger.error(error_msg)
        results = [{
            "table": "Unknown",
            "status": "Error",
            "records": 0,
            "message": str(e)
        }]
    
    finally:
        if pg_engine:
            pg_engine.dispose()
            logger.info("Disposed PostgreSQL connection")
    
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
    
    if uploaded_file:
        if not check_file_size(uploaded_file):
            st.error("File size exceeds maximum limit (1GB)")
            return
        
        try:
            # Save uploaded file
            file_path = os.path.join(config.UPLOAD_FOLDER, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            # Process file when user clicks the button
            if st.button("Start Transfer"):
                with st.spinner("Processing..."):
                    try:
                        results = transfer_mdb_to_postgresql(file_path)
                        
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
                                        <strong>Message:</strong> {result.get('message', '')}
                                    </div>
                                """, unsafe_allow_html=True)
                    
                    except Exception as e:
                        st.error(f"Error during transfer: {str(e)}")
                        logger.error(f"Transfer error: {str(e)}\n{traceback.format_exc()}")
                    
                    finally:
                        # Cleanup
                        if os.path.exists(file_path):
                            os.remove(file_path)
        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
            logger.error(f"File processing error: {str(e)}\n{traceback.format_exc()}")
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)

if __name__ == "__main__":
    main()
