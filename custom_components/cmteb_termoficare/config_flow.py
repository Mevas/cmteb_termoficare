"""Config flow for CMTEB Termoficare."""

from __future__ import annotations

import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN


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


def _schema(defaults: dict[str, str] | None = None) -> vol.Schema:
    """Return the user/options schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required("street", default=defaults.get("street", "")): cv.string,
            vol.Required("block", default=defaults.get("block", "")): cv.string,
            vol.Optional("punct_termic", default=defaults.get("punct_termic", "")): cv.string,
        }
    )


class CMTEBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CMTEB Termoficare."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            street = user_input.get("street", "").strip()
            block = user_input.get("block", "").strip()
            if not street:
                errors["street"] = "street_required"
            if not block:
                errors["block"] = "block_required"

            if not errors:
                punct_termic = user_input.get("punct_termic", "").strip()
                unique_id = _unique_id(street, block, punct_termic)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"CMTEB {street} {block}",
                    data={
                        "street": street,
                        "block": block,
                        "punct_termic": punct_termic,
                    },
                )

        return self.async_show_form(step_id="user", data_schema=_schema(), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return options flow handler."""
        return CMTEBOptionsFlow(config_entry)


class CMTEBOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for CMTEB Termoficare."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        errors: dict[str, str] = {}
        defaults = {
            "street": self.config_entry.options.get("street", self.config_entry.data.get("street", "")),
            "block": self.config_entry.options.get("block", self.config_entry.data.get("block", "")),
            "punct_termic": self.config_entry.options.get(
                "punct_termic", self.config_entry.data.get("punct_termic", "")
            ),
        }
        if user_input is not None:
            street = user_input.get("street", "").strip()
            block = user_input.get("block", "").strip()
            if not street:
                errors["street"] = "street_required"
            if not block:
                errors["block"] = "block_required"

            if errors:
                return self.async_show_form(step_id="init", data_schema=_schema(defaults), errors=errors)

            return self.async_create_entry(
                title="",
                data={
                    "street": street,
                    "block": block,
                    "punct_termic": user_input.get("punct_termic", "").strip(),
                },
            )

        return self.async_show_form(step_id="init", data_schema=_schema(defaults))
