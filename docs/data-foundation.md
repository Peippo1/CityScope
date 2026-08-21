# CityScope data foundation

## Canonical contract

CityScope accepts a small stable mobility-trip core: city, dataset and snapshot IDs, movement mode, source location IDs, origin/destination coordinates, timestamps, duration, and source extension properties. Source adapters own their native schemas; shared temporal, H3, aggregation, and DuckDB code operates only on the canonical columns.

H3 cells are the canonical analytical geography. Station IDs, named places, and future source zones are resolved into H3 before shared analytics. A future zone-based adapter such as NYC TLC can use zone polygon coverage to derive H3 cells without changing the analytics or future MCP contract.

## London production snapshot

The current production snapshot is the complete May 2026 period, split across two official TfL files:

- `443JourneyDataExtract01May2026-16May2026.csv`
- `444JourneyDataExtract17May2026-31May2026.csv`

TfL publishes Santander Cycle Hire journey data by week and documents journey ID, bike ID, start/end dates and times, and start/end docking station IDs. The snapshot uses the authoritative BikePoint feed for station coordinates. Source URLs, checksums, row reconciliation, quarantine counts, transformation version, and generated-artifact hash are stored in `data/metadata/london-cycling-production.json` after running the production build.

TfL attribution is displayed in the application as: `Data provided by Transport for London`. Historical data is explicitly labelled as a snapshot and is not presented as live activity.

## Citi Bike portability check

The Citi Bike system publishes trip histories containing ride ID, timestamps, station IDs, coordinates, and member/casual status. The portability fixture maps these fields into the same canonical trip columns and preserves `rideable_type` and `member_casual` as source extensions. The shared temporal, H3, and aggregate functions process the fixture without NYC-specific branches.

Citi Bike data is subject to the NYCBS Data Use Policy. It is not exposed as a finished CityScope city in this slice.
