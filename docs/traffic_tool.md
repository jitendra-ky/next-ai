# Traffic Analysis Tool

## Overview

This module estimates real-time traffic congestion for a selected ward using OpenStreetMap and the TomTom Traffic API.

---

## Workflow

User selects Ward

↓

Load Ward Polygon

↓

Download Road Network from OpenStreetMap

↓

Filter Major Roads
 
↓

Generate Midpoints

↓

Query TomTom Traffic API

↓

Compute Ward Statistics

↓

Return Traffic Report

---

## Logic

1. Read the ward polygon from the GeoJSON dataset.
2. Download the road network using OSMnx.
3. Filter only major road segments.
4. Compute the midpoint of each road segment.
5. Query the TomTom Flow Segment API for every midpoint.
6. Calculate the congestion percentage for each road segment using:

```text
Congestion (%) = (1 - Current Speed / Free Flow Speed) × 100
```

where:

- **Current Speed** = Real-time speed reported by the TomTom Traffic API.
- **Free Flow Speed** = Expected speed under uncongested traffic conditions.

7. Compute ward-level metrics using a road-length weighted average.

### Weighted Average Speed

```text
Average Speed =
Σ(Speed × Road Length) / Σ(Road Length)
```

### Weighted Average Congestion

```text
Average Congestion =
Σ(Congestion × Road Length) / Σ(Road Length)
```

Road-length weighting ensures that longer road segments contribute proportionally more to the overall ward traffic statistics than shorter road segments.

---
## Technologies

- GeoPandas
- OSMnx
- TomTom Traffic API

---
## Output

Example

{
  "ward":15,
  "average_speed":31.4,
  "average_congestion":22.7,
  "roads":54,
  "closed_roads":1,
  "confidence":0.94
}