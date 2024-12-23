import os
import streamlit as st

class Config:
    # Database settings from secrets.toml
    PG_USER = st.secrets["postgres"]["user"]
    PG_PASSWORD = st.secrets["postgres"]["password"]
    PG_HOST = st.secrets["postgres"]["host"]
    PG_PORT = st.secrets["postgres"]["port"]
    PG_DATABASE = st.secrets["postgres"]["database"]
    
    # Construct database URL
    PG_CONNECTION_STRING = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
    print(f"Database URL: {PG_CONNECTION_STRING}")
    
    # Application settings from secrets.toml
    MAX_FILE_SIZE = st.secrets["app"]["max_file_size"]
    UPLOAD_FOLDER = st.secrets["app"]["upload_folder"]
    
    # Ensure upload directory exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

# Create config instance
config = Config()