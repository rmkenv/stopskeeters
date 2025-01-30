import streamlit as st
import duckdb
import geopandas as gpd
import folium
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
from shapely.geometry import Point
import requests
from requests.exceptions import RequestException
import logging
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DATA_SOURCES = {
    "parcels": "https://geodata.md.gov/imap/rest/services/PlanningCadastre/MD_ParcelBoundaries/MapServer/0/query?outFields=*&where=1%3D1&f=geojson",
    "wetlands": "https://geodata.md.gov/imap/services/Hydrology/MD_Wetlands/MapServer/WFSServer?request=GetCapabilities&service=WFS",
    "roads": "https://services.arcgis.com/njFNhDsUCentVYJW/arcgis/rest/services/MDOT_Know_Your_Roads/FeatureServer/0/query?outFields=*&where=1%3D1&f=geojson"
}
DEFAULT_CENTER = [39.0457, -76.6413]  # Maryland center coordinates

# Initialize DuckDB (in-memory for Streamlit Sharing)
@st.cache_resource
def init_duckdb():
    conn = duckdb.connect()  # Use in-memory database
    conn.execute("INSTALL spatial; LOAD spatial;")
    logger.info("DuckDB initialized with spatial extension")
    return conn

conn = init_duckdb()


# Data Loading and Preprocessing
@st.cache_data(ttl=3600)  # Refresh every hour
def load_geospatial_data(url: str, _session: requests.Session) -> gpd.GeoDataFrame:
    try:
        response = _session.get(url, timeout=10)
        response.raise_for_status()
        gdf = gpd.read_file(response.text)
        logger.info(f"Loaded data from {url}: {len(gdf)} rows")
        return gdf
    except Exception as e:
        logger.error(f"Failed to load data from {url}: {str(e)}")
        st.error(f"Failed to load data from source: {url}")
        return gpd.GeoDataFrame()



# Load data with error handling
with st.spinner("Loading data..."):
    try:
        session = requests.Session()
        parcels = load_geospatial_data(DATA_SOURCES["parcels"], session)
        wetlands = load_geospatial_data(DATA_SOURCES["wetlands"], session)
        roads = load_geospatial_data(DATA_SOURCES["roads"], session)

        # Validate data after loading
        if parcels.empty or wetlands.empty or roads.empty:
            raise ValueError("One or more datasets failed to load.")

        # Preprocess data
        parcels = preprocess_data(parcels, wetlands)

    except Exception as e:
        st.error(f"Error during data loading or preprocessing: {e}")
        st.stop()


# Geocoding
class Geocoder:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="mosquito_control_app", timeout=10)

    @lru_cache(maxsize=1000)
    def geocode(self, address: str) -> Point:
        try:
            location = self.geolocator.geocode(address)
            if location:
                return Point(location.longitude, location.latitude)
        except Exception as e:
            logger.error(f"Geocoding failed for {address}: {str(e)}")
        return None

geocoder = Geocoder()


# Preprocess data
@st.cache_data
def preprocess_data(_parcels, _wetlands):
    try:
        wetlands_buffer = _wetlands.geometry.buffer(100)
        _parcels['wetland_adjacent'] = _parcels.geometry.apply(lambda x: wetlands_buffer.intersects(x).any())
        _parcels['total_score'] = _parcels['wetland_adjacent'].astype(int)
        return _parcels.drop(columns=['index_right'], errors='ignore')
    except Exception as e:
        logger.error(f"Data preprocessing failed: {str(e)}")
        return _parcels



def create_map(center_point=None, parcels=gpd.GeoDataFrame(), wetlands=gpd.GeoDataFrame(), roads=gpd.GeoDataFrame()):
    m = folium.Map(
        location=center_point or DEFAULT_CENTER,
        zoom_start=10,
        tiles='CartoDB positron'
    )

    def style_function(feature):
        return {
            'fillColor': '#3186cc',
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.3
        }

    if not parcels.empty:
        folium.GeoJson(
            parcels,
            style_function=style_function,
            name='Parcels',
            tooltip=folium.GeoJsonTooltip(fields=['total_score'])
        ).add_to(m)

    if not wetlands.empty:
        folium.GeoJson(
            wetlands,
            style_function=lambda x: {'fillColor': 'green', 'color': 'darkgreen'},
            name='Wetlands'
        ).add_to(m)

    if not roads.empty:
        folium.GeoJson(
            roads,  # Show all roads
            style_function=lambda x: {'color': 'gray'},
            name='Roads'
        ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


# Streamlit UI
st.title("Mosquito Control Interactive Dashboard")

# Main map display
main_map = create_map(parcels=parcels, wetlands=wetlands, roads=roads)
folium_static(main_map)


# Address search
with st.form("address_search"):
    address = st.text_input("Enter an address:", key="address_input")
    if st.form_submit_button("Search"):
        if address:
            point = geocoder.geocode(address)
            if point:
                st.session_state['search_point'] = point
                st.session_state['nearest_parcel'] = parcels.iloc[parcels.distance(point).argsort()[0]]
            else:
                st.error("Address not found. Please try a different address.")


if 'search_point' in st.session_state:
    point = st.session_state.search_point
    parcel = st.session_state.nearest_parcel

    with st.expander("Search Results", expanded=True):
        cols = st.columns([2, 1])
        with cols[0]:
            focused_map = create_map(center_point=[point.y, point.x])
            folium.Marker([point.y, point.x], popup="Search Location", icon=folium.Icon(color='red')).add_to(focused_map)
            folium.GeoJson(parcel.geometry, style_function=lambda x: {'fillColor': 'blue', 'color': 'black'}).add_to(focused_map)
            folium_static(focused_map)

        with cols[1]:
            st.metric("Total Risk Score", parcel.total_score)
            st.metric("Wetland Adjacent", "Yes" if parcel.wetland_adjacent else "No")


# Risk analysis sidebar
with st.sidebar:
    st.title("Risk Analysis")
    score_threshold = st.slider(
        "Risk Threshold",
        min_value=int(parcels.total_score.min()),
        max_value=int(parcels.total_score.max()),
        value=int(parcels.total_score.quantile(0.75))
    )

    high_risk = parcels[parcels.total_score > score_threshold]
    st.metric("High Risk Parcels", len(high_risk))

    if st.button("Export High Risk Data"):
        st.download_button(
            label="Download CSV",
            data=high_risk.to_csv(index=False),
            file_name="high_risk_parcels.csv",
            mime="text/csv"
        )


# No file operations in this version, except optional high_risk_parcels.csv download.
