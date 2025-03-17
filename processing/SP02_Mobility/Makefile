generate-data:
	@echo "Generating data for SP02 Mobility"
	tippecanoe --force -zg \
		--coalesce-densest-as-needed \
		--extend-zooms-if-still-dropping \
		-o accessibility_20250220.pmtiles accessibility_20250220_wgs84.json
	cp accessibility_20250220.pmtiles ../../frontend/public/geodata/
	@echo "Data generated for SP02 Mobility"


generate-data-coalesce:
	@echo "Generating data for SP02 Mobility"
	tippecanoe --force -zg \
		--coalesce-smallest-as-needed \
		--extend-zooms-if-still-dropping \
		-E access_nearest_k_time_return_walk_poi_shop_short:mean \
		-E access_nearest_k_time_return_walk_poi_recreation_indoors:mean \
		-E access_nearest_time_return_bike_e25_poi_education_school:mean \
		-E access_nearest_time_return_drive_peak_poi_education_school:mean \
		-E ar_schools_ebike_bike:mean \
		-E ar_schools_ebike_car:mean \
		-E access_gravity_time_return_bike_e25_employment_total:mean \
		-E access_gravity_time_return_transit_employment_total:mean \
		-E access_gravity_time_return_drive_peak_employment_total:mean \
		-E ar_jobs_transit_car:mean \
		-E ar_jobs_ebike_car:mean \
		--no-tile-compression \
		-o accessibility_20250220_wgs84.pmtiles accessibility_20250220_wgs84.json
	cp accessibility_20250220_wgs84.pmtiles ../../frontend/public/geodata/
	@echo "Data generated for SP02 Mobility"



test-coalesce:
	@echo "Generating data for SP02 Mobility"
	tippecanoe --force -zg \
		--coalesce-densest-as-needed \
		--extend-zooms-if-still-dropping \
		-o test-coalesce.pmtiles accessibility_20250220_wgs84.json
	cp test-coalesce.pmtiles ../../frontend/public/geodata/
	@echo "Data generated for SP02 Mobility"