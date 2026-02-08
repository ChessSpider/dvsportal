"""Setup car sensors."""

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DVSPortalConfigEntry
from .coordinator import DVSPortalCoordinator


class DVSCarSensor(CoordinatorEntity[DVSPortalCoordinator], SensorEntity):
    """Car reservation state sensor (identified by license plate)."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["not present", "reserved", "present"]

    def __init__(self, config_entry: DVSPortalConfigEntry, license_plate: str) -> None:
        """Register a new car as entity."""
        super().__init__(config_entry.runtime_data.coordinator)

        self._license_plate = license_plate
        self._attr_unique_id = (
            f"dvsportal_{config_entry.entry_id}_carsensor_{license_plate.lower()}"
        )

        self._reset_attributes()
        self._set_state()

    @property
    def icon(self) -> str:
        """Icon reflects reservation state."""
        return "mdi:car" if self.native_value == "not present" else "mdi:car-clock"

    @property
    def name(self) -> str:
        """Human-readable name."""
        name = self.extra_state_attributes.get("name")
        return (
            f"{name} ({self._license_plate})" if name else f"Car {self._license_plate}"
        )

    def _reset_attributes(self) -> None:
        if not self.coordinator.data:
            return

        self._attr_extra_state_attributes = {
            "dvs_entity": "car",
            "license_plate": self._license_plate,
            "name": self.coordinator.data.known_license_plates.get(self._license_plate),
        }

        history = self.coordinator.data.historic_reservations.get(
            self._license_plate, {}
        )
        self._attr_extra_state_attributes.update(
            {f"previous_{k}": v for k, v in history.items()}
        )

    def _set_state(self) -> None:
        if not self.coordinator.data:
            return

        reservation = self.coordinator.data.active_reservations.get(self._license_plate)

        if reservation is None:
            self._attr_native_value = "not present"
            return

        self._attr_extra_state_attributes.update(reservation)

        now = datetime.now()
        valid_from = datetime.fromisoformat(
            reservation["valid_from"].split(".", maxsplit=1)[0]
        )
        valid_until = datetime.fromisoformat(
            reservation["valid_until"].split(".", maxsplit=1)[0]
        )

        self._attr_native_value = (
            "present" if valid_from <= now < valid_until else "reserved"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._reset_attributes()
        self._set_state()
        self.async_write_ha_state()
