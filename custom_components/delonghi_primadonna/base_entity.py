from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .device import DelongiPrimadonna


class DelonghiDeviceEntity:
    """Entity class for the Delonghi devices"""

    _attr_has_entity_name = True
    _attr_should_poll = False  # Push-based, no HA polling needed

    def __init__(self, delongh_device, hass: HomeAssistant):
        """Init entity with the device"""
        self._attr_unique_id = (
            f'{delongh_device.mac}_'
            f'{self.__class__.__name__}'
        )
        self.device: DelongiPrimadonna = delongh_device
        self.hass = hass

    async def async_added_to_hass(self) -> None:
        """Subscribe to device state updates via dispatcher."""
        # Call parent (RestoreEntity etc.) if present
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.device.signal_state_updated,
                self._handle_state_update,
            )
        )

    @callback
    def _handle_state_update(self) -> None:
        """Handle updated data from device."""
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Shared device info information"""
        return {
            'identifiers': {(DOMAIN, self.device.mac)},
            'connections': {(dr.CONNECTION_NETWORK_MAC, self.device.mac)},
            'name': self.device.name,
            'manufacturer': 'Delonghi',
            'model': self.device.model,
        }
