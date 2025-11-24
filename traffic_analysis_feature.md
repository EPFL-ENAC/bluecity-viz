Traffic Analysis Workflow

1. Opening Traffic Analysis
   Click "Traffic Analysis" in Resources Panel → Opens traffic panel in Map Controls
   Automatically loads the graph edges (gray base layer) and generates 1000 random origin-destination pairs
2. Removing Edges (Optional)
   Click on any edge in the visualization → Adds it to "Removed Edges" list
   Edges are highlighted on hover (cursor changes to pointer)
   Removed edges shown as black dashed lines on top of all other layers
   Remove edges from the list by clicking the X button
   Clear all removed edges with the trash icon
3. Calculating Routes
   Click "Calculate Routes" → Computes shortest paths for the OD pairs
   First calculation shows "Edge Usage Frequency" visualization (purple/green colors)
   Legend appears showing the frequency scale
4. Recalculating with Removed Edges
   After removing edges, click "Calculate Routes" again
   Now multiple visualization layers are available:
   - Edge Usage Frequency: Shows relative usage (0-100%, purple Viridis scale)
   - CO₂ Emissions: Shows total CO₂ emissions per edge in grams (purple Viridis scale)
   - Traffic Change (Delta): Shows vehicle count differences (blue ↔ red, RdBu diverging scale)
   - CO₂ Emissions Change: Shows CO₂ emission differences in grams (blue ↔ red, RdBu diverging scale)
     All visualizations use the same data, just displayed differently
     Impact Statistics panel appears showing detailed metrics about the impact of removed edges including CO₂ emissions
5. Understanding Impact Statistics
   The Impact Statistics panel shows comprehensive metrics:
   - Overview: Total routes, affected routes count and percentage, failed routes
   - Total Impact: Cumulative additional distance, time, and CO₂ emissions across all affected routes
   - Average Impact: Mean detour per affected route with percentage increases for distance, time, and CO₂
   - Maximum Impact: Worst-case detour for any single route including maximum CO₂ increase
     Panel is expandable/collapsible for better space management
6. Switching Visualizations
   Select between available layers in the "Visualization Layers" list
   Active layer highlighted with primary color and radio button
   Legend updates automatically to match selected visualization
   Can switch back and forth - both scales are preserved
   Impact Statistics remain visible regardless of selected visualization
7. Regenerating Scenarios
   Click "Generate New OD" → Creates new random origin-destination pairs
   Clears previous results and removed edges list
   Restart the process from step 2
