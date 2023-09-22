from datetime import timedelta
import logging

from homeassistant import config_entries, core
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .dvsportal import DVSPortal, DVSPortalError, DVSPortalAuthError, DVSPortalConnectionError

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dvsportal"

from homeassistant.helpers import config_validation as cv
import voluptuous as vol
from homeassistant.helpers import service
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.components.persistent_notification import async_create as async_create_notification

SERVICE_CREATE_RESERVATION = "create_reservation"

CREATE_RESERVATION_SCHEMA = vol.Schema({
    vol.Required("license_plate_value"): cv.string,
    vol.Optional("license_plate_name"): cv.string,
    vol.Optional("date_from"): cv.datetime,
    vol.Optional("date_until"): cv.datetime,
})


async def async_setup(hass: core.HomeAssistant, config: dict):
    """Set up the dvsportal component from YAML configuration."""

    conf = config.get("dvsportal")
    if conf is None:
        return True

    api_host = conf.get("api_host")
    identifier = conf.get("identifier")
    password = conf.get("password")
    user_agent = conf.get("user_agent")

    dvs_portal = DVSPortal(
        api_host=api_host, 
        identifier=identifier, 
        password=password, 
        user_agent=user_agent,
    )

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            await dvs_portal.update()
            return {
                "balance": dvs_portal.balance,
                "active_reservations": dvs_portal.active_reservations,
            }
        except Exception as e:
            raise e
            raise UpdateFailed(f"Error communicating with API: {e}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="dvsportal",
        update_method=async_update_data,
        update_interval=timedelta(minutes=5),
    )

    hass.data[DOMAIN] = {
        "coordinator": coordinator,
        "dvs_portal": dvs_portal,
    }

    await coordinator.async_config_entry_first_refresh()

    hass.helpers.discovery.load_platform('sensor', DOMAIN, {}, config)

    async def create_reservation_service(call):
        """Create a reservation."""
        license_plate_value = call.data.get("license_plate_value")
        license_plate_name = call.data.get("license_plate_name")
        date_from = call.data.get("date_from")
        date_until = call.data.get("date_until")
        
        dvs_portal = hass.data[DOMAIN]["dvs_portal"]
        try:
            await dvs_portal.create_reservation(
                license_plate_value=license_plate_value,
                license_plate_name=license_plate_name,
                date_from=date_from,
                date_until=date_until
            )
        except DVSPortalError as e:
            _LOGGER.error(f"Failed to create reservation: {e}")
            raise Exception(f"Failed to create reservation: {e}")
    hass.services.async_register(
        DOMAIN, 
        SERVICE_CREATE_RESERVATION, 
        create_reservation_service,
        schema=CREATE_RESERVATION_SCHEMA  # Add this line
    )    

    return True
