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
    _LOGGER.error(f"async_setup_entry 1")
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    existing_sensors = hass.data[DOMAIN][config_entry.entry_id]["car_sensors"]
    
    new_entities = [BalanceSensor(coordinator), ActiveReservationsSensor(coordinator)]
    
    for license_plate in coordinator.data["license_plates"]:
        _LOGGER.error(f"async_setup_entry 2")
        if license_plate not in existing_sensors:
            _LOGGER.error(f"async_setup_entry 3")
            new_sensor = DVSCarSensor(license_plate, coordinator)
            new_entities.append(new_sensor)
            existing_sensors.add(license_plate)
            
    if new_entities:
        _LOGGER.error(f"async_setup_entry 4")
        async_add_entities(new_entities)
        

class DVSCarSensor(CoordinatorEntity, Entity):
    def __init__(self, license_plate, coordinator):
        self._license_plate = license_plate
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        return f"dvsportal_carsensor_{self._license_plate}"

    @property
    def icon(self) -> str:
        return "mdi:car"        

    @property
    def name(self):
        return f"Car {self._license_plate}"

    @property
    def state(self):
        return "present" if self._license_plate in self.coordinator.data["license_plates"] else "not present"


class BalanceSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Balance Sensor."""

    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)

    @property
    def unique_id(self) -> str:
        return "dvsportal_balance_unique_id"

    @property
    def icon(self) -> str:
        return "mdi:car-clock"

    @property
    def name(self) -> str:
        return "Guest Parking Balance"

    @property
    def state(self) -> int:
        return self.coordinator.data["balance"]

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
        return "Active Reservations"

    @property
    def state(self) -> int:
        active_reservations = self.coordinator.data.get("active_reservations", [])
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
            "active_licenseplates": active_licenseplates,
            "future_licenseplates": future_licenseplates,
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
