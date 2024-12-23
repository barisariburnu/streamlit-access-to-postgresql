# Access to PostgreSQL Data Transfer Tool

This Streamlit application facilitates the transfer of data from Microsoft Access databases (.mdb files) to PostgreSQL databases. It provides a user-friendly web interface for uploading Access database files and handles the transfer process with detailed progress tracking and error reporting.

## Features

- Web-based interface for file upload
- Support for Microsoft Access .mdb files
- Automatic table detection and transfer
- Progress tracking for each table
- Detailed error reporting
- Special handling for ID-controlled tables
- Dark mode interface
- Secure configuration management

## Prerequisites

- Python 3.8 or higher
- Microsoft Access Database Engine (for reading .mdb files)
- PostgreSQL Server
- Windows OS (due to Access Database Engine requirement)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/streamlit-access-to-postgresql.git
cd streamlit-access-to-postgresql
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Install Microsoft Access Database Engine:
   - Download the appropriate version (32-bit or 64-bit) from Microsoft's website
   - Run the installer
   - Make sure it matches your Python architecture (32/64-bit)

## Configuration

1. Create a `.streamlit` directory in the project root:
```bash
mkdir .streamlit
```

2. Create and configure `secrets.toml` in the `.streamlit` directory:
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

3. The application will automatically create an `uploads` directory for temporary file storage.

## Usage

1. Start the application:
```bash
streamlit run app.py
```

2. Open your web browser and navigate to the provided URL (typically `http://localhost:8501`)

3. Upload an Access database file (.mdb)

4. Click "Start Transfer" to begin the transfer process

5. Monitor the progress and check the results in the detailed report

## Special Features

### ID-Controlled Tables
The application provides special handling for certain tables that require ID control:
- unmovablemaincins
- unmovablecins

For these tables, the application:
- Checks for existing records
- Only transfers new records
- Maintains data integrity

### Error Handling
- Detailed logging of all operations
- Visual feedback for success/failure
- Expandable error details
- Automatic cleanup of temporary files

## Troubleshooting

### PostgreSQL Connection Issues
If you encounter PostgreSQL connection errors:
1. Verify PostgreSQL server is running
2. Check firewall settings for port 5432
3. Verify PostgreSQL connection settings in `secrets.toml`
4. Ensure PostgreSQL user has appropriate permissions

### Access Database Engine Issues
If you see "No Access driver found" error:
1. Verify Microsoft Access Database Engine is installed
2. Ensure Python and Access Database Engine architectures match
3. Restart your system after installing the Access Database Engine

## Security Considerations

- Sensitive configuration is stored in `secrets.toml`
- Temporary files are automatically cleaned up
- Database credentials are never exposed in the interface
- File size limits prevent server overload
- CORS and XSRF protections enabled

## Project Structure

```
project/
├── .gitignore
├── .streamlit/
│   ├── config.toml        # Streamlit UI configuration
│   └── secrets.toml       # Sensitive configuration data
├── app.py                 # Main application
├── config.py             # Configuration management
├── requirements.txt      # Project dependencies
└── uploads/             # Upload directory
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the development team.