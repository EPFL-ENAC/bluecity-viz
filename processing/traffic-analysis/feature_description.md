I understand the request. Here's a concise reformulation:

## Traffic Simulation Feature for Lausanne

**Goal**: Create an interactive traffic simulation that shows real-time impact of infrastructure changes on city-wide traffic patterns and CO2 emissions.

**Core Functionality**:

- Simulate traffic flow across Lausanne's road network
- Allow users to block/close specific routes (e.g., Grand Pont)
- Calculate ripple effects on traffic patterns
- Estimate CO2 impact using traffic increase as proxy (Δtraffic time = ΔCO2)

**Key Components Needed**:

1. **Graph representation** of road network with traffic weights
2. **Flow algorithm** (e.g., shortest path recalculation when routes blocked)
3. **Baseline traffic data** for normal conditions
4. **Diff calculation** between baseline and modified scenarios
5. **Visual feedback** showing affected routes and congestion levels
6. **Metrics dashboard** displaying traffic increase % and CO2 impact

**Simplified MVP**:

- Use existing road network data
- Model traffic as flow between key points (origins → destinations)
- When user blocks a route: recalculate paths → sum additional distance/time → display %Δ
- Show heatmap of affected areas

**Technical Approach**:

- Graph algorithms for pathfinding (Dijkstra/A\*)
- Store network as weighted graph (nodes = intersections, edges = roads)
- Calculate multiple routes simultaneously for different origin-destination pairs
- Aggregate results for city-wide impact
