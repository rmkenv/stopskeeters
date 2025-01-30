import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import logging
from geopy.geocoders import Nominatim

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CENTER = [39.0458, -76.6413]  # Default map center (Baltimore)
HIGH_RISK_THRESHOLD = 0.7  # Default high-risk threshold

# Data source URLs (updated for WMS)
DATA_SOURCES = {
    "parcels": "https://geodata.md.gov/imap/rest/services/PlanningCadastre/MD_ParcelBoundaries/MapServer/0/query?outFields=*&where=1%3D1&f=geojson",
    "roads": "https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services/MDOT_Know_Your_Roads/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson"
}
WETLANDS_WMS_URL = "https://geodata.md.gov/imap/services/Hydrology/MD_Wetlands/MapServer/WMSServer?"


@st.cache_data  # Cache the loaded data
def load_data(source, data_type="geojson"):
    try:
        if data_type == "geojson":
            gdf = gpd.read_file(source)
            return gdf
        # Add handling for other data types if needed
    except Exception as e:
        logger.error(f"Error loading {source}: {e}")
        st.error(f"Failed to load {source}.")
        return gpd.GeoDataFrame() if data_type == "geojson" else None  # Return empty GeoDataFrame or None


def create_map(center_point=None, parcels=gpd.GeoDataFrame(), wetlands_wms_url=None, roads=gpd.GeoDataFrame()):
    m = folium.Map(
        location=center_point or DEFAULT_CENTER,
        zoom_start=10,
        tiles='CartoDB positron'
    )

    if not parcels.empty:
        folium.GeoJson(parcels, name="Parcels").add_to(m)

    if wetlands_wms_url:
        folium.WmsTileLayer(
            url=wetlands_wms_url,
            layers='0',  # Replace with correct layer name from GetCapabilities
            name='Wetlands (WMS)',
            fmt='image/png',
            transparent=True,
            control=True,
            show=True
        ).add_to(m)

    if not roads.empty:
        folium.GeoJson(roads, name="Roads").add_to(m)

    folium.LayerControl().add_to(m)
    return m


# Placeholder for risk calculation (replace with your actual logic)
def calculate_risk(parcel):
    return 0.5  # Placeholder


# Geocoding function
def geocode_address(address):
    geolocator = Nominatim(user_agent="mosquito_control_app")
    location = geolocator.geocode(address)
    if location:
        return [location.latitude, location.longitude]
    else:
        return None


# Streamlit App
st.title("Mosquito Control Dashboard")

with st.spinner("Loading data..."):
    parcels = load_data(DATA_SOURCES["parcels"])
    roads = load_data(DATA_SOURCES["roads"])

# Address search
address = st.text_input("Enter an address:")
if address:
    center_point = geocode_address(address)
    if center_point:
        # Find nearest parcel (replace with your actual logic)
        nearest_parcel = parcels.iloc[0]  # Placeholder
        risk_score = calculate_risk(nearest_parcel)
        st.write(f"Risk Score: {risk_score}")

        main_map = create_map(center_point=center_point, parcels=parcels, wetlands_wms_url=WETLANDS_WMS_URL, roads=roads)
        folium_static(main_map)

    else:
        st.error("Address not found.")
else:
    main_map = create_map(parcels=parcels, wetlands_wms_url=WETLANDS_WMS_URL, roads=roads)
    folium_static(main_map)


# ... (Add any other features like high-risk parcel identification, data export, etc.)
