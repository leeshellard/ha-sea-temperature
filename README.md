# Sea Temperature for Home Assistant

Live sea temperature (and wave height, period and direction) for any coastal
location, with a point-and-click picker. Built with the UK in mind, works worldwide.

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=leeshellard&repository=ha-sea-temperature&category=integration)

## Install (HACS)

Click the button above, or add it by hand:

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/leeshellard/ha-sea-temperature`, category **Integration**.
2. Install **Sea Temperature** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Sea Temperature**.

[![Add the integration to your Home Assistant.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=sea_temperature)

## Adding a location

- **Search by name**: type e.g. `Brighton beach`, then choose a result. Beaches are listed first.
- **Pick on the map**: name it, then drop a pin on the shore or in the sea.

Add the integration again for each extra beach. Each one becomes a device with:

| Entity | Enabled by default |
|---|---|
| Sea temperature | yes |
| Swim comfort (very cold → warm, with a `rough_water` flag) | yes |
| Wave height | yes |
| Wave period | no |
| Wave direction | no |

## How accurate is it?

Data comes from the [Open-Meteo Marine API](https://open-meteo.com/en/docs/marine-weather-api),
which is a **modelled** value on a grid several kilometres wide, not a thermometer in the water.
Offshore it is usually close; right at a shallow beach, bay or estuary it can be off by a few degrees.

Every sensor exposes `distance_to_grid_point_km`, the distance from your chosen point to the grid
point actually used, and an `accuracy_note` if that is large. Points too far inland are rejected.

Open-Meteo's free tier is for non-commercial use. Please follow their terms.

Swim comfort is a guide based on temperature alone and is not safety advice. Always check
local conditions, tides and flags.

## Feedback and issues

Something not working, or a beach that won't add? Please
[open an issue](https://github.com/leeshellard/ha-sea-temperature/issues) and include your Home
Assistant version and any `sea_temperature` lines from **Settings → System → Logs**.

## Roadmap

- Measured readings from nearby buoys (needs data-provider credentials), falling back to the model.
- Higher-resolution UK coastal model.
