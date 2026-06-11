import os
import geopandas as gpd
import fiona
from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon
import tempfile
from zipfile import ZipFile
import logging

# Register KML driver
fiona.drvsupport.supported_drivers['KML'] = 'rw'
fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'

# Maps geometry types to a short label used as suffix when multiple types exist
_GEOM_LABELS = {
    'Point': 'point', 'MultiPoint': 'point',
    'LineString': 'line', 'MultiLineString': 'line',
    'Polygon': 'polygon', 'MultiPolygon': 'polygon',
}

def _save_gdf_by_geom_type(gdf, output_dir, base_filename):
    """
    Save a GeoDataFrame to shapefile(s) grouped by geometry type.
    - Single geometry type  → <base_filename>.shp
    - Multiple geometry types → <base_filename>_point.shp / _line.shp / _polygon.shp
    Returns list of all shapefile component paths created.
    """
    extensions = ['.shp', '.shx', '.dbf', '.prj', '.cpg']
    output_files = []

    broad_types = gdf.geometry.geom_type.map(lambda t: _GEOM_LABELS.get(t, 'other')).unique()
    use_suffix = len(broad_types) > 1

    for label in broad_types:
        subset = gdf[gdf.geometry.geom_type.map(lambda t: _GEOM_LABELS.get(t, 'other')) == label]
        if subset.empty:
            continue
        out_stem = f"{base_filename}_{label}" if use_suffix else base_filename
        out_path = os.path.join(output_dir, f"{out_stem}.shp")
        subset.to_file(out_path)
        for ext in extensions:
            p = os.path.join(output_dir, f"{out_stem}{ext}")
            if os.path.exists(p):
                output_files.append(p)

    return output_files

def convert_kml_to_shapefile(kml_path, output_dir, geometry_types_to_include=None):
    """
    Convert a KML file to Shapefile format.
    
    Args:
        kml_path (str): Path to the input KML file
        output_dir (str): Directory to save the output Shapefile
        geometry_types_to_include (list, optional): List of geometry types to include.
            If provided, only features with these geometry types will be included.
            Example: ['Point'] to include only point geometries.
    
    Returns:
        dict: Dictionary containing conversion results
    """
    temp_dirs = []  # Store temporary directories to prevent premature deletion
    
    # Always use the original uploaded filename as the base for output files
    original_base_filename = os.path.splitext(os.path.basename(kml_path))[0]
    
    try:
        # Handle KMZ files by extracting them first
        if kml_path.lower().endswith(".kmz"):
            # Create a temporary directory that will exist throughout the function's scope
            kmz_temp_dir = tempfile.mkdtemp()
            temp_dirs.append(kmz_temp_dir)  # Save reference to prevent deletion
            
            # Extract KMZ file (which is just a zip file)
            with ZipFile(kml_path, 'r') as zip_ref:
                zip_ref.extractall(kmz_temp_dir)
            
            # Find the KML file in the extracted directory
            kml_files = [f for f in os.listdir(kmz_temp_dir) if f.lower().endswith('.kml')]
            if not kml_files:
                return {
                    "success": False,
                    "error": "No KML file found inside the KMZ archive"
                }
            
            # Use the first KML file found (but keep original_base_filename from the KMZ)
            kml_path = os.path.join(kmz_temp_dir, kml_files[0])
        
        # Try to read by specific layers rather than all at once
        try:
            # Get all layers first
            try:
                available_layers = fiona.listlayers(kml_path)
                logging.info(f"Available layers in KML: {available_layers}")
            except Exception:
                # If we can't get layer list, default to [''] (default layer)
                available_layers = ['']
                logging.info("Could not get layer list, using default empty layer name")
            
            # Initialize an empty GeoDataFrame for combining all layers
            combined_gdf = None
            all_geometry_types = set()
            
            # First, analyze all layers to find out what geometry types exist
            geometry_type_by_layer = {}
            
            # Check if we need to filter by geometry types
            apply_geometry_filter = geometry_types_to_include is not None and len(geometry_types_to_include) > 0
            
            # First pass: analyze layers
            for layer in available_layers:
                logging.info(f"Analyzing layer: {layer}")
                try:
                    layer_gdf = gpd.read_file(kml_path, driver='KML', layer=layer)
                    
                    # Skip empty layers
                    if layer_gdf.empty:
                        logging.info(f"Layer {layer} is empty, skipping")
                        continue
                    
                    # Log geometry types found in this layer
                    layer_geom_types = layer_gdf.geometry.type.unique()
                    geometry_type_by_layer[layer] = layer_geom_types
                    all_geometry_types.update(layer_geom_types)
                    
                    logging.info(f"Layer '{layer}' contains geometry types: {layer_geom_types}")
                
                except Exception as layer_analyze_error:
                    logging.warning(f"Error analyzing layer '{layer}': {str(layer_analyze_error)}")
            
            # Log all geometry types found
            logging.info(f"All geometry types found in KML: {all_geometry_types}")
            
            # If filtering by geometry type, check if any layer has matching types
            if apply_geometry_filter:
                matching_layers = []
                for layer, geom_types in geometry_type_by_layer.items():
                    # Check if any requested geometry type is in this layer
                    if any(gt in geometry_types_to_include for gt in geom_types):
                        matching_layers.append(layer)
                
                if not matching_layers:
                    return {
                        "success": False,
                        "error": f"No features found with the specified geometry types: {', '.join(geometry_types_to_include)}"
                    }
                
                logging.info(f"Layers containing requested geometry types: {matching_layers}")
            
            # Second pass: read and process layers
            for layer in available_layers:
                # Skip this layer if filtering and no matching geometries
                if apply_geometry_filter:
                    if layer not in geometry_type_by_layer:
                        continue
                        
                    layer_geom_types = geometry_type_by_layer[layer]
                    if not any(gt in geometry_types_to_include for gt in layer_geom_types):
                        logging.info(f"Skipping layer '{layer}' as it doesn't contain requested geometry types")
                        continue
                
                logging.info(f"Processing layer: {layer}")
                try:
                    layer_gdf = gpd.read_file(kml_path, driver='KML', layer=layer)
                    
                    # Skip empty layers
                    if layer_gdf.empty:
                        logging.info(f"Layer {layer} is empty, skipping")
                        continue
                    
                    # Add a layer name column to identify the source
                    layer_gdf['layer_name'] = layer
                    
                    # Apply geometry filtering within the layer if needed
                    if apply_geometry_filter:
                        original_count = len(layer_gdf)
                        layer_gdf = layer_gdf[layer_gdf.geometry.type.isin(geometry_types_to_include)]
                        filtered_count = len(layer_gdf)
                        
                        logging.info(f"Layer '{layer}': Filtered from {original_count} to {filtered_count} features")
                        
                        if layer_gdf.empty:
                            logging.info(f"Layer '{layer}' has no features after filtering, skipping")
                            continue
                        
                    # Combine with existing data
                    if combined_gdf is None:
                        combined_gdf = layer_gdf
                    else:
                        # Ensure the combined GeoDataFrame has all columns from both
                        for col in layer_gdf.columns:
                            if col not in combined_gdf.columns and col != 'geometry':
                                combined_gdf[col] = None
                        for col in combined_gdf.columns:
                            if col not in layer_gdf.columns and col != 'geometry':
                                layer_gdf[col] = None
                                
                        # Concatenate the dataframes
                        combined_gdf = gpd.pd.concat([combined_gdf, layer_gdf], ignore_index=True)
                        
                except Exception as layer_read_error:
                    logging.warning(f"Error reading layer '{layer}': {str(layer_read_error)}")
        
        except Exception as e:
            logging.exception("Error in layer processing, trying fallback of reading all at once")
            # Try to read all layers at once as a fallback
            try:
                combined_gdf = gpd.read_file(kml_path, driver='KML')
                logging.info(f"Successfully read all KML layers at once with {len(combined_gdf)} features")
            except Exception:
                logging.exception("Failed to read KML file at all")
                raise
        
        # Use the combined GeoDataFrame
        gdf = combined_gdf
        
        if gdf is None or gdf.empty:
            return {
                "success": False,
                "error": "No features found in the KML file"
            }
        
        # Apply geometry type filter if specified
        if geometry_types_to_include:
            logging.info(f"Filtering geometry types to include only: {geometry_types_to_include}")
            original_count = len(gdf)
            
            # Filter GeoDataFrame to only include specified geometry types
            gdf = gdf[gdf.geometry.type.isin(geometry_types_to_include)]
            
            filtered_count = len(gdf)
            logging.info(f"Filtered from {original_count} to {filtered_count} features based on geometry type")
            
            if gdf.empty:
                return {
                    "success": False,
                    "error": f"No features found with the specified geometry types: {', '.join(geometry_types_to_include)}"
                }
        
        # Use original uploaded filename (not the inner doc.kml name from KMZ)
        base_filename = original_base_filename

        # Save one shapefile per named layer using the layer name as the filename.
        # Single/unnamed layer → {base_filename}.shp
        # Multiple named layers → {layer_name}.shp (e.g. bldg.shp, line.shp, poly.shp)
        output_files = []
        named_layers = [l for l in available_layers if l]
        if len(named_layers) > 1 and 'layer_name' in gdf.columns:
            for layer_lbl, layer_gdf in gdf.groupby('layer_name'):
                safe = ''.join(c if c.isalnum() else '_' for c in str(layer_lbl)).strip('_')
                stem = safe if safe else base_filename
                clean = layer_gdf.drop(columns=['layer_name'], errors='ignore')
                output_files.extend(_save_gdf_by_geom_type(clean, output_dir, stem))
        else:
            clean_gdf = gdf.drop(columns=['layer_name'], errors='ignore')
            output_files = _save_gdf_by_geom_type(clean_gdf, output_dir, base_filename)

        # Get geometry types present in the data
        geometry_types = list(set(gdf.geometry.type))
        
        return {
            "success": True,
            "output_files": output_files,
            "feature_count": len(gdf),
            "geometry_types": geometry_types
        }
        
    except Exception as e:
        logging.exception("Error in KML conversion")
        # Try the fallback method
        logging.info("Attempting fallback conversion method")
        try:
            return fallback_convert_kml_to_shapefile(kml_path, output_dir, geometry_types_to_include, original_base_filename)
        except Exception as fallback_error:
            logging.exception("Fallback conversion also failed")
            return {
                "success": False,
                "error": f"Conversion failed: {str(e)}. Fallback also failed: {str(fallback_error)}"
            }
    finally:
        # Clean up temporary directories
        for temp_dir in temp_dirs:
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except Exception:
                pass  # Ignore cleanup errors

def fallback_convert_kml_to_shapefile(kml_path, output_dir, geometry_types_to_include=None, original_base_filename=None):
    """
    Fallback method to convert KML to Shapefile using an alternative approach
    in case the primary geopandas method fails.
    
    Args:
        kml_path (str): Path to the input KML file
        output_dir (str): Directory to save the output Shapefile
        geometry_types_to_include (list, optional): List of geometry types to include.
            If provided, only features with these geometry types will be included.
        original_base_filename (str, optional): The original uploaded filename base to use
            for output files. If not provided, derived from kml_path.
    
    Returns:
        dict: Dictionary containing conversion results
    """
    temp_dirs = []  # Store temporary directories to prevent premature deletion
    
    # Use provided original filename, or fall back to deriving from kml_path
    if original_base_filename is None:
        original_base_filename = os.path.splitext(os.path.basename(kml_path))[0]
    
    try:
        # Handle KMZ files by extracting them first
        if kml_path.lower().endswith(".kmz"):
            # Create a temporary directory that will exist throughout the function's scope
            kmz_temp_dir = tempfile.mkdtemp()
            temp_dirs.append(kmz_temp_dir)  # Save reference to prevent deletion
            
            # Extract KMZ file (which is just a zip file)
            with ZipFile(kml_path, 'r') as zip_ref:
                zip_ref.extractall(kmz_temp_dir)
            
            # Find the KML file in the extracted directory
            kml_files = [f for f in os.listdir(kmz_temp_dir) if f.lower().endswith('.kml')]
            if not kml_files:
                return {
                    "success": False,
                    "error": "No KML file found inside the KMZ archive"
                }
            
            # Use the first KML file found (but keep original_base_filename from the KMZ)
            kml_path = os.path.join(kmz_temp_dir, kml_files[0])
        
        # Try a different approach - use fiona directly
        try:
            # Register KML driver (it may not be registered yet)
            fiona.drvsupport.supported_drivers['KML'] = 'rw'
            fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
            
            # Get list of layers
            layer_names = fiona.listlayers(kml_path)
            logging.info(f"Fallback found layers: {layer_names}")
            
            # Initialize counters and metadata
            feature_count = 0
            geometry_types = set()
            output_files = []
            
            # Use original uploaded filename (not the inner doc.kml name from KMZ)
            base_filename = original_base_filename
            output_path = os.path.join(output_dir, f"{base_filename}.shp")
            
            # Process each layer
            all_data = []
            
            # If we have no layers or a single default layer, try to read without a layer name
            if not layer_names or (len(layer_names) == 1 and layer_names[0] == ''):
                with fiona.open(kml_path, 'r', driver='KML') as src:
                    schema = src.schema.copy()
                    crs = src.crs
                    
                    # Process all features
                    for feature in src:
                        geom_type = feature['geometry']['type'] if feature.get('geometry') else None
                        
                        # Add to geometry types set if it exists
                        if geom_type:
                            geometry_types.add(geom_type)
                        
                        # Apply geometry filter if specified
                        if geometry_types_to_include and geom_type not in geometry_types_to_include:
                            logging.info(f"Skipping feature with geometry type {geom_type} (not in filter: {geometry_types_to_include})")
                            continue
                            
                        all_data.append(feature)
                    
                    feature_count = len(all_data)
                    
                    # Write to shapefile if we have data
                    if all_data:
                        with fiona.open(
                            output_path, 'w',
                            driver='ESRI Shapefile',
                            schema=schema,
                            crs=crs
                        ) as dst:
                            for feature in all_data:
                                dst.write(feature)
            else:
                # Save one shapefile per named layer: {base}_{layer_name}.shp
                shp_files = []
                for layer_name in layer_names:
                    try:
                        layer_gdf = gpd.read_file(kml_path, driver='KML', layer=layer_name)
                        if layer_gdf.empty:
                            continue
                        if geometry_types_to_include:
                            layer_gdf = layer_gdf[layer_gdf.geometry.type.isin(geometry_types_to_include)]
                        if layer_gdf.empty:
                            continue
                        for gt in layer_gdf.geometry.type.unique():
                            geometry_types.add(gt)
                        feature_count += len(layer_gdf)
                        safe = ''.join(c if c.isalnum() else '_' for c in layer_name).strip('_')
                        stem = safe if safe and len(layer_names) > 1 else base_filename
                        shp_files.extend(_save_gdf_by_geom_type(layer_gdf, output_dir, stem))
                    except Exception as le:
                        logging.warning(f"Skipping layer '{layer_name}': {le}")
            
            # Collect all shapefile component files that were created
            if not shp_files:
                shp_files = []
                for root, dirs, files in os.walk(output_dir):
                    for file in files:
                        if file.startswith(base_filename) and file.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
                            shp_files.append(os.path.join(root, file))
            
            if not shp_files:
                return {
                    "success": False,
                    "error": "No Shapefile components were created"
                }
            
            return {
                "success": True,
                "output_files": shp_files,
                "feature_count": feature_count,
                "geometry_types": list(geometry_types)
            }
            
        except Exception as fiona_error:
            logging.exception("Error in fiona direct fallback conversion")
            return {
                "success": False,
                "error": f"Fallback conversion failed: {str(fiona_error)}"
            }
        
    except Exception as e:
        logging.exception("Error in fallback conversion")
        return {
            "success": False,
            "error": f"Fallback conversion failed: {str(e)}"
        }
    finally:
        # Clean up temporary directories
        for temp_dir in temp_dirs:
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except Exception:
                pass  # Ignore cleanup errors
