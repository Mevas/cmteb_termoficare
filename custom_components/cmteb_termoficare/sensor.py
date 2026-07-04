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

from .const import URL_CMTEB
from .parser import CmtebStatus, parse_cmteb_status

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CMTEB sensors from a config entry."""
    async_add_entities([CmtebStatusSensor(config_entry)], update_before_add=True)


def _slug(value: str) -> str:
    """Create a stable slug for entity IDs."""
    slug = re.sub(r"[^\w\s]", "", (value or "").lower().strip())
    slug = re.sub(r"\s+", "_", slug).strip("_")
    if not slug:
        return "address"
    if not slug[0].isalpha():
        return f"address_{slug}"
    return slug


class CmtebStatusSensor(SensorEntity):
    """Current CMTEB hot water status for one address."""

    _attr_icon = "mdi:water-boiler-alert"

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the status sensor."""
        self._config_entry = config_entry
        self._street = config_entry.options.get("street") or config_entry.data.get("street", "")
        self._block = config_entry.options.get("block") or config_entry.data.get("block", "")
        self._punct_termic = config_entry.options.get("punct_termic") or config_entry.data.get("punct_termic", "")
        self._state = "unknown"
        self._available = True
        self._attrs: dict[str, object] = {}
        address_slug = _slug(f"{self._street}_{self._block}")
        self._attr_unique_id = f"{config_entry.entry_id}_hot_water_status"
        self._attr_name = f"CMTEB Hot Water Status {address_slug}"

    @property
    def native_value(self) -> str:
        """Return the sensor state."""
        return self._state

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return self._available

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return detailed CMTEB row attributes."""
        return self._attrs

    async def async_update(self) -> None:
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
            self._apply_status(status)
            self._available = True
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
        except Exception as err:  # noqa: BLE001 - expose integration errors as sensor state.
            _LOGGER.exception("Failed to update CMTEB status for %s %s", self._street, self._block)
            self._available = False
            self._state = "error"
            self._attrs = self._base_attributes()
            self._attrs.update({"error": str(err), "last_error_at": datetime.now().astimezone().isoformat(timespec="seconds")})

    def _apply_status(self, status: CmtebStatus) -> None:
        """Apply parsed status to entity state and attributes."""
        self._state = status.state
        self._attrs = self._base_attributes()
        self._attrs.update(status.as_attributes())
        self._attrs["last_checked"] = datetime.now().astimezone().isoformat(timespec="seconds")

    def _base_attributes(self) -> dict[str, object]:
        """Return common attributes."""
        return {
            "street": self._street,
            "block": self._block,
            "punct_termic_configured": self._punct_termic,
            "source_url": URL_CMTEB,
        }
