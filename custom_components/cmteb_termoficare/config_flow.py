"""Config flow for CMTEB Termoficare."""

from __future__ import annotations

import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_BLOCK,
    CONF_PUNCT_TERMIC,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_STREET,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)


def _slug(text: str) -> str:
    """Create a valid unique-id fragment."""
    if not text:
        return ""
    slug = re.sub(r"[^\w\s]", "", text.lower().strip())
    return re.sub(r"\s+", "_", slug).strip("_")


def _unique_id(street: str, block: str, punct_termic: str = "") -> str:
    """Create a stable unique ID for a configured address."""
    parts = ["cmteb", _slug(street), _slug(block)]
    punct_slug = _slug(punct_termic)
    if punct_slug:
        parts.append(punct_slug)
    return "_".join(part for part in parts if part)


def _schema(defaults: dict[str, object] | None = None) -> vol.Schema:
    """Return the user/options schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_STREET, default=defaults.get(CONF_STREET, "")): cv.string,
            vol.Required(CONF_BLOCK, default=defaults.get(CONF_BLOCK, "")): cv.string,
            vol.Optional(CONF_PUNCT_TERMIC, default=defaults.get(CONF_PUNCT_TERMIC, "")): cv.string,
            vol.Required(
                CONF_SCAN_INTERVAL_MINUTES,
                default=defaults.get(CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        }
    )


class CMTEBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CMTEB Termoficare."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            street = user_input.get(CONF_STREET, "").strip()
            block = user_input.get(CONF_BLOCK, "").strip()
            if not street:
                errors[CONF_STREET] = "street_required"
            if not block:
                errors[CONF_BLOCK] = "block_required"

            if not errors:
                punct_termic = user_input.get(CONF_PUNCT_TERMIC, "").strip()
                unique_id = _unique_id(street, block, punct_termic)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"CMTEB {street} {block}",
                    data={
                        CONF_STREET: street,
                        CONF_BLOCK: block,
                        CONF_PUNCT_TERMIC: punct_termic,
                        CONF_SCAN_INTERVAL_MINUTES: user_input[CONF_SCAN_INTERVAL_MINUTES],
                    },
                )

        return self.async_show_form(step_id="user", data_schema=_schema(), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return options flow handler."""
        return CMTEBOptionsFlow()


class CMTEBOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle options flow for CMTEB Termoficare."""

    async def async_step_init(self, user_input=None):
        """Manage options."""
        errors: dict[str, str] = {}
        defaults = {
            CONF_STREET: self.config_entry.options.get(CONF_STREET, self.config_entry.data.get(CONF_STREET, "")),
            CONF_BLOCK: self.config_entry.options.get(CONF_BLOCK, self.config_entry.data.get(CONF_BLOCK, "")),
            CONF_PUNCT_TERMIC: self.config_entry.options.get(
                CONF_PUNCT_TERMIC, self.config_entry.data.get(CONF_PUNCT_TERMIC, "")
            ),
            CONF_SCAN_INTERVAL_MINUTES: self.config_entry.options.get(
                CONF_SCAN_INTERVAL_MINUTES,
                self.config_entry.data.get(CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES),
            ),
        }
        if user_input is not None:
            street = user_input.get(CONF_STREET, "").strip()
            block = user_input.get(CONF_BLOCK, "").strip()
            if not street:
                errors[CONF_STREET] = "street_required"
            if not block:
                errors[CONF_BLOCK] = "block_required"

            if errors:
                return self.async_show_form(step_id="init", data_schema=_schema(defaults), errors=errors)

            return self.async_create_entry(
                title="",
                data={
                    CONF_STREET: street,
                    CONF_BLOCK: block,
                    CONF_PUNCT_TERMIC: user_input.get(CONF_PUNCT_TERMIC, "").strip(),
                    CONF_SCAN_INTERVAL_MINUTES: user_input[CONF_SCAN_INTERVAL_MINUTES],
                },
            )

        return self.async_show_form(step_id="init", data_schema=_schema(defaults))
