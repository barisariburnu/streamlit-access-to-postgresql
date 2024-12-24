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

## Technical Stack

- **Frontend**: Streamlit
- **Backend**: Python 3.10+
- **Databases**: Microsoft Access, PostgreSQL
- **Containerization**: Docker

## Installation

1. Install Docker and Docker Compose:
```bash
# Add Docker repository
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Install Docker and Docker Compose
sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y

# Start and enable Docker service
sudo systemctl start docker
sudo systemctl enable docker
```

2. Configure firewall:
```bash
# Install firewall if not installed
sudo dnf install firewalld -y

# Start and enable firewall service
sudo systemctl start firewalld
sudo systemctl enable firewalld

# Open port 8501 for Streamlit
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload

# Verify open ports
sudo firewall-cmd --list-ports
```

3. Clone the repository:
```bash
git clone https://github.com/yourusername/streamlit-access-to-postgresql.git
cd streamlit-access-to-postgresql
```

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

## Usage

1. Start the application with Docker:
```bash
sudo docker-compose up -d --build
```

2. Access the application at `http://your-server-ip:8501`

3. Upload an Access database file (.mdb)

4. Click "Start Transfer" to begin the transfer process

5. Monitor the progress and check the results in the detailed report

## Docker Commands

```bash
# View application logs
sudo docker-compose logs -f

# Stop the application
sudo docker-compose down

# Restart the application
sudo docker-compose restart

# Rebuild and start
sudo docker-compose up -d --build
```

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
3. Verify PostgreSQL connection settings in `.streamlit/secrets.toml`
4. Ensure PostgreSQL user has appropriate permissions

### Access Database Engine Issues
If you see "No Access driver found" error:
1. Verify Microsoft Access Database Engine is installed in the Docker container
2. Check Docker build logs for any installation errors
3. Ensure proper configuration in Dockerfile

## Security Considerations

- Sensitive configuration is stored in `.streamlit/secrets.toml`
- Temporary files are automatically cleaned up
- Database credentials are never exposed in the interface
- File size limits prevent server overload
- CORS and XSRF protections enabled

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