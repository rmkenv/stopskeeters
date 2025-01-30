import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import logging
from geopy.geocoders import Nominatim
from shapely.geometry import Point

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CENTER = [39.0458, -76.6413]  # Default map center (Baltimore)
HIGH_RISK_THRESHOLD = 0.7  # Default high-risk threshold

# Data source URLs
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
    except Exception as e:
        logger.error(f"Error loading {source}: {e}")
        st.error(f"Failed to load {source}.")
        return gpd.GeoDataFrame() if data_type == "geojson" else None


def create_map(center_point=None, parcels=gpd.GeoDataFrame(), wetlands_wms_url=None, roads=gpd.GeoDataFrame(), zoom_level=10, basemap='CartoDB positron'):
    m = folium.Map(
        location=center_point or DEFAULT_CENTER,
        zoom_start=zoom_level,
        tiles=basemap
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


def calculate_risk(parcel):  # Placeholder for risk calculation
    return 0.5


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

basemap_options = {
    'CartoDB positron': 'CartoDB positron',
    'NAIP': 'https://services.nationalmap.gov/arcgis/rest/services/USGS_Imagery/NAIP/MapServer/tile/{z}/{y}/{x}'
}
selected_basemap = st.selectbox("Select Basemap", options=list(basemap_options.keys()))

address = st.text_input("Enter an address:")
if address:
    center_point = geocode_address(address)
    if center_point:
        nearest_parcel = parcels.iloc[0]  # Placeholder - Replace with actual logic
        risk_score = calculate_risk(nearest_parcel)
        st.write(f"Risk Score: {risk_score}")

        point_gdf = gpd.GeoDataFrame({'geometry': [Point(center_point)]}, crs="EPSG:4326")
        buffered_point = point_gdf.buffer(0.005)
        bounds = buffered_point.total_bounds

        main_map = create_map(center_point=center_point, parcels=parcels, wetlands_wms_url=WETLANDS_WMS_URL, roads=roads, basemap=basemap_options[selected_basemap])
        main_map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        folium_static(main_map)

    else:
        st.error("Address not found.")
else:
    main_map = create_map(parcels=parcels, wetlands_wms_url=WETLANDS_WMS_URL, roads=roads, basemap=basemap_options[selected_basemap])
    folium_static(main_map)

# ... (Add any other features)
