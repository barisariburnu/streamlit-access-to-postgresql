import os
import streamlit as st

class Config:
    # Database settings from secrets.toml
    db_config = st.secrets.get("postgres", {})
    PG_USER = db_config.get("user")
    PG_PASSWORD = db_config.get("password")
    PG_HOST = db_config.get("host")
    PG_PORT = db_config.get("port")
    PG_DATABASE = db_config.get("database")
    
    # Construct database URL
    PG_CONNECTION_STRING = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
    
    # Application settings from secrets.toml
    app_config = st.secrets.get("app", {})
    MAX_FILE_SIZE = app_config.get("max_file_size")
    UPLOAD_FOLDER = app_config.get("upload_folder")
    
    # Ensure upload directory exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

# Create config instance
config = Config()