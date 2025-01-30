import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import logging
from geopy.geocoders import Nominatim
from shapely.geometry import Point
from shapely.ops import nearest_points
import pyproj

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CENTER = [39.0458, -76.6413]  # Baltimore coordinates
HIGH_RISK_THRESHOLD = 0.7
CRS_WGS84 = "EPSG:4326"  # WGS84 coordinate system
CRS_PROJECTED = "EPSG:26985"  # Projected CRS for Maryland

# Data sources
DATA_SOURCES = {
    "parcels": "https://geodata.md.gov/imap/rest/services/PlanningCadastre/MD_ParcelBoundaries/MapServer/0/query?outFields=*&where=1%3D1&f=geojson",
    "roads": "https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services/MDOT_Know_Your_Roads/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson"
}
WETLANDS_WMS_URL = "https://geodata.md.gov/imap/services/Hydrology/MD_Wetlands/MapServer/WMSServer?"
WETLANDS_LAYER_NAME = '0'

@st.cache_data
def load_data(source, data_type="geojson"):
    try:
        if data_type == "geojson":
            gdf = gpd.read_file(source)
            return gdf
    except Exception as e:
        logger.error(f"Error loading {source}: {e}")
        st.error(f"Failed to load {source}.  Check the URL and your internet connection.")
        return gpd.GeoDataFrame()  # Return empty GeoDataFrame to avoid further errors

def create_map(center_point=None, parcels=gpd.GeoDataFrame(), wetlands_wms_url=None,
               roads=gpd.GeoDataFrame(), highlighted_parcel=None):
    zoom = 12 if center_point else 10
    m = folium.Map(
        location=center_point or DEFAULT_CENTER,
        zoom_start=zoom,
        tiles='CartoDB positron'
    )

    if not parcels.empty:
        folium.GeoJson(parcels.to_crs(CRS_WGS84), name="Parcels").add_to(m) # Project parcels to WGS84

    if wetlands_wms_url:
        folium.WmsTileLayer(
            url=wetlands_wms_url,
            layers=WETLANDS_LAYER_NAME,
            name='Wetlands',
            fmt='image/png',
            transparent=True,
            control=True,
            show=True
        ).add_to(m)

    if not roads.empty:
        folium.GeoJson(roads.to_crs(CRS_WGS84), name="Roads").add_to(m) # Project roads to WGS84

    if highlighted_parcel is not None and not highlighted_parcel.empty: #Check if it's empty
        folium.GeoJson(
            highlighted_parcel.to_crs(CRS_WGS84),  # Project highlighted parcel to WGS84
            style_function=lambda x: {'fillColor': 'red', 'color': 'red', 'fillOpacity': 0.5} # Add fillOpacity
        ).add_to(m)

    folium.LayerControl().add_to(m)
    m.attribution = '<a href="https://imap.maryland.gov/">Maryland iMap</a>'
    return m

def calculate_risk(parcel):
    return 0.5  # Placeholder implementation - replace with your actual risk calculation

def geocode_address(address):
    geolocator = Nominatim(user_agent="mosquito_control_app")
    try:
        location = geolocator.geocode(address)
        return [location.latitude, location.longitude] if location else None
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        st.error("Geocoding failed. Please check your address and try again.")
        return None

def find_nearest_parcel(point, parcels):
    try:
        parcels_proj = parcels.to_crs(CRS_PROJECTED)
        point_proj = gpd.GeoSeries([point], crs=CRS_WGS84).to_crs(CRS_PROJECTED)[0]
        nearest = nearest_points(point_proj, parcels_proj.unary_union)
        nearest_parcel = parcels_proj[parcels_proj.geometry == nearest[1]].to_crs(CRS_WGS84) #Project back
        return nearest_parcel
    except Exception as e:
        logger.error(f"Error finding nearest parcel: {e}")
        return gpd.GeoDataFrame()

# Streamlit App
st.title("Mosquito Control Dashboard")

with st.spinner("Loading data..."):
    parcels = load_data(DATA_SOURCES["parcels"])
    roads = load_data(DATA_SOURCES["roads"])

if not parcels.empty and not roads.empty: # Check if data loaded successfully
    address = st.text_input("Enter an address:")
    if address:
        center_point = geocode_address(address)
        if center_point:
            point = Point(center_point[1], center_point[0])  # Shapely Point (lon, lat)
            nearest_parcel = find_nearest_parcel(point, parcels)

            if not nearest_parcel.empty:
                risk_score = calculate_risk(nearest_parcel)
                st.metric("Risk Score", f"{risk_score:.2f}")

                map_obj = create_map(
                    center_point=center_point,
                    parcels=parcels,
                    wetlands_wms_url=WETLANDS_WMS_URL,
                    roads=roads,
                    highlighted_parcel=nearest_parcel
                )
                folium_static(map_obj)
            else:
                st.error("No parcels found near this address.")
        else:
            st.error("Address not found.")
    else:
        map_obj = create_map(parcels=parcels, wetlands_wms_url=WETLANDS_WMS_URL, roads=roads)
        folium_static(map_obj)
else:
    st.error("Failed to load required data.  The app cannot run.")
