"""Constants for the Sea Temperature integration."""

from datetime import timedelta

DOMAIN = "sea_temperature"

CONF_LOCATION_NAME = "name"

UPDATE_INTERVAL = timedelta(minutes=30)

# A grid cell further than this from the requested point means the point is
# effectively inland and we refuse to set it up.
MAX_GRID_DISTANCE_KM = 40.0
# Beyond this the reading is still returned, but flagged as approximate.
WARN_GRID_DISTANCE_KM = 15.0

USER_AGENT = "HomeAssistant-SeaTemperature/0.1 (+https://github.com/leeshellard/ha-sea-temperature)"
