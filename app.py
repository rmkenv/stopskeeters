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
DEFAULT_CENTER = [39.0458, -76.6413]  # Default map center (Baltimore)
HIGH_RISK_THRESHOLD = 0.7  # Default high-risk threshold
CRS_WGS84 = "EPSG:4326"  # WGS84 coordinate system for geocoding
CRS_PROJECTED = "EPSG:26985"  # Projected CRS for Maryland (NAD83 / UTM zone 18N)

# Data source URLs
DATA_SOURCES = {
    "parcels": "https://geodata.md.gov/imap/rest/services/PlanningCadastre/MD_ParcelBoundaries/MapServer/0/query?outFields=*&where=1%3D1&f=geojson",
    "roads": "https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services/MDOT_Know_Your_Roads/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson"
}
WETLANDS_WMS_URL = "https://geodata.md.gov/imap/services/Hydrology/MD_Wetlands/MapServer/WMSServer?"
WETLANDS_LAYER_NAME = '0'  # Replace with the actual layer name from GetCapabilities


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


def create_map(center_point=None, parcels=gpd.GeoDataFrame(), wetlands_wms_url=None, roads=gpd.GeoDataFrame(), highlighted_parcel=None, zoom_level=12, basemap='CartoDB positron'):
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
            layers=WETLANDS_LAYER_NAME,  # Use the layer name constant
            name='Wetlands (WMS)',
            fmt='image/png',
            transparent=True,
            control=True,
            show=True
        ).add_to(m)

    if not roads.empty:
        folium.GeoJson(roads, name="Roads").add_to(m)

    if highlighted_parcel is not None:
        folium.GeoJson(
            highlighted_parcel.to_crs(CRS_WGS84),  # Ensure correct CRS for Folium
            style_function=lambda x: {'fillColor': 'red', 'color': 'red'}
        ).add_to(m)

    folium.LayerControl().add_to(m)
    m.attribution = '<a href="https://imap.maryland.gov/">Maryland iMap</a>'  # Add attribution
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


def find_nearest_parcel(point, parcels):
    parcels_proj = parcels.to_crs(CRS_PROJECTED)  # Project to a suitable CRS for distance calculations
    point_proj = gpd.GeoSeries([point], crs=CRS_WGS84).to_crs(CRS_PROJECTED)[0]

    nearest = nearest_points(point_proj, parcels_proj.unary_union)
    nearest_parcel = parcels_proj[parcels_proj.geometry == nearest[1]]
    return nearest_parcel.to_crs(CRS_WGS84)  # Convert back to WGS84


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
        point = Point(center_point[1], center_point[0])  # Create a Shapely Point
        nearest_parcel = find_nearest_parcel(point, parcels)

        if not nearest_parcel.empty:
            risk_score = calculate_risk(nearest_parcel)
            st.write(f"Risk Score: {risk_score}")

            main_map = create_map(center_point=center_point, parcels=parcels, wetlands_wms_url=WETLANDS_WMS_URL, roads=roads, highlighted_parcel=nearest_parcel, basemap=basemap_options[selected_basemap])
            folium_static(main_map)
        else:
            st.error("No parcel found near this address.")

    else:
        st.error("Address not found.")
else:
    main_map = create_map(parcels=parcels, wetlands_wms_url=WETLANDS_WMS_URL, roads=roads, basemap=basemap_options[selected_basemap])
    folium_static(main_map)

# ... (Add other features)
