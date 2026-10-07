"""Vitrea Scenarios integration: run V-Box scenarios from Home Assistant."""
from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .client import VitreaClient, VitreaError
from .const import ATTR_SCENARIO_ID, DOMAIN, SERVICE_RUN_SCENARIO

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

RUN_SCENARIO_SCHEMA = vol.Schema(
    {vol.Required(ATTR_SCENARIO_ID): vol.All(vol.Coerce(int), vol.Range(min=0, max=255))}
)

type VitreaConfigEntry = ConfigEntry[VitreaClient]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    async def run_scenario(call: ServiceCall) -> None:
        entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
        ]
        if not entries:
            raise HomeAssistantError("Vitrea Scenarios is not configured")
        client: VitreaClient = entries[0].runtime_data
        scenario_id = call.data[ATTR_SCENARIO_ID]
        try:
            await client.run_scenario(scenario_id)
        except VitreaError as e:
            raise HomeAssistantError(f"Failed to run Vitrea scenario {scenario_id}: {e}") from e

    hass.services.async_register(DOMAIN, SERVICE_RUN_SCENARIO, run_scenario, schema=RUN_SCENARIO_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: VitreaConfigEntry) -> bool:
    entry.runtime_data = VitreaClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VitreaConfigEntry) -> bool:
    return True
