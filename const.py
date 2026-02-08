"""Setup dvsportal."""

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

DOMAIN = "dvsportal"

SERVICE_CREATE_RESERVATION = "create_reservation"

CREATE_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id"): cv.entity_id,
        vol.Optional("entry_id"): cv.string,
        vol.Optional("license_plate_value"): cv.string,
        vol.Optional("license_plate_name"): cv.string,
        vol.Optional("date_from"): cv.datetime,
        vol.Optional("date_until"): cv.datetime,
    }
)


SERVICE_END_RESERVATION = "end_reservation"

END_RESERVATION_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
    }
)
