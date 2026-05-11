# Candidate-stops YAMLs

One YAML per school. `build_bsd_dataset.py` reads these as the only
hand-curated input — everything else (snapped lat/lng, distance matrix,
optimized route ordering, road-snapped polylines, validated geometry) is
computed by the build script using the Google Maps + OR-Tools toolchain.

## Schema

```yaml
# School identity
dataset_id: bellevue_elementary          # filename of the output JSON (minus .json)
school_name: Clyde Hill Elementary
school_level: elementary                 # "elementary" | "middle" | "high"
school_address: "9601 NE 32nd St, Clyde Hill, WA 98004"
school_lat: 47.6235                      # optional — if absent, build script geocodes
school_lng: -122.2198                    # optional — if absent, build script geocodes

# Provenance
source_name: "Bellevue School District public route maps + ACS 2022 5-year"
source_url: "https://bsd405.org/departments/transportation/"
source_version: "2025-26 school year"
source_notes: >
  Stops are taken from BSD's public route documents where verified, and
  otherwise inferred from catchment neighborhoods. Rider estimates derived
  from ACS census tract child counts × zone peak_demand_multiplier.

# Optimization parameters
bus_capacity: 72                         # seats per bus
max_vehicles: 4                          # generous; solver picks fewer
departure_window: "07:30-08:15"          # for traffic_model timing
peak_window_label: "07:00-09:00"         # human-readable peak window

# Zones — used both for "before" baseline (one route per zone) and for
# ridership weighting. Keep the polygon coarse; it's a bucket, not a hull.
zones:
  - zone_id: Z1
    name: "North Bellevue"
    polygon:
      - [47.645, -122.190]
      - [47.645, -122.215]
      - [47.618, -122.215]
      - [47.618, -122.190]
    peak_demand_multiplier: 1.00

  - zone_id: Z2
    name: "West Bellevue / Medina"
    polygon: [...]
    peak_demand_multiplier: 0.85

# Traffic context per zone — fills the Dataset.traffic_context section
traffic_context:
  notes: "Modeled morning peak. Z1 sees school-zone congestion; Z2 is quieter."
  zones:
    Z1: { congestion_level: "medium", peak_delay_minutes: 3.5 }
    Z2: { congestion_level: "low",    peak_delay_minutes: 1.5 }

# Demand context — fills the Dataset.demand_context section
demand_context:
  total_enrolled: 470
  bus_eligible_pct: 0.62
  notes: "Enrollment from OSPI 2024-25 report card; eligibility from BSD policy."

# Candidate stops — one entry per intersection. Build script snaps lat/lng
# to nearest road, computes ridership via ACS × zone multiplier, and
# assigns the stop to a route via the VRP solver.
stops:
  - name: "NE 24th St & 108th Ave NE"
    lat: 47.6389
    lng: -122.2023
    zone_id: Z1
    riders_acs_tract: "53033041901"      # ACS 2022 5-year tract id
    riders_tract_children: 312           # children aged 5-11 in tract
    source: "BSD 2025-26 Transportation, route 14 PDF p.2"
    confidence: verified                  # verified | approximate | interpolated
    notes: "Northbound morning pickup"

  - name: "Bellevue Way NE & NE 12th St"
    zone_id: Z3
    riders_acs_tract: "53033025301"
    riders_tract_children: 248
    source: "Inferred — central catchment intersection"
    confidence: approximate
    notes: ""
```

## Ridership derivation (Q4(b) in the grilled plan)

Per stop, `estimated_riders = round(
  riders_tract_children
  × demand_context.bus_eligible_pct
  × zones[zone_id].peak_demand_multiplier
  ÷ stops_in_same_tract
)`. The build script computes this; do not pre-fill `estimated_riders` in
the YAML.

## What the build script does NOT need from the YAML

- `estimated_riders` per stop (computed)
- `total_estimated_riders` aggregate (computed)
- Per-zone `current_capacity` (computed from VRP output)
- Any route / route geometry / optimized scenario (computed)

The YAML is intentionally minimal — anything that can be computed from
public data + Google Maps + the VRP solver is.
