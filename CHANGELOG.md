# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release
- Web-based interface for MDB file upload
- Automatic table detection and transfer
- Progress tracking for each table transfer
- Detailed error reporting and logging
- Support for ID-based duplicate detection
- Docker and Docker Compose support
- Comprehensive documentation
- Example secrets configuration file

### Changed
- Replaced hardcoded `/tmp/` path with configurable upload folder
- Translated Turkish comments to English for international collaboration
- Improved error handling and user feedback

### Security
- Added file size validation (1GB limit)
- Secure credential management via Streamlit secrets
- Automatic cleanup of temporary files

## [1.0.0] - 2025-11-25

### Added
- Core functionality for transferring Microsoft Access (.mdb) databases to PostgreSQL
- Streamlit-based user interface
- MDBTools integration for reading Access databases
- SQLAlchemy for PostgreSQL connections
- Support for large file transfers
- Dark mode interface
- Health checks in Docker container
- Firewall configuration documentation

### Features
- Automatic table structure detection
- Batch processing of multiple tables
- Duplicate record prevention via ID checking
- Visual progress indicators
- Expandable detailed results view
- Automatic temporary file cleanup

---

## Release Notes

### Version 1.0.0
This is the initial release of MDB to PostgreSQL transfer tool. The application provides a simple, web-based interface for migrating data from Microsoft Access databases to PostgreSQL.

**Key Features:**
- Simple file upload interface
- Automated table detection
- Progress tracking
- Error reporting
- Docker support

**Known Limitations:**
- Only supports .mdb files (Access 2003 format)
- Requires MDBTools to be installed
- Maximum file size: 1GB

**Future Improvements:**
- Support for .accdb files (newer Access formats)
- Parallel table processing
- Resume capability for failed transfers
- Data validation options
- Custom field mapping
