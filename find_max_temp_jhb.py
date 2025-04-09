import ee
import datetime
import sys

# Authenticate and initialize Earth Engine
try:
    ee.Initialize()
    print("Earth Engine initialized successfully.")
except Exception as e:
    print(f"ERROR: Earth Engine initialization failed. \nPlease ensure you have authenticated by running 'earthengine authenticate' in your terminal.")
    print(f"Details: {e}")
    sys.exit(1)

# Define the Area of Interest (Johannesburg)
# Coordinates are Lon, Lat
joburg_point = ee.Geometry.Point(28.0473, -26.2041)

# Define the time range (last 10 years from today)
try:
    end_date = datetime.datetime.now(datetime.timezone.utc)
    # Calculate start date precisely 10 years ago
    start_date = end_date.replace(year=end_date.year - 10)
except Exception as e:
    print(f"Error calculating date range: {e}")
    sys.exit(1)

start_date_str = start_date.strftime('%Y-%m-%d')
end_date_str = end_date.strftime('%Y-%m-%d')

print(f"Searching for max temperature between {start_date_str} and {end_date_str}...")

# Load the ERA5 Daily Aggregates image collection
# Dataset provides max 2m air temperature ('maximum_2m_air_temperature') in Kelvin
era5_daily_collection = ee.ImageCollection('ECMWF/ERA5/DAILY') \
    .filterBounds(joburg_point) \
    .filterDate(start_date_str, end_date_str) \
    .select('maximum_2m_air_temperature')

# Function to convert K->C AND add time band for quality mosaic
def add_temp_and_time(image):
    # Convert K to C
    celsius = image.subtract(273.15).rename('max_temp_celsius')
    # Get time and cast to integer (milliseconds since epoch)
    time = image.metadata('system:time_start').rename('time')
    # Add bands together and copy original time property just in case
    return celsius.addBands(time).copyProperties(image, ['system:time_start'])

# Apply the function
era5_with_time = era5_daily_collection.map(add_temp_and_time)

# Check if the collection contains any images after filtering
count = era5_with_time.size().getInfo()
if count == 0:
    print(f"No temperature data found for the specified location and date range ({start_date_str} to {end_date_str}).")
    sys.exit(1)
else:
    print(f"Found {count} daily temperature images to analyze.")

# --- Get Max Temp AND Date using Reducer.max(2) ---
# Reducer selects pixels based on max temperature ('max_temp_celsius')
# but returns values from both bands ['max_temp_celsius', 'time']
max_temp_and_time_reducer = ee.Reducer.max(numInputs=2)
max_image = era5_with_time.select(['max_temp_celsius', 'time'])\
                          .reduce(reducer=max_temp_and_time_reducer)

# Extract the max temp and corresponding time at the point of interest
# Result is a dictionary like {'max_temp_celsius_max': temp, 'time_max': time_ms}
max_info = max_image.reduceRegion(
    reducer=ee.Reducer.first(), # Use first() as we reduced to a single image
    geometry=joburg_point,
    scale=27830, # Use native scale
    crs='EPSG:4326'
)

# Retrieve the results from Earth Engine
try:
    # Get values from the dictionary using the correct keys
    # 'max' corresponds to the first band ('max_temp_celsius')
    # 'max1' corresponds to the second band ('time') for that max temp
    max_temp_celsius = max_info.get('max').getInfo()
    max_time_ms = max_info.get('max1').getInfo()

    if max_temp_celsius is not None and max_time_ms is not None:
        # Convert time in milliseconds to a date object and format it
        max_date = ee.Date(max_time_ms).format('YYYY-MM-dd').getInfo()

        print("\n--- Hottest Day Found (using Reducer.max(2)) ---")
        print(f"Date: {max_date}")
        print(f"Maximum Temperature over 10 years: {max_temp_celsius:.2f} °C")
        print("\n(Note: Based on ERA5 Daily reanalysis data, representing approx. 27km grid cell average)")
    else:
        print("\nCould not retrieve the maximum temperature and date for Johannesburg.")

except ee.EEException as e:
    print(f"\nAn error occurred while fetching data from Earth Engine: {e}")
except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")
