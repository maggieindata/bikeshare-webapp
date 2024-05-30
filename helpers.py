import urllib  # Import module for working with URLs
import json  # Import module for working with JSON data
import pandas as pd  # Import pandas for data manipulation
import folium  # Import folium for creating interactive maps
import datetime as dt  # Import datetime for working with dates and times
from geopy.distance import geodesic  # Import geodesic for calculating distances
from geopy.geocoders import Nominatim  # Import Nominatim for geocoding
import streamlit as st  # Import Streamlit for creating web apps

@st.cache_data  # Cache the function's output to improve performance
# Define the function to query station status from a given URL
def query_station_status(url):
    with urllib.request.urlopen(url) as data_url:  # Open the URL
        data = json.loads(data_url.read().decode())  # Read and decode the JSON data

    df = pd.DataFrame(data['data']['stations'])  # Convert the data to a DataFrame
    df = df[df.is_renting == 1]  # Filter out stations that are not renting
    df = df[df.is_returning == 1]  # Filter out stations that are not returning
    df = df.drop_duplicates(['station_id', 'last_reported'])  # Remove duplicate records
    df.last_reported = df.last_reported.map(lambda x: dt.datetime.utcfromtimestamp(x))  # Convert timestamps to datetime
    df['time'] = data['last_updated']  # Add the last updated time to the DataFrame
    df.time = df.time.map(lambda x: dt.datetime.utcfromtimestamp(x))  # Convert timestamps to datetime
    df = df.set_index('time')  # Set the time as the index
    df.index = df.index.tz_localize('UTC')  # Localize the index to UTC
    df = pd.concat([df, df['num_bikes_available_types'].apply(pd.Series)], axis=1)  # Expand the bike types column

    return df  # Return the DataFrame

# Define the function to get station latitude and longitude from a given URL
def get_station_latlon(url):
    with urllib.request.urlopen(url) as data_url:  # Open the URL
        latlon = json.loads(data_url.read().decode())  # Read and decode the JSON data
    latlon = pd.DataFrame(latlon['data']['stations'])  # Convert the data to a DataFrame
    return latlon  # Return the DataFrame

# Define the function to join two DataFrames on station_id
def join_latlon(df1, df2):
    df = df1.merge(df2[['station_id', 'lat', 'lon']], 
                how='left', 
                on='station_id')  # Merge the DataFrames on station_id
    return df  # Return the merged DataFrame

# Function to determine marker color based on the number of bikes available
def get_marker_color(num_bikes_available):
    if num_bikes_available > 3:
        return 'green'
    elif 0 < num_bikes_available <= 3:
        return 'yellow'
    else:
        return 'red'

# Define the function to geocode an address
def geocode(address):
    geolocator = Nominatim(user_agent="clicked-demo")  # Create a geolocator object
    location = geolocator.geocode(address)  # Geocode the address
    if location is None:
        return ''  # Return an empty string if the address is not found
    else:
        return (location.latitude, location.longitude)  # Return the latitude and longitude

# Define the function to get bike availability near a location
def get_bike_availability(latlon, df, input_bike_modes):
    """Calculate distance from each station to the user and return a single station id, lat, lon"""
    if len(input_bike_modes) == 0 or len(input_bike_modes) == 2:  # If no mode selected, assume both bikes are selected
        i = 0
        df['distance'] = ''
        while i < len(df):
            df.loc[i, 'distance'] = geodesic(latlon, (df['lat'][i], df['lon'][i])).km  # Calculate distance to each station
            i = i + 1
        df = df.loc[(df['ebike'] > 0) | (df['mechanical'] > 0)]  # Remove stations with no available bikes
        chosen_station = []
        chosen_station.append(df[df['distance'] == min(df['distance'])]['station_id'].iloc[0])  # Get closest station
        chosen_station.append(df[df['distance'] == min(df['distance'])]['lat'].iloc[0])
        chosen_station.append(df[df['distance'] == min(df['distance'])]['lon'].iloc[0])
    else:
        i = 0
        df['distance'] = ''
        while i < len(df):
            df.loc[i, 'distance'] = geodesic(latlon, (df['lat'][i], df['lon'][i])).km  # Calculate distance to each station
            i = i + 1
        df = df.loc[df[input_bike_modes[0]] > 0]  # Remove stations without the selected mode available
        chosen_station = []
        chosen_station.append(df[df['distance'] == min(df['distance'])]['station_id'].iloc[0])  # Get closest station
        chosen_station.append(df[df['distance'] == min(df['distance'])]['lat'].iloc[0])
        chosen_station.append(df[df['distance'] == min(df['distance'])]['lon'].iloc[0])
    return chosen_station  # Return the chosen station

# Define the function to get dock availability near a location
def get_dock_availability(latlon, df):
    """Calculate distance from each station to the user and return a single station id, lat, lon"""
    i = 0
    df['distance'] = ''
    while i < len(df):
        df.loc[i, 'distance'] = geodesic(latlon, (df['lat'][i], df['lon'][i])).km  # Calculate distance to each station
        i = i + 1
    df = df.loc[df['num_docks_available'] > 0]  # Remove stations without available docks
    chosen_station = []
    chosen_station.append(df[df['distance'] == min(df['distance'])]['station_id'].iloc[0])  # Get closest station
    chosen_station.append(df[df['distance'] == min(df['distance'])]['lat'].iloc[0])
    chosen_station.append(df[df['distance'] == min(df['distance'])]['lon'].iloc[0])
    return chosen_station  # Return the chosen station

import requests  # Import requests for making HTTP requests

# Define the function to run OSRM and get route coordinates and duration
def run_osrm(chosen_station, iamhere):
    start = "{},{}".format(iamhere[1], iamhere[0])  # Format the start coordinates
    end = "{},{}".format(chosen_station[2], chosen_station[1])  # Format the end coordinates
    url = 'http://router.project-osrm.org/route/v1/driving/{};{}?geometries=geojson'.format(start, end)  # Create the OSRM API URL

    headers = {'Content-type': 'application/json'}
    r = requests.get(url, headers=headers)  # Make the API request
    print("Calling API ...:", r.status_code)  # Print the status code

    routejson = r.json()  # Parse the JSON response
    coordinates = []
    i = 0
    lst = routejson['routes'][0]['geometry']['coordinates']
    while i < len(lst):
        coordinates.append([lst[i][1], lst[i][0]])  # Extract coordinates
        i = i + 1
    duration = round(routejson['routes'][0]['duration'] / 60, 1)  # Convert duration to minutes

    return coordinates, duration  # Return the coordinates and duration
