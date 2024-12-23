import streamlit as st
import pandas as pd
import pyodbc
from sqlalchemy import create_engine, text
import os
import warnings
import traceback
import logging
from typing import List, Dict, Any
from config import config
import psycopg2
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

def check_access_driver() -> str:
    """Check for available Access drivers."""
    try:
        drivers = [x for x in pyodbc.drivers() if 'access' in x.lower()]
        logger.info(f"Available drivers: {drivers}")
        if not drivers:
            raise RuntimeError("No Access driver found. Please install Microsoft Access Database Engine.")
        return drivers[0]
    except Exception as e:
        logger.error(f"Error checking Access driver: {str(e)}")
        raise

def transfer_mdb_to_postgresql(mdb_path: str) -> List[Dict[str, Any]]:
    """Transfer data from Access database to PostgreSQL."""
    results = []
    conn = None
    pg_engine = None
    
    # Special tables requiring ID control
    id_controlled_tables = ['unmovablemaincins', 'unmovablecins']
    
    try:
        logger.info(f"Starting transfer from {mdb_path}")
        
        # Test PostgreSQL connection first
        pg_success, pg_message = test_postgresql_connection()
        if not pg_success:
            raise RuntimeError(f"PostgreSQL connection test failed: {pg_message}")
        
        # Check for Access driver
        driver = check_access_driver()
        logger.info(f"Using driver: {driver}")
        
        # Create connection string
        conn_str = (
            f'DRIVER={{{driver}}};'
            f'DBQ={os.path.abspath(mdb_path)};'
        )
        
        # Connect to Access database
        conn = pyodbc.connect(conn_str)
        logger.info("Connected to Access database")
        
        # Get tables
        cursor = conn.cursor()
        tables = [row.table_name for row in cursor.tables(tableType='TABLE')]
        logger.info(f"Found {len(tables)} tables: {tables}")
        
        if not tables:
            raise ValueError("No tables found in the database")
        
        # Create PostgreSQL engine with extended logging
        logger.info(f"Creating PostgreSQL engine with connection string: {config.PG_CONNECTION_STRING}")
        pg_engine = create_engine(
            config.PG_CONNECTION_STRING,
            echo=True  # Enable SQLAlchemy logging
        )
        
        # Process each table with progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, table in enumerate(tables):
            try:
                status_text.text(f"Processing table: {table}")
                logger.info(f"Starting to process table: {table}")
                
                # Read from Access
                query = f"SELECT * FROM [{table}]"
                df = pd.read_sql(query, conn)
                logger.info(f"Read {len(df)} rows from Access table {table}")
                
                if df.empty:
                    results.append({
                        "table": table,
                        "status": "Skipped",
                        "records": 0,
                        "message": "Empty table"
                    })
                    continue
                
                table_lower = table.lower()
                
                # Log column information
                logger.info(f"Columns in table {table}: {df.columns.tolist()}")
                logger.info(f"Column types in table {table}: {df.dtypes.to_dict()}")
                
                # Special processing for ID-controlled tables
                if table_lower in id_controlled_tables:
                    with pg_engine.connect() as connection:
                        try:
                            # Check if table exists
                            table_exists = connection.execute(text(
                                f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_lower}')"
                            )).scalar()

                            if table_exists:
                                # Get existing IDs
                                existing_ids = pd.read_sql(f"SELECT id FROM {table_lower}", connection)
                                
                                if not existing_ids.empty:
                                    df = df[~df['ID'].isin(existing_ids['id'])]
                                
                                if not df.empty:
                                    df.to_sql(
                                        name=table_lower,
                                        con=pg_engine,
                                        if_exists='append',
                                        index=False
                                    )
                            else:
                                df.to_sql(
                                    name=table_lower,
                                    con=pg_engine,
                                    if_exists='replace',
                                    index=False
                                )
                        except SQLAlchemyError as e:
                            logger.error(f"SQLAlchemy error processing table {table}: {str(e)}")
                            raise
                else:
                    # Normal append for other tables with error handling
                    try:
                        df.to_sql(
                            name=table_lower,
                            con=pg_engine,
                            if_exists='append',
                            index=False
                        )
                    except SQLAlchemyError as e:
                        logger.error(f"SQLAlchemy error writing table {table}: {str(e)}")
                        raise
                
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
                error_msg = f"Error processing table {table}: {str(e)}\n{traceback.format_exc()}"
                logger.error(error_msg)
                results.append({
                    "table": table,
                    "status": "Error",
                    "records": 0,
                    "message": str(e)
                })
        
        status_text.text("Processing complete!")
        
    except Exception as e:
        error_msg = f"Transfer error: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        results = [{
            "status": "Error",
            "message": str(e)
        }]
    
    finally:
        if conn:
            conn.close()
            logger.info("Closed Access database connection")
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
                                        <strong>Table:</strong> {result['table']}<br>
                                        <strong>Status:</strong> {result['status']}<br>
                                        <strong>Records:</strong> {result['records']}<br>
                                        <strong>Message:</strong> {result['message']}
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