import os
import zipfile
import datetime
import tempfile
import humanize

def get_file_info(uploaded_file):
    """
    Extract information about the uploaded file.
    
    Args:
        uploaded_file: Streamlit uploaded file object
    
    Returns:
        dict: Dictionary containing file information
    """
    file_info = {
        "filename": uploaded_file.name,
        "size": humanize.naturalsize(uploaded_file.size),
        "filetype": uploaded_file.type if uploaded_file.type else "application/octet-stream"
    }
    return file_info

def create_download_zip(file_paths, temp_dir):
    """
    Create a zip file containing all Shapefile component files.
    
    Args:
        file_paths (list): List of paths to files to include in the zip
        temp_dir (str): Temporary directory to create the zip in
    
    Returns:
        str: Path to the created zip file
    """
    # Create timestamp for unique zip filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(temp_dir, f"shapefile_{timestamp}.zip")
    
    # Create zip file
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file_path in file_paths:
            # Add file to zip with just the filename (not the full path)
            zipf.write(file_path, os.path.basename(file_path))
    
    return zip_path

def extract_kmz(kmz_path):
    """
    Extract a KMZ file (which is a zipped KML file).
    
    Args:
        kmz_path (str): Path to the KMZ file
    
    Returns:
        tuple: (str, str) - (path to the extracted KML file, temp directory path) 
               or (None, None) if extraction failed
    """
    try:
        # Create a temporary directory to extract the KMZ
        temp_dir = tempfile.mkdtemp()
        
        # Extract the KMZ file
        with zipfile.ZipFile(kmz_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Look for KML files in the extracted directory
        kml_files = [f for f in os.listdir(temp_dir) if f.lower().endswith('.kml')]
        
        if not kml_files:
            # Clean up if no KML files found
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except Exception:
                pass
            return None, None
        
        # Return the path to the first KML file found and the temp directory
        # The caller is responsible for cleaning up the temp directory
        return os.path.join(temp_dir, kml_files[0]), temp_dir
    
    except Exception as e:
        print(f"Error extracting KMZ file: {str(e)}")
        # Clean up in case of error
        try:
            # Check if temp_dir was created in this scope
            if 'temp_dir' in locals():
                import shutil
                shutil.rmtree(temp_dir)
        except Exception:
            pass
        return None, None
