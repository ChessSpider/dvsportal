from __future__ import annotations

import asyncio
import logging
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CREATE_RESERVATION_SCHEMA,
    DOMAIN,
    END_RESERVATION_SCHEMA,
    SERVICE_CREATE_RESERVATION,
    SERVICE_END_RESERVATION,
)

_LOGGER = logging.getLogger(__name__)


def _get_target_entry(hass: HomeAssistant, call: ServiceCall) -> ConfigEntry:
    """Resolve the config entry this service call should act on.

    - If `entry_id` is provided, use it.
    - If only one entry for this domain exists, use it.
    - Otherwise raise.
    """
    entry_id = call.data.get("entry_id")
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise HomeAssistantError(f"Invalid entry_id: {entry_id}")
        if (
            entry.state.name != "LOADED"
        ):  # avoid importing ConfigEntryState for a tiny check
            raise HomeAssistantError(f"Entry not loaded: {entry_id}")
        return entry

    entries = hass.config_entries.async_entries(DOMAIN)
    if len(entries) == 1:
        return entries[0]

    raise HomeAssistantError(
        "Multiple DVSPortal entries found; specify entry_id in the service call."
    )


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services (actions)."""

    async def create_reservation_service(call: ServiceCall) -> None:
        entry = _get_target_entry(hass, call)
        runtime = cast("DVSPortalRuntimeData", entry.runtime_data)
        coordinator = runtime.coordinator
        dvs_portal = coordinator.dvs_portal

        entity_id = call.data.get("entity_id")
        license_plate_value = call.data.get("license_plate_value")
        license_plate_name = call.data.get("license_plate_name")
        date_from = call.data.get("date_from")
        date_until = call.data.get("date_until")

        if entity_id:
            state = hass.states.get(entity_id)
            if state is None:
                raise HomeAssistantError(f"Entity not found: {entity_id}")
            license_plate_value = state.attributes.get("license_plate")

        if not license_plate_value:
            raise HomeAssistantError("Missing license_plate_value (or entity_id)")

        try:
            tasks: list[asyncio.Task[object]] = [
                asyncio.create_task(
                    dvs_portal.create_reservation(
                        license_plate_value=license_plate_value,
                        license_plate_name=license_plate_name,
                        date_from=date_from,
                        date_until=date_until,
                    )
                )
            ]
            if license_plate_name:
                tasks.append(
                    asyncio.create_task(
                        dvs_portal.store_license_plate(
                            license_plate=license_plate_value,
                            name=license_plate_name,
                        )
                    )
                )
            await asyncio.gather(*tasks)
        except Exception as ex:  # noqa: BLE001
            _LOGGER.exception("Failed to create reservation")
            raise HomeAssistantError(f"Failed to create reservation: {ex}") from ex
        finally:
            await coordinator.async_request_refresh()

    async def end_reservation_service(call: ServiceCall) -> None:
        entry = _get_target_entry(hass, call)
        runtime = cast("DVSPortalRuntimeData", entry.runtime_data)
        coordinator = runtime.coordinator
        dvs_portal = coordinator.dvs_portal

        entity_id = call.data.get("entity_id")
        if not entity_id:
            raise HomeAssistantError("Missing entity_id")

        state = hass.states.get(entity_id)
        if state is None:
            raise HomeAssistantError(f"Entity not found: {entity_id}")

        reservation_id = state.attributes.get("reservation_id")
        if not reservation_id:
            raise HomeAssistantError(f"No reservation_id on entity: {entity_id}")

        try:
            await dvs_portal.end_reservation(reservation_id=reservation_id)
        except Exception as ex:  # noqa: BLE001
            _LOGGER.exception("Failed to end reservation")
            raise HomeAssistantError(f"Failed to end reservation: {ex}") from ex
        finally:
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_RESERVATION,
        create_reservation_service,
        schema=CREATE_RESERVATION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_END_RESERVATION,
        end_reservation_service,
        schema=END_RESERVATION_SCHEMA,
    )
