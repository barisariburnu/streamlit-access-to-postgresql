# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit web application that facilitates data transfer from Microsoft Access databases (.mdb files) to PostgreSQL databases. The application provides a user-friendly interface for uploading Access database files and handles the transfer process with progress tracking and error reporting.

## Technology Stack

- **Frontend**: Streamlit (Python web framework)
- **Backend**: Python 3.10+
- **Database Tools**: MDBTools (for reading Access databases), PostgreSQL via psycopg2 and SQLAlchemy
- **Containerization**: Docker with docker-compose
- **Dependencies**: pandas, numpy, SQLAlchemy, psycopg2-binary, watchdog

## Development Commands

### Docker Commands
```bash
# Start the application
sudo docker-compose up -d --build

# View logs
sudo docker-compose logs -f

# Stop the application
sudo docker-compose down

# Restart the application
sudo docker-compose restart
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application locally
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

## Configuration

### Required Configuration Files

1. **`.streamlit/secrets.toml`** - Contains sensitive configuration:
   ```toml
   [postgres]
   user = "your_user"
   password = "your_password"
   host = "your_host"
   port = "5432"
   database = "your_database"
   
   [app]
   max_file_size = 1073741824  # 1GB in bytes
   upload_folder = "uploads"
   ```

2. **`.streamlit/config.toml`** - UI configuration with dark theme settings

### Configuration Management
- `config.py` centralizes configuration loading from Streamlit secrets
- Automatically creates upload directory if it doesn't exist
- Database connection string is constructed from individual components

## Application Architecture

### Core Components

1. **`app.py`** - Main application file containing:
   - Streamlit UI setup and styling
   - File upload handling with size validation
   - PostgreSQL connection testing
   - MDBTools integration for Access database reading
   - Progress tracking and error reporting

2. **`config.py`** - Configuration management:
   - Loads settings from `.streamlit/secrets.toml`
   - Creates database connection strings
   - Manages upload directory creation

### Key Functions

- `test_postgresql_connection()` - Tests both psycopg2 and SQLAlchemy connections
- `get_tables()` - Uses `mdb-tables` command to extract table list from Access files
- `export_table_to_csv()` - Uses `mdb-export` to convert Access tables to CSV
- `transfer_mdb_to_postgresql()` - Main transfer orchestration function

## Data Transfer Process

1. **File Upload**: User uploads .mdb file with size validation
2. **MDBTools Processing**: Extract tables using `mdb-tables` command
3. **Table Export**: Convert each table to CSV using `mdb-export`
4. **Data Loading**: Load CSV into pandas DataFrame
5. **PostgreSQL Insert**: Write data to PostgreSQL using SQLAlchemy
6. **Progress Tracking**: Real-time progress updates in Streamlit UI
7. **Cleanup**: Remove temporary files and connections

## System Dependencies

The Docker container includes these system packages:
- `mdbtools` - For reading Microsoft Access databases
- `unixodbc` and `unixodbc-dev` - ODBC drivers
- `g++` - For compiling Python extensions
- `curl` - For health checks

## Security Considerations

- Sensitive database credentials stored in `.streamlit/secrets.toml`
- File size limits enforced (1GB default)
- Temporary file cleanup after processing
- CORS disabled, XSRF protection enabled
- Error details hidden from users in production

## Special Features

- **Progress Tracking**: Real-time progress bars during transfer
- **Error Handling**: Comprehensive error reporting with expandable details
- **Dark Theme**: Custom dark mode styling
- **File Validation**: Size limits and type checking
- **Connection Testing**: Automatic PostgreSQL connection validation

## Common Issues

- **MDBTools Not Found**: Ensure Docker image includes mdbtools package
- **PostgreSQL Connection**: Verify connection settings in secrets.toml
- **File Size**: Check MAX_FILE_SIZE setting for large databases
- **Temporary Files**: Application automatically cleans up /tmp/*.csv files

## Port Configuration

- Application runs on port 8501
- Docker exposes port 8501:8501
- Firewall should allow port 8501 for external access