from datetime import timedelta
import logging
import voluptuous as vol
from homeassistant import config_entries, core
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.components.persistent_notification import async_create as async_create_notification

from .dvsportal import DVSPortal, DVSPortalError, DVSPortalAuthError, DVSPortalConnectionError
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dvsportal"

SERVICE_CREATE_RESERVATION = "create_reservation"

CREATE_RESERVATION_SCHEMA = vol.Schema({
    vol.Required("entry_id"): cv.string,
    vol.Required("license_plate_value"): cv.string,
    vol.Optional("license_plate_name"): cv.string,
    vol.Optional("date_from"): cv.datetime,
    vol.Optional("date_until"): cv.datetime,
})

async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up the dvsportal component from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": None,
        "dvs_portal": None,
        "car_sensors": set(),
        'license_plates': set(),
    }

    api_host = entry.data[CONF_HOST]
    identifier = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    user_agent = entry.data.get("user_agent", "HomeAssistant")

    dvs_portal = DVSPortal(
        api_host=api_host,
        identifier=identifier,
        password=password,
        user_agent=user_agent,
    )



    async def async_update_data():
        try:
            await dvs_portal.update()
            return {
                "balance": dvs_portal.balance,
                "active_reservations": dvs_portal.active_reservations,
                "license_plates":  [ ar['license_plate'] for ar in dvs_portal.active_reservations]
            }
        except Exception as e:
            raise UpdateFailed(f"Error communicating with API: {e}")

    def update_sensors_callback():
        """Update sensors based on new data."""
        known_license_plates = set(hass.data[DOMAIN][entry.entry_id]["license_plates"])
        registered_license_plates = set(coordinator.data["license_plates"])

        _LOGGER.error(f"update_sensors_callback 1")
        new_license_plates = len(registered_license_plates - known_license_plates)
        if new_license_plates > 0:
            _LOGGER.error(f"update_sensors_callback 2 {new_license_plates} - unloading ")
            hass.add_job(hass.config_entries.async_forward_entry_unload(entry, "sensor"))
            _LOGGER.error(f"update_sensors_callback 3 - loading ")
            hass.add_job(hass.config_entries.async_forward_entry_setup(entry, "sensor"))
            _LOGGER.error(f"update_sensors_callback 4")

        hass.data[DOMAIN][entry.entry_id]["license_plates"] = registered_license_plates

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="dvsportal",
        update_method=async_update_data,
        update_interval=timedelta(minutes=2),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id].update( {
        "coordinator": coordinator,
        "dvs_portal": dvs_portal,
    })
    coordinator.async_add_listener(update_sensors_callback)

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    

    async def create_reservation_service(call):
        entry_id = call.data.get("entry_id")
        license_plate_value = call.data.get("license_plate_value")
        license_plate_name = call.data.get("license_plate_name")
        date_from = call.data.get("date_from")
        date_until = call.data.get("date_until")
        
        dvs_portal = hass.data[DOMAIN][entry_id]["dvs_portal"]
        try:
            await dvs_portal.create_reservation(
                license_plate_value=license_plate_value,
                license_plate_name=license_plate_name,
                date_from=date_from,
                date_until=date_until
            )
        except DVSPortalError as e:
            _LOGGER.error(f"Failed to create reservation: {e}")
            async_create_notification(hass, f"Failed to create reservation: {e}", "DVSPortal Error", "dvsportal_error")

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_RESERVATION,
        create_reservation_service,
        schema=CREATE_RESERVATION_SCHEMA
    )

    return True
