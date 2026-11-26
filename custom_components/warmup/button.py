"""Button platform for the Warmup integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WarmupConfigEntry
from .coordinator import WarmupCoordinator
from .entity import WarmupLocationEntity, async_run_command, warmup_locations


@dataclass(frozen=True, kw_only=True)
class WarmupLocationButtonEntityDescription(ButtonEntityDescription):
    """Describes a button acting on every room at a Warmup location."""

    # Returns the client method to call with the location id.
    command_fn: Callable[[Any], Callable[[int], None]]


LOCATION_BUTTONS: tuple[WarmupLocationButtonEntityDescription, ...] = (
    WarmupLocationButtonEntityDescription(
        key="all_rooms_frost",
        translation_key="all_rooms_frost",
        command_fn=lambda client: client.set_all_rooms_to_frost,
    ),
    WarmupLocationButtonEntityDescription(
        key="all_rooms_off",
        translation_key="all_rooms_off",
        command_fn=lambda client: client.set_all_rooms_to_off,
    ),
    WarmupLocationButtonEntityDescription(
        key="all_rooms_schedule",
        translation_key="all_rooms_schedule",
        command_fn=lambda client: client.set_all_rooms_to_program,
    ),
    WarmupLocationButtonEntityDescription(
        key="cancel_all_overrides",
        translation_key="cancel_all_overrides",
        command_fn=lambda client: client.cancel_all_overrides,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WarmupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Warmup buttons from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        WarmupLocationButton(coordinator, location_id, name, description)
        for location_id, name in warmup_locations(coordinator).items()
        for description in LOCATION_BUTTONS
    )


class WarmupLocationButton(WarmupLocationEntity, ButtonEntity):
    """A button that acts on every room at a Warmup location."""

    entity_description: WarmupLocationButtonEntityDescription

    def __init__(
        self,
        coordinator: WarmupCoordinator,
        location_id: int,
        name: str,
        description: WarmupLocationButtonEntityDescription,
    ) -> None:
        """Initialise the button for this location."""
        super().__init__(coordinator, location_id, name, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Send the command for every room at the location."""
        command = self.entity_description.command_fn(self.coordinator.client)
        await async_run_command(self.hass, self.coordinator, command, self._location_id)
