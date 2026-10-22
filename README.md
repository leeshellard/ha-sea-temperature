# Sea Temperature for Home Assistant

Live sea temperature (and wave height, period and direction) for any coastal
location, with a point-and-click picker. Built with the UK in mind, works worldwide.

## Install (HACS)

1. HACS → ⋮ → **Custom repositories** → add this repository, category **Integration**.
2. Install **Sea Temperature** and restart Home Assistant.
3. **Settings → Devices & services → Add integration → Sea Temperature**.

## Adding a location

- **Search by name**: type e.g. `Brighton beach`, then choose a result. Beaches are listed first.
- **Pick on the map**: name it, then drop a pin on the shore or in the sea.

Add the integration again for each extra beach. Each one becomes a device with:

| Entity | Enabled by default |
|---|---|
| Sea temperature | yes |
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

## Roadmap

- Measured readings from nearby buoys (needs data-provider credentials), falling back to the model.
- Higher-resolution UK coastal model.
