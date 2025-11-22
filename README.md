## Starlink Power Automation (Shelly AZ Plug + TP-Link ER605 + Raspberry Pi 5)

A lightweight Dockerized Python service that automatically powers Starlink equipment on or off based on the primary WAN status of a TP-Link ER605 gateway (via the Omada Controller API).

When the primary internet connection is unavailable for three consecutive checks (≈30 seconds), the service enables a Shelly AZ Plug through its local HTTP RPC API to power up Starlink.
Once the primary WAN is restored and stable for 10 minutes, the plug turns off again — conserving energy when Starlink isn't needed.

The service includes a secure REST API endpoint for remote control, allowing to manually override the automatic behavior and set the plug to always on, always off, or automatic mode.

Originally developed to reduce power draw on a portable power station during outages in Ukraine, this project runs reliably on a Raspberry Pi 5, which handles both the Omada Controller and the automation container.

## How It Works

- **Default State**: Starlink (Shelly plug) is OFF
- **WAN1 Failure**: After 3 consecutive failures (30 seconds), Starlink turns ON
- **WAN1 Recovery**: After WAN1 is back online for 10 minutes, Starlink turns OFF
- **Check Interval**: Every 10 seconds
- **State Persistence**: Maintains state across restarts via `state.json`

## Project Structure

```
.
├── src/                     # Python source code
│   ├── api.py              # FastAPI application
│   ├── monitor_wan1.py     # WAN monitoring service
│   ├── shelly_controller.py # Shelly plug controller
│   └── supervisor.py       # Multi-process supervisor
├── static/                  # Static web files
│   └── index.html          # Web control interface
├── .env.example            # Example environment configuration
├── docker-compose.yml      # Docker Compose configuration
├── Dockerfile              # Container image definition
├── requirements.txt        # Python dependencies
└── state.json             # Runtime state (auto-generated)
```

## Setup

1. Configure environment variables:
```bash
cp .env.example .env
nano .env
```

2. Start the service:
```bash
make up
```

## Commands

```bash
make up       # Start the monitoring service
make stop     # Stop the service (without removing)
make restart  # Restart the service
make rebuild  # Rebuild and restart the service
```

## Configuration

Edit `.env` file:

**Omada Controller**
- `OMADA_URL` - Controller URL
- `OMADA_USERNAME` - Login username
- `OMADA_PASSWORD` - Login password
- `OMADA_SITE_ID` - Site ID
- `OMADA_GATEWAY_MAC` - Gateway MAC address

**Shelly Plug**
- `SHELLY_BASE_URL` - Shelly base URL

**Monitoring**
- `CHECK_INTERVAL` - Seconds between checks (default: 10)
- `FAILURE_THRESHOLD` - Failures before turning plug ON (default: 3)
- `RECOVERY_DELAY` - Seconds WAN1 online before turning plug OFF (default: 600)

**API**
- `API_TOKEN` - Secure token for API authentication (required)

## Web Interface

The service provides a simple web interface for controlling the plug. Access it at:

```
http://localhost:3051/
```

The interface includes:
- **Mode dropdown**: Select between Auto, On, or Off
- **Token field**: Enter your API token
- **Apply button**: Submit the changes

The interface is fully browser-based and works on any device.

## API Control

The service also exposes a REST API on `http://localhost:3051` for programmatic control.

### Rate Limiting

API endpoints have different rate limits per IP address to prevent abuse:
- **Control endpoints** (`/control`): 10 requests per hour
- **Status endpoint** (`/status`): 30 requests per hour (to accommodate auto-refresh)

### Endpoints

#### Control Mode
```
GET /control?mode={on|off|auto}&token=YOUR_API_TOKEN
```

**Modes:**
- `on` - Keep plug always ON (disables automatic monitoring)
- `off` - Keep plug always OFF (disables automatic monitoring)
- `auto` - Automatic control based on WAN1 status (default)

**Examples:**
```bash
# Set to always ON
curl "http://localhost:3051/control?mode=on&token=YOUR_API_TOKEN"

# Set to always OFF
curl "http://localhost:3051/control?mode=off&token=YOUR_API_TOKEN"

# Set to automatic mode
curl "http://localhost:3051/control?mode=auto&token=YOUR_API_TOKEN"
```

#### Get Status
```
GET /status
```

Returns current mode, plug state, and monitoring information.

**Example:**
```bash
curl "http://localhost:3051/status"
```

#### Get Available Modes
```
GET /modes
```

Returns all available control modes with their descriptions.

**Example:**
```bash
curl "http://localhost:3051/modes"
```

**Response:**
```json
{
  "modes": [
    {
      "value": "auto",
      "label": "Auto - Automatic control based on WAN1",
      "description": "Automatically turns plug on/off based on WAN1 status"
    },
    {
      "value": "on",
      "label": "On - Keep plug always ON",
      "description": "Plug will stay ON regardless of WAN1 status"
    },
    {
      "value": "off",
      "label": "Off - Keep plug always OFF",
      "description": "Plug will stay OFF regardless of WAN1 status"
    }
  ]
}
```

### API Security

Most endpoints require token authentication via the `token` query parameter. Set the `API_TOKEN` in your `.env` file and include it in every request.

**Public endpoints (no auth required):**
- `GET /modes` - Get available control modes

The API is accessible via Cloudflare Tunnel on localhost:3051 and can be used directly from a browser or the web interface.

## State File

`state.json` automatically tracks:
- `consecutive_failures` - Current failure count
- `plug_on` - Current plug state
- `last_wan1_online_time` - Last successful WAN1 check timestamp
- `mode` - Current operating mode (on/off/auto)
