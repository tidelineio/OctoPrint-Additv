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

## Settings

The plugin stores its settings in `additv.yaml` within the plugin's data folder. These settings can be configured through environment variables:

### Environment Variables

The following settings can be configured using environment variables with the `additv_` prefix. If an environment variable exists, it will take precedence over the local setting:

- `additv_url`: Base URL for the service
- `additv_registration_token`: Token used for printer registration

To configure these environment variables:

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your configuration:
   ```
   ADDITV_URL=your_service_url
   ADDITV_REGISTRATION_TOKEN=your_registration_token
   ```

The DevContainer is configured to automatically load these environment variables when starting up. The `.env` file is excluded from git to keep sensitive information secure.

### Settings

The plugin stores the following settings in `additv.yaml`:

- `url`: Base URL for the service (default: "", can be provided via $ADDITV_URL)
- `registration_token`: Token used for printer registration (default: empty, can be provided via $ADDITV_REGISTRATION_TOKEN)
- `service_user`: Service user identifier for the printer (set automatically during registration)
- `printer_id`: Unique identifier for the printer (set automatically during registration)
- `access_key`: Access token (set automatically during registration)
- `refresh_token`: Refresh token (set automatically during registration)
- `anon_key`: Anonymous key for public access (set automatically during registration)

### Telemetry Settings

The plugin includes temperature-based telemetry filtering to optimize data transmission:

- High Resolution Mode (above 30°C): Full telemetry data is sent for accurate monitoring during printer operation
- Low Resolution Mode (below 30°C): Data is only sent when temperature changes exceed 0.3°C, reducing data transmission during idle periods

### Telemetry Type Settings

The plugin supports different telemetry formats:

- `telemetry_type`: Type of telemetry format to process (default: "PrusaMK3")
  - "PrusaMK3": For Prusa MK3 printers, processes both temperature and power/fan data across multiple lines
  - "Virtual": For virtual printers with simplified single-line format (e.g., "T:21.30/ 0.00 B:21.30/ 0.00 @:64")

### Error Handling

The plugin includes enhanced error handling for edge function calls:

- All edge function calls return both the result data and an error message (if any)
- Specific error messages are displayed on the printer's LCD for common issues:
  - Authentication failures: "Error: Auth failed"
  - Connection issues: "Error: Client offline"
  - API errors: "Error: API issue"
- Detailed error information is logged to assist with troubleshooting
- Job progress reporting includes error handling to ensure reliable telemetry data transmission
