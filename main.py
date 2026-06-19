import streamlit as st
import os
import tempfile
import shutil
import logging
import datetime
from kml_converter import convert_kml_to_shapefile
from utils import get_file_info, create_download_zip, extract_kmz
from cleanup import cleanup_old_files

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Create a persistent temp directory for the application
TEMP_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_data")
os.makedirs(TEMP_DATA_DIR, exist_ok=True)
logging.info(f"Initialized temp directory at: {TEMP_DATA_DIR}")

# Run cleanup at startup to remove old files
try:
    deleted_count = cleanup_old_files()
    logging.info(f"Startup cleanup completed: removed {deleted_count} old files/directories")
except Exception as e:
    logging.error(f"Error during startup cleanup: {str(e)}")

from PIL import Image

icon_image = Image.open("favicon.png")

st.set_page_config(
    page_title="KML to Shapefile Converter",
    page_icon=icon_image,
    layout="wide"
)


st.title("🌍 KML to Shapefile Converter")
st.markdown("""
This app converts Google Earth KML files to ESRI Shapefile format.
Upload your KML file below to get started.
""")

# File uploader for KML files
uploaded_file = st.file_uploader("Upload a KML file", type=["kml", "kmz"])

if uploaded_file is not None:
    # Display file info
    st.subheader("File Information")
    file_info = get_file_info(uploaded_file)
    
    # Create columns for file info display
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Filename:** {file_info['filename']}")
        st.write(f"**File size:** {file_info['size']}")
    with col2:
        st.write(f"**File type:** {file_info['filetype']}")
    
    # Process button
    if st.button("Convert to Shapefile"):
        with st.spinner("Converting KML to Shapefile..."):
            # Create a list to track temp directories that need cleanup
            temp_dirs_to_cleanup = []
            
            try:
                # Create a unique dated folder inside the persistent temp directory
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                user_temp_dir = os.path.join(TEMP_DATA_DIR, f"conversion_{timestamp}")
                os.makedirs(user_temp_dir, exist_ok=True)
                temp_dirs_to_cleanup.append(user_temp_dir)
                logging.info(f"Created user temporary directory: {user_temp_dir}")
                
                # Create a processing temp directory (will be auto-cleaned)
                main_temp_dir = tempfile.mkdtemp()
                temp_dirs_to_cleanup.append(main_temp_dir)
                logging.info(f"Created processing temporary directory: {main_temp_dir}")
                
                # Save the uploaded file to the temporary directory
                temp_kml_path = os.path.join(main_temp_dir, uploaded_file.name)
                with open(temp_kml_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                logging.info(f"Processing file: {uploaded_file.name}")
                
                # Convert KML to Shapefile (all geometry types)
                conversion_result = convert_kml_to_shapefile(
                    temp_kml_path,
                    main_temp_dir
                )
                
                if conversion_result["success"]:
                    st.success("✅ Conversion completed successfully!")
                    
                    # Show details about the conversion
                    st.subheader("Conversion Details")
                    st.write(f"**Features processed:** {conversion_result['feature_count']}")
                    
                    # Show geometry types
                    if 'geometry_types' in conversion_result:
                        geometry_types = conversion_result['geometry_types']
                        if isinstance(geometry_types, list) and geometry_types:
                            st.write(f"**Geometry types:** {', '.join(geometry_types)}")
                            
                            # Add icons for each geometry type
                            geom_icons = {
                                'Point': '📍', 
                                'MultiPoint': '📍📍',
                                'LineString': '〰️', 
                                'MultiLineString': '〰️〰️',
                                'Polygon': '🔷',
                                'MultiPolygon': '🔷🔷'
                            }
                            
                            st.write("**Exported geometry types:**")
                            for geom in geometry_types:
                                icon = geom_icons.get(geom, '🌐')
                                st.write(f"{icon} {geom}")
                    
                    # Create a zip file for download
                    zip_path = create_download_zip(conversion_result["output_files"], main_temp_dir)
                    
                    # Save a copy to the persistent directory for cleanup
                    base_name = os.path.splitext(uploaded_file.name)[0]
                    persistent_zip_path = os.path.join(
                        user_temp_dir,
                        f"{base_name}.zip"
                    )
                    shutil.copy2(zip_path, persistent_zip_path)
                    logging.info(f"Saved persistent copy at: {persistent_zip_path}")
                    
                    # Provide download link
                    with open(zip_path, "rb") as f:
                        zip_data = f.read()
                    
                    st.download_button(
                        label="📥 Download Shapefile (ZIP)",
                        data=zip_data,
                        file_name=f"{base_name}.zip",
                        mime="application/zip"
                    )
                else:
                    st.error(f"❌ Conversion failed: {conversion_result['error']}")
            except Exception as e:
                logging.exception("Error during conversion")
                st.error(f"❌ An error occurred during conversion: {str(e)}")
            finally:
                # Clean up all temporary directories
                for temp_dir in temp_dirs_to_cleanup:
                    try:
                        shutil.rmtree(temp_dir)
                        logging.info(f"Cleaned up temporary directory: {temp_dir}")
                    except Exception as cleanup_error:
                        logging.error(f"Failed to clean up temporary directory {temp_dir}: {cleanup_error}")

# Add instructions and information at the bottom
with st.expander("ℹ️ About KML to Shapefile Conversion"):
    st.markdown("""
    ### What is a KML file?
    KML (Keyhole Markup Language) is an XML-based file format used to display geographic data in applications like Google Earth and Google Maps.
    
    ### What is a Shapefile?
    ESRI Shapefile is a popular geospatial vector data format for geographic information system (GIS) software. It spatially describes geometries like points, lines, and polygons.
    
    ### Conversion Details
    This app preserves the following during conversion:
    - Geometry (points, lines, polygons)
    - Attributes/metadata
    - Coordinate system information (when available)
    
    ### Output Files
    A Shapefile consists of multiple files with the same name but different extensions:
    - `.shp`: Shape format; the feature geometry itself
    - `.shx`: Shape index format; a positional index of the feature geometry
    - `.dbf`: Attribute format; columnar attributes for each shape
    - `.prj`: Projection format; the coordinate system and projection information
    
    All these files will be packaged into a ZIP file for download.
    """)

st.sidebar.title("About")
st.sidebar.info(
    "This tool converts Google Earth KML files to ESRI Shapefile format. "
    "It supports points, lines, and polygons with their associated attributes."
)
st.sidebar.markdown("---")
st.sidebar.subheader("Supported Features")
st.sidebar.markdown("""
- KML and KMZ file formats
- Point, line, and polygon geometries
- Attribute/metadata preservation
- Coordinate system conversion
""")
