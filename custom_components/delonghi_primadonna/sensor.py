"""Sensor entities for Delonghi Primadonna."""

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .base_entity import DelonghiDeviceEntity
from .const import DOMAIN, MACHINE_STATUSES, ECAM_MACHINE_STATE, ECAM_ALARM
from .device import DelongiPrimadonna, NOZZLE_STATE
from .machine_switch import MachineSwitch, MachineAlarm


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """Register sensor entities for a config entry."""

    delongh_device: DelongiPrimadonna = hass.data[DOMAIN][entry.unique_id]
    async_add_entities(
        [
            DelongiPrimadonnaNozzleSensor(delongh_device, hass),
            DelongiPrimadonnaStatusSensor(delongh_device, hass),
            DelongiPrimadonnaSwitchesSensor(delongh_device, hass),
            DelongiPrimadonnaAlarmSensor(delongh_device, hass),
            DelongiPrimadonnaProgressSensor(delongh_device, hass),
        ]
    )
    return True


class DelongiPrimadonnaNozzleSensor(
    DelonghiDeviceEntity, SensorEntity, RestoreEntity
):
    """
    Check the connected steam nozzle
    Steam or milk pot
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = 'nozzle_status'

    _attr_options = list(NOZZLE_STATE.values())

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = last_state.state

    @property
    def native_value(self):
        return self.device.steam_nozzle

    @property
    def entity_category(self, **kwargs: Any) -> None:
        """Return the category of the entity."""
        return EntityCategory.DIAGNOSTIC

    @property
    def icon(self):
        result = 'mdi:coffee'
        if self.device.steam_nozzle == "detached":
            result = 'mdi:coffee-off-outline'
        if self.device.steam_nozzle.startswith("milk"):
            result = 'mdi:coffee-outline'
        return result


class DelongiPrimadonnaStatusSensor(
    DelonghiDeviceEntity, SensorEntity, RestoreEntity
):
    """
    Shows the actual device status
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = 'Status'
    _attr_options = MACHINE_STATUSES

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = last_state.state

    @property
    def native_value(self):
        return self.device.status

    @property
    def extra_state_attributes(self):
        """Expose raw machine state and detailed info."""
        state_name = ECAM_MACHINE_STATE.get(
            self.device.machine_state,
            f'Unknown({self.device.machine_state})',
        )
        attrs = {
            'machine_state': state_name,
            'machine_state_raw': self.device.machine_state,
            'progress': self.device.progress,
            'percentage': self.device.percentage,
        }
        if self.device.active_alarms:
            attrs['alarms'] = [a.value for a in self.device.active_alarms]
        return attrs

    @property
    def entity_category(self, **kwargs: Any) -> None:
        """Return the category of the entity."""
        return EntityCategory.DIAGNOSTIC

    @property
    def icon(self):
        result = 'mdi:thumb-up-outline'
        return result


class DelongiPrimadonnaSwitchesSensor(
    DelonghiDeviceEntity, SensorEntity, RestoreEntity
):
    """Show active machine switches."""

    # Changed from ENUM to None - multiple switches can be active simultaneously
    # returning comma-separated values which is not compatible with ENUM type
    _attr_device_class = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = 'switches'

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = last_state.state

    @property
    def native_value(self):
        if not self.device.active_switches:
            return 'none'
        return ', '.join(s.value for s in self.device.active_switches)

    @property
    def entity_category(self, **kwargs: Any) -> None:
        """Return the category of the entity."""
        return EntityCategory.DIAGNOSTIC


class DelongiPrimadonnaAlarmSensor(
    DelonghiDeviceEntity, SensorEntity, RestoreEntity
):
    """Show active machine alarms."""

    _attr_device_class = None
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = 'Alarms'
    _attr_icon = 'mdi:alert-circle-outline'

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = last_state.state

    @property
    def native_value(self):
        if not self.device.active_alarms:
            return 'none'
        return ', '.join(a.value for a in self.device.active_alarms)

    @property
    def extra_state_attributes(self):
        """Expose raw alarm bitmask."""
        return {
            'alarm_mask': f'0x{self.device.alarm_mask:04x}',
            'alarm_count': len(self.device.active_alarms),
        }

    @property
    def icon(self):
        if self.device.active_alarms:
            return 'mdi:alert-circle'
        return 'mdi:alert-circle-outline'


class DelongiPrimadonnaProgressSensor(
    DelonghiDeviceEntity, SensorEntity, RestoreEntity
):
    """Show beverage dispensing progress percentage."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = 'Progress'
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = 'mdi:progress-clock'

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._attr_native_value = int(float(last_state.state))
            except (ValueError, TypeError):
                pass

    @property
    def native_value(self):
        return self.device.percentage
