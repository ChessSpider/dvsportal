from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from datetime import datetime
from homeassistant.core import callback

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import TIME_MINUTES
import logging
_LOGGER = logging.getLogger(__name__)

DOMAIN = "dvsportal"

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    
    async def async_add_car(new_license_plate):
        """Add new DVSCarSensor."""
        async_add_entities([DVSCarSensor(coordinator, new_license_plate)])

    def update_sensors_callback():
        # license plates
        ha_registered_license_plates = set(hass.data[DOMAIN][config_entry.entry_id]["ha_registered_license_plates"])
        known_license_plates =set()
        if coordinator.data is not None:
            # sometimes coordinator.data is still None, if upstream api is slow..
            known_license_plates = set(coordinator.data.get("known_license_plates", {}).keys())

        new_license_plates = known_license_plates - ha_registered_license_plates

        for new_license_plate in new_license_plates:
            hass.async_create_task(async_add_car(new_license_plate))

        hass.data[DOMAIN][config_entry.entry_id]["ha_registered_license_plates"] = known_license_plates

    async_add_entities([BalanceSensor(coordinator), ActiveReservationsSensor(coordinator)]) # add the default sensors

    coordinator.async_add_listener(update_sensors_callback) # make sure new kentekens are registered
    update_sensors_callback() # add the kentekens at the start
        

class DVSCarSensor(CoordinatorEntity, Entity):

    def __init__(self, coordinator, license_plate):
        super().__init__(coordinator)

        self._license_plate = license_plate
        self._reset_attributes()

    @property
    def unique_id(self) -> str:
        return f"dvsportal_carsensor_{self._license_plate}"

    @property
    def icon(self) -> str:
        return "mdi:car" if self.state == "not present" else "mdi:car-clock"   

    @property
    def device_class(self):
        return "dvs_car_sensor"

    @property
    def name(self):
        return f"Car {self._license_plate}" if self._attributes.get('name') is None else f"{self._attributes.get('name')} ({self._license_plate})"
    
    @property
    def extra_state_attributes(self) -> dict:
        return self._attributes

    def _reset_attributes(self):
        self._attributes = {
            "license_plate": self._license_plate, 
            'name': self.coordinator.data.get("known_license_plates", {}).get(self._license_plate)
        }
        history = self.coordinator.data.get("historic_reservations", {}).get(self._license_plate, {})
        self._attributes.update({f"previous_{k}": v for k, v in history.items()})

    @property
    def state(self):
        reservation = self.coordinator.data.get("active_reservations", {}).get(self._license_plate)
        if reservation is None:
            self._reset_attributes()
            return "not present"
        
        self._attributes.update(reservation)

        now = datetime.now()
        valid_until = datetime.strptime(reservation.get("valid_until", "1900-01-01T00:00:00"), "%Y-%m-%dT%H:%M:%S")
        valid_from = datetime.strptime(reservation.get("valid_from", "1900-01-01T00:00:00"), "%Y-%m-%dT%H:%M:%S")
        
        if valid_until > now and valid_from <= now:
            return "present"
        else:
            return "reserved"
        return "unknown"


class BalanceSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Balance Sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attributes = {}

    @property
    def unique_id(self) -> str:
        return "dvsportal_balance_unique_id"

    @property
    def icon(self) -> str:
        return "mdi:clock"

    @property
    def name(self) -> str:
        return "Guest Parking Balance"

    @property
    def state(self) -> int:
        self._attributes = self.coordinator.data["balance"]
        return self.coordinator.data["balance"]['balance']

    @property
    def extra_state_attributes(self) -> dict:
        return self._attributes

    @property
    def unit_of_measurement(self) -> str:
        return TIME_MINUTES

    @property
    def state_class(self) -> str:
        return "total"

    @property
    def device_class(self) -> str:
        return SensorDeviceClass.DURATION



class ActiveReservationsSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Active Reservations Sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attributes = {}

    @property
    def unique_id(self) -> str:
        return "dvsportal_active_reservations_unique_id"

    @property
    def icon(self) -> str:
        return "mdi:car-multiple"

    @property
    def name(self) -> str:
        return "Reservations"

    @property
    def state(self) -> int:
        active_reservations = [v for k, v in self.coordinator.data.get("active_reservations", {}).items()]

        now = datetime.now()

        active_licenseplates = []
        future_licenseplates = []

        for reservation in active_reservations:
            valid_until = datetime.strptime(reservation.get("valid_until", "1900-01-01T00:00:00"), "%Y-%m-%dT%H:%M:%S")
            valid_from = datetime.strptime(reservation.get("valid_from", "1900-01-01T00:00:00"), "%Y-%m-%dT%H:%M:%S")
            license_plate = reservation.get("license_plate")

            if license_plate:
                if valid_until > now and valid_from <= now:
                    active_licenseplates.append(license_plate)
                else:
                    future_licenseplates.append(license_plate)

        self._attributes = {
            "current_reservations": active_licenseplates,
            "future_reservationsthe": future_licenseplates,
        }
        return  len(active_licenseplates) + len(future_licenseplates)

    @property
    def unit_of_measurement(self) -> str:
        return "reservations"

    @property
    def state_class(self) -> str:
        return "total"

    @property
    def extra_state_attributes(self) -> dict:
        return self._attributes
