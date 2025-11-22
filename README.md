## Starlink Power Automation (Shelly AZ Plug + TP-Link ER605 + Raspberry Pi 5)

A lightweight Dockerized Python service that automatically powers Starlink equipment on or off based on the primary WAN status of a TP-Link ER605 gateway (via the Omada Controller API).

When the primary internet connection is unavailable for three consecutive checks (≈30 seconds), the service enables a Shelly AZ Plug through its local HTTP RPC API to power up Starlink.
Once the primary WAN is restored and stable for 10 minutes, the plug turns off again — conserving energy when Starlink isn’t needed.

Originally developed to reduce power draw on a portable power station during outages in Ukraine, this project runs reliably on a Raspberry Pi 5, which handles both the Omada Controller and the automation container.

## How It Works

- **Default State**: Starlink (Shelly plug) is OFF
- **WAN1 Failure**: After 3 consecutive failures (30 seconds), Starlink turns ON
- **WAN1 Recovery**: After WAN1 is back online for 10 minutes, Starlink turns OFF
- **Check Interval**: Every 10 seconds
- **State Persistence**: Maintains state across restarts via `state.json`

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

## State File

`state.json` automatically tracks:
- `consecutive_failures` - Current failure count
- `plug_on` - Current plug state
- `last_wan1_online_time` - Last successful WAN1 check timestamp

