"""Sensor platform for CMTEB Termoficare."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re

import aiohttp

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import (
    CONF_BLOCK,
    CONF_PUNCT_TERMIC,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_STREET,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    URL_CMTEB,
)
from .parser import CmtebStatus, parse_cmteb_status

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CMTEB sensors from a config entry."""
    coordinator = CmtebDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()
    async_add_entities([CmtebStatusSensor(coordinator)])


def _slug(value: str) -> str:
    """Create a stable slug for entity IDs."""
    slug = re.sub(r"[^\w\s]", "", (value or "").lower().strip())
    slug = re.sub(r"\s+", "_", slug).strip("_")
    if not slug:
        return "address"
    if not slug[0].isalpha():
        return f"address_{slug}"
    return slug


class CmtebDataUpdateCoordinator(DataUpdateCoordinator[CmtebStatus]):
    """Fetch CMTEB data for one config entry."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._config_entry = config_entry
        self._street = config_entry.options.get(CONF_STREET) or config_entry.data.get(CONF_STREET, "")
        self._block = config_entry.options.get(CONF_BLOCK) or config_entry.data.get(CONF_BLOCK, "")
        self._punct_termic = config_entry.options.get(CONF_PUNCT_TERMIC) or config_entry.data.get(CONF_PUNCT_TERMIC, "")
        scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES,
            config_entry.data.get(CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"CMTEB {self._street} {self._block}",
            update_interval=timedelta(minutes=scan_interval),
        )

    async def _async_update_data(self) -> CmtebStatus:
        """Fetch and parse the CMTEB status page."""
        session = async_get_clientsession(self.hass)
        headers = {
            "User-Agent": "HomeAssistant CMTEB Termoficare/2.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
        }
        try:
            async with session.get(URL_CMTEB, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                html = await response.text()
            status = parse_cmteb_status(html, self._street, self._block, self._punct_termic)
            _LOGGER.debug(
                "CMTEB parsed status for %s %s: state=%s match=%s punct=%s status_type=%s eta=%s",
                self._street,
                self._block,
                status.state,
                status.match_found,
                status.punct_termic,
                status.status_type,
                status.eta,
            )
            return status
        except Exception as err:  # noqa: BLE001 - expose integration errors as sensor state.
            _LOGGER.exception("Failed to update CMTEB status for %s %s", self._street, self._block)
            return CmtebStatus(state="error", match_found=False, record_text=str(err))


class CmtebStatusSensor(CoordinatorEntity[CmtebDataUpdateCoordinator], SensorEntity):
    """Current CMTEB hot water status for one address."""

    _attr_icon = "mdi:water-boiler-alert"

    def __init__(self, coordinator: CmtebDataUpdateCoordinator) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator)
        config_entry = coordinator._config_entry
        self._street = coordinator._street
        self._block = coordinator._block
        self._punct_termic = coordinator._punct_termic
        address_slug = _slug(f"{self._street}_{self._block}")
        self._attr_unique_id = f"{config_entry.entry_id}_hot_water_status"
        self._attr_name = f"CMTEB Hot Water Status {address_slug}"

    @property
    def native_value(self) -> str:
        """Return the sensor state."""
        return self.coordinator.data.state if self.coordinator.data else "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return detailed CMTEB row attributes."""
        attrs = self._base_attributes()
        if self.coordinator.data:
            attrs.update(self.coordinator.data.as_attributes())
        attrs["last_checked"] = datetime.now().astimezone().isoformat(timespec="seconds")
        attrs["scan_interval_minutes"] = int(self.coordinator.update_interval.total_seconds() / 60)
        return attrs

    def _base_attributes(self) -> dict[str, object]:
        """Return common attributes."""
        return {
            "street": self._street,
            "block": self._block,
            "punct_termic_configured": self._punct_termic,
            "source_url": URL_CMTEB,
        }
