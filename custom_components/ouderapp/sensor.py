"""Compact counters and a historical last-success timestamp."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OuderAppCoordinator
from .entity import OuderAppEntity

COUNTERS = ("children_count", "unread_messages", "unread_news")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[OuderAppCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [OuderAppCounter(entry.runtime_data, entry, key) for key in COUNTERS]
        + [OuderAppLastSuccess(entry.runtime_data, entry, "last_success")]
    )


class OuderAppCounter(OuderAppEntity, SensorEntity):
    def __init__(self, coordinator: OuderAppCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator, entry, key)
        source = {
            "children_count": "timeline",
            "unread_messages": "messages",
            "unread_news": "news",
        }.get(key)
        if source:
            self._attr_extra_state_attributes = {
                "custom_ui_more_info": "more-info-ouderapp",
                "ouderapp_config_entry_id": entry.entry_id,
                "ouderapp_source": source,
            }

    @property
    def native_value(self) -> int | None:
        value = (self.coordinator.data or {}).get(self.translation_key)
        return value if type(value) is int and value >= 0 else None


class OuderAppLastSuccess(OuderAppEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        return self.coordinator.last_success
