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
    vol.Optional("entity_id"): cv.entity_id,
    vol.Optional("entry_id"): cv.string,
    vol.Optional("license_plate_value"): cv.string,
    vol.Optional("license_plate_name"): cv.string,
    vol.Optional("date_from"): cv.datetime,
    vol.Optional("date_until"): cv.datetime,
})

SERVICE_END_RESERVATION = "end_reservation"

END_RESERVATION_SCHEMA = vol.Schema({
    vol.Required("entity_id"): cv.entity_id,
})

async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up the dvsportal component from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": None,
        "dvs_portal": None,
        'ha_registered_license_plates': set(), # license plates registered
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
                "default_code": dvs_portal.default_code,
                "default_type_id": dvs_portal.default_type_id,
                "balance": dvs_portal.balance,
                "active_reservations": dvs_portal.active_reservations,
                "known_license_plates": dvs_portal.known_license_plates
            }
        except Exception as e:
            raise UpdateFailed(f"Error communicating with API: {e}")

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

    await coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    

    async def create_reservation_service(call):
        entity_id = call.data.get("entity_id")
        entry_id = call.data.get("entry_id", list(hass.data[DOMAIN].keys())[0] if len(hass.data[DOMAIN]) == 1 else None)
        license_plate_value = call.data.get("license_plate_value")
        license_plate_name = call.data.get("license_plate_name")
        date_from = call.data.get("date_from")
        date_until = call.data.get("date_until")
        
        if entity_id:
            entity = hass.states.get(entity_id)
            if entity is None:
                _LOGGER.error(f"Entity {entity_id} not found")
                return
            license_plate_value = entity.attributes.get("license_plate")

        if entry_id is None:
            _LOGGER.error("No DVSPortal registration selected")
            return

        dvs_portal = hass.data[DOMAIN][entry_id]["dvs_portal"]
        
        try:
            await dvs_portal.create_reservation(
                license_plate_value=license_plate_value,
                license_plate_name=license_plate_name,
                date_from=date_from,
                date_until=date_until
            )
        except Exception as e:
            _LOGGER.error(f"Failed to create reservation: {e}")
        finally:
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_RESERVATION,
        create_reservation_service,
        schema=CREATE_RESERVATION_SCHEMA
    )

    async def end_reservation_service(call):
        entity_id = call.data.get("entity_id")
        entity = hass.states.get(entity_id)
        
        if entity is None:
            _LOGGER.error(f"Entity {entity_id} not found")
            return

        reservation_id = entity.attributes.get("reservation_id")
        
        if reservation_id is None:
            _LOGGER.error(f"No reservation_id found in entity {entity_id}")
            return

        dvs_portal = hass.data[DOMAIN][entry.entry_id]["dvs_portal"]
        
        try:
            await dvs_portal.end_reservation(reservation_id=reservation_id)
        except Exception as e:
            _LOGGER.error(f"Failed to end reservation: {e}")
        finally: 
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_END_RESERVATION,
        end_reservation_service,
        schema=END_RESERVATION_SCHEMA
    )

    return True
