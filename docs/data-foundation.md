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

## Matched US production snapshots

CityScope ingests the official May 2026 Citi Bike, Divvy, and Capital Bikeshare archives through one validated source-family adapter. ZIP members are read in bounded chunks. Source-local timestamps are localized using each city registry timezone before being converted to UTC for storage; hour, weekday, weekend, and May-window checks remain local to the city.

The verified builds reconcile as follows:

| City | Source rows | Accepted | Rejected |
| --- | ---: | ---: | ---: |
| New York City | 4,694,878 | 4,680,767 | 14,111 |
| Chicago | 653,704 | 653,075 | 629 |
| Washington, DC | 592,555 | 588,599 | 3,956 |

Rows are excluded for malformed timestamps, starts outside the May 1-31 local window, missing or out-of-city coordinates, non-positive durations, duplicate trip IDs, or invalid H3 assignments. Each exclusion has one reason in the city quarantine artifact and metadata manifest. Dockless trips with valid coordinates remain in mobility metrics; null station IDs remain null and therefore do not create a fake active station in the station-normalized denominator.

The generated manifests pin the direct archive URL, archive SHA-256, artifact SHA-256, timezone, licence reference, transformation version, and exclusion counts. Citi Bike is governed by the NYCBS Data Use Policy, Divvy by the Divvy Data License Agreement, and Capital Bikeshare by its Data License Agreement.
