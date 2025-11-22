import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .shelly_controller import ShellyController, ControlMode

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load API token from environment
API_TOKEN = os.getenv('API_TOKEN')
if not API_TOKEN:
    raise ValueError('API_TOKEN environment variable must be set')

# Initialize rate limiter (10 requests per hour for all endpoints)
limiter = Limiter(key_func=get_remote_address, default_limits=["10/hour"])

# Initialize FastAPI app
app = FastAPI(
    title="Shelly Starlink Control API",
    description="API to control Shelly plug operation modes",
    version="1.0.0"
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initialize controller
controller = ShellyController()


class ControlResponse(BaseModel):
    """Response model for control endpoint"""
    success: bool
    mode: str
    message: str


class ModeOption(BaseModel):
    """Response model for mode option"""
    value: str
    label: str
    description: str


class ModesResponse(BaseModel):
    """Response model for modes endpoint"""
    modes: list[ModeOption]


def verify_token(token: str) -> None:
    """Verify the API token from query parameter"""
    if token != API_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )


@app.get("/")
async def home():
    """Serve the HTML control interface"""
    html_path = Path(__file__).parent.parent / "static" / "index.html"
    return FileResponse(html_path)


@app.get("/modes", response_model=ModesResponse)
async def get_modes() -> ModesResponse:
    """
    Get all available control modes.

    Returns:
        List of available modes with their descriptions
    """
    modes = [
        ModeOption(
            value=ControlMode.AUTO.value,
            label="Auto - Automatic control based on WAN1",
            description="Automatically turns plug on/off based on WAN1 status"
        ),
        ModeOption(
            value=ControlMode.ON.value,
            label="On - Keep plug always ON",
            description="Plug will stay ON regardless of WAN1 status"
        ),
        ModeOption(
            value=ControlMode.OFF.value,
            label="Off - Keep plug always OFF",
            description="Plug will stay OFF regardless of WAN1 status"
        )
    ]
    return ModesResponse(modes=modes)


@app.get("/control", response_model=ControlResponse)
async def control_mode(
    mode: ControlMode,
    token: str,
) -> ControlResponse:
    """
    Control the Shelly plug operation mode.

    Args:
        mode: Operating mode (on/off/auto)
        token: API authentication token

    Returns:
        ControlResponse with success status and message
    """
    verify_token(token)

    try:
        # Set the mode
        success = controller.set_mode(mode)

        if success:
            logger.info(f"Mode changed to: {mode.value}")
            return ControlResponse(
                success=True,
                mode=mode.value,
                message=f"Successfully set mode to '{mode.value}'"
            )
        else:
            logger.error(f"Failed to set mode to: {mode.value}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to set mode to '{mode.value}'"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting mode: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )


@app.get("/status")
@limiter.limit("30/hour")
async def get_status(request: Request) -> dict:
    """
    Get current system status.

    Returns:
        Current mode, plug state, and monitoring status
    """
    try:
        status = controller.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )
