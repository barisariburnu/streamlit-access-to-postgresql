# MDB to PostgreSQL

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red.svg)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/barisariburnu/mdb-to-postgresql/pulls)

A Streamlit-based web application that simplifies the transfer of data from Microsoft Access databases (.mdb files) to PostgreSQL databases. Features a user-friendly interface with progress tracking, error reporting, and intelligent duplicate detection.

## ✨ Features

- 🌐 **Web-based interface** - No command-line expertise required
- 📁 **Drag & drop** - Simple file upload for .mdb files
- 🔍 **Auto-detection** - Automatically discovers and transfers all tables
- 📊 **Progress tracking** - Visual feedback for each table being processed
- 🛡️ **Duplicate prevention** - Smart ID-based checking to avoid duplicate records
- 📝 **Detailed logging** - Comprehensive error reporting and transfer statistics
- 🐳 **Docker support** - Easy deployment with Docker and Docker Compose
- 🎨 **Modern UI** - Dark mode interface for comfortable viewing
- 🔒 **Secure** - Credentials managed via Streamlit secrets

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Docker Deployment](#docker-deployment)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## 🔧 Prerequisites

### System Requirements

- **Python**: 3.10 or higher
- **PostgreSQL**: 9.x or higher
- **MDBTools**: Required for reading Access databases
- **Docker** (optional): For containerized deployment

### Installing MDBTools

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install mdbtools
```

**CentOS/RHEL/Fedora:**
```bash
sudo dnf install mdbtools
```

**macOS:**
```bash
brew install mdbtools
```

**Windows:**
MDBTools can be installed via [Windows Subsystem for Linux (WSL)](https://docs.microsoft.com/en-us/windows/wsl/install) or using a Docker container.

## 📥 Installation

### Option 1: Local Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/barisariburnu/mdb-to-postgresql.git
   cd mdb-to-postgresql
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Option 2: Docker Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/barisariburnu/mdb-to-postgresql.git
   cd mdb-to-postgresql
   ```

2. **Install Docker and Docker Compose**
   
   Follow the official Docker installation guide for your platform:
   - [Docker Desktop for Windows/Mac](https://www.docker.com/products/docker-desktop)
   - [Docker Engine for Linux](https://docs.docker.com/engine/install/)

## ⚙️ Configuration

1. **Create the `.streamlit` directory** (if not exists)
   ```bash
   mkdir -p .streamlit
   ```

2. **Copy the example secrets file**
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

3. **Edit `.streamlit/secrets.toml`** with your PostgreSQL credentials
   ```toml
   [postgres]
   user = "your_postgresql_username"
   password = "your_postgresql_password"
   host = "your_postgresql_host"  # e.g., "localhost" or "192.168.1.100"
   port = "5432"
   database = "your_database_name"
   
   [app]
   max_file_size = 1073741824  # 1GB in bytes
   upload_folder = "uploads"    # Temporary file storage directory
   ```

### Firewall Configuration (Linux servers)

If deploying on a Linux server, you may need to open port 8501:

```bash
# Install firewalld (if not installed)
sudo dnf install firewalld -y

# Start and enable firewall
sudo systemctl start firewalld
sudo systemctl enable firewalld

# Open port 8501 for Streamlit
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

## 🚀 Usage

### Running Locally

1. **Activate your virtual environment** (if using one)
   ```bash
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Start the Streamlit application**
   ```bash
   streamlit run app.py
   ```

3. **Open your browser** and navigate to `http://localhost:8501`

4. **Upload your .mdb file** and click "Start Transfer"

### Running with Docker

1. **Build and start the container**
   ```bash
   docker-compose up -d --build
   ```

2. **Access the application** at `http://your-server-ip:8501`

3. **View logs** (optional)
   ```bash
   docker-compose logs -f
   ```

4. **Stop the application**
   ```bash
   docker-compose down
   ```

## 🐳 Docker Deployment

### Docker Commands Reference

```bash
# Build and start in detached mode
docker-compose up -d --build

# View real-time logs
docker-compose logs -f

# Stop the application
docker-compose down

# Restart the application
docker-compose restart

# Remove containers and volumes
docker-compose down -v
```

## 📁 Project Structure

```
mdb-to-postgresql/
├── .streamlit/
│   ├── config.toml              # Streamlit UI configuration
│   ├── secrets.toml             # Database credentials (not in repo)
│   └── secrets.toml.example     # Example secrets template
├── app.py                       # Main application file
├── config.py                    # Configuration management
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker container definition
├── docker-compose.yml           # Docker Compose configuration
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
├── LICENSE                      # MIT License
├── CONTRIBUTING.md              # Contribution guidelines
├── CHANGELOG.md                 # Version history
└── uploads/                     # Temporary upload directory (auto-created)
```

## 🔍 How It Works

1. **Upload**: User uploads an .mdb file through the web interface
2. **Validation**: Application validates file size and format
3. **Connection Test**: Verifies PostgreSQL connection
4. **Table Discovery**: Uses MDBTools to detect all tables in the Access database
5. **Data Extraction**: Each table is exported to CSV format temporarily
6. **Duplicate Check**: If tables contain an 'ID' column, existing records are filtered
7. **Data Transfer**: Clean data is inserted into PostgreSQL
8. **Progress Tracking**: Real-time updates shown for each table
9. **Cleanup**: Temporary files are automatically removed
10. **Results**: Detailed summary displayed with success/error status per table

## 🛠️ Troubleshooting

### PostgreSQL Connection Issues

**Problem**: "PostgreSQL Connection Error"

**Solutions**:
- Verify PostgreSQL server is running
- Check firewall settings (port 5432 should be open)
- Verify credentials in `.streamlit/secrets.toml`
- Ensure user has appropriate database permissions
- Test connection manually:
  ```bash
  psql -h your_host -U your_user -d your_database
  ```

### MDBTools Not Found

**Problem**: "MDBTools not installed"

**Solutions**:
- Install MDBTools (see [Prerequisites](#prerequisites))
- Verify installation:
  ```bash
  mdb-tables --version
  ```
- If using Docker, rebuild the container:
  ```bash
  docker-compose up -d --build
  ```

### File Size Exceeded

**Problem**: "File size exceeds maximum limit"

**Solutions**:
- Current limit is 1GB (defined in `secrets.toml`)
- Increase `max_file_size` in `.streamlit/secrets.toml`
- Ensure sufficient disk space in upload directory

### Port 8501 Already in Use

**Problem**: "Address already in use"

**Solutions**:
- Stop other Streamlit instances
- Change port in docker-compose.yml:
  ```yaml
  ports:
    - "8502:8501"  # Use port 8502 instead
  ```

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- Code of conduct
- Development setup
- Submitting pull requests
- Reporting bugs
- Suggesting enhancements

### Quick Start for Contributors

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Commit your changes (`git commit -m '✨ Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Streamlit](https://streamlit.io/)
- Uses [MDBTools](https://github.com/mdbtools/mdbtools) for Access database reading
- Powered by [SQLAlchemy](https://www.sqlalchemy.org/) and [pandas](https://pandas.pydata.org/)

## 📞 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/barisariburnu/mdb-to-postgresql/issues)
- 💡 **Feature Requests**: [GitHub Issues](https://github.com/barisariburnu/mdb-to-postgresql/issues)
- 📖 **Documentation**: [GitHub Wiki](https://github.com/barisariburnu/mdb-to-postgresql/wiki)

---

**Made with ❤️ by [Baris Ari Burnu](https://github.com/barisariburnu)**

If this project helped you, please consider giving it a ⭐ on GitHub!