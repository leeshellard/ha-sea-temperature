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

## Measured buoy data (optional)

If a Regional Coastal Monitoring Programme wave buoy that reports sea temperature is close to your
beach, the integration can use its **measured** reading instead of the model, falling back to the
model when no recent buoy is close enough. Wave values come from the buoy too when it reports them.

1. Request a free API key on the [CCO API page](https://coastalmonitoring.org/ccoresources/api/)
   ("Obtaining an API key for your own service"). You give them a domain; keys only work with the
   domain they were issued for.
2. In Home Assistant open **Settings → Devices & services → Sea Temperature → Configure** on your
   beach, then enter the key, the same domain, and the furthest buoy distance you will accept
   (default 25 km).
3. The sensors then show `source`, `buoy`, `buoy_distance_km` and `model_temperature` so you can see
   what you are looking at. Buoys with no reading in the last 3 hours are ignored.

Leave the key blank to turn it off. In testing, nearby buoys read within about 1 °C of the model in spot checks.

Real time data from the buoys is from the
[Regional Coastal Monitoring Programme](https://coastalmonitoring.org/), made freely available
under the Open Government Licence. These are real-time data and are not quality-controlled.

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

- Higher-resolution UK coastal model.
