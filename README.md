# OctoPrint-Additv Plugin

This is a development environment for the Additv OctoPrint plugin using DevContainers.

## Development Setup

### Prerequisites
- Visual Studio Code
- Docker Desktop
- VSCode Remote - Containers extension

### Getting Started

1. Open this folder in VSCode
2. When prompted, click "Reopen in Container" or run the command palette (F1) and select "Remote-Containers: Reopen in Container"
3. VSCode will build the development container and install all dependencies
4. Once the container is ready, you can start debugging:
   - Set breakpoints in your code
   - Press F5 or use the Run and Debug panel to start "OctoPrint: Debug Plugin"
   - OctoPrint will start in debug mode with your plugin installed
   - Access OctoPrint at http://localhost:5000

### Running with Docker

If you prefer to run the plugin directly with Docker instead of using DevContainers:

1. Start OctoPrint with the plugin:
   ```bash
   docker-compose up
   ```
2. Access OctoPrint at http://localhost:5000

The docker-compose configuration:
- Mounts a persistent volume for OctoPrint configuration
- All settings, uploaded files, and configurations will persist across container restarts
- The plugin is mounted and installed in development mode

### Development Notes

- The plugin is installed in development mode (`pip install -e .`)
- Debugging is configured to break on your plugin code and OctoPrint core code
- Changes to Python files will be reflected after restarting the debug session
- OctoPrint's debug mode is enabled for detailed logging

### Project Structure

```
.
├── .devcontainer/          # DevContainer configuration
├── .vscode/               # VSCode configuration
├── octoprint_additv/      # Plugin source code
└── setup.py              # Plugin setup configuration
