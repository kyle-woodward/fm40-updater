import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from utils import expand_ruleset, time_function, aligned_vrt

@time_function
def update_fm40_raster(
    original_fm40_path: str,
    dist_raster_path: str,
    ruleset_csv_path: str,
    output_fm40_path: str,
) -> str:
    """
    Updates an original FM40 raster based on a disturbance (DIST) raster
    and a provided ruleset.

    The ruleset specifies how unique combinations of DIST code and original FM40 code
    map to a new FM40 code. The rules are defined by parent classes, which are
    expanded into numeric codes for processing. If a combination is not found
    in the ruleset, the original FM40 code is retained.

    Args:
        original_fm40_path (str): Path to the input original FM40 raster.
        dist_raster_path (str): Path to the input combined DIST raster.
        ruleset_csv_path (str): Path to the CSV file containing the update rules.
        output_fm40_path (str): Path to write the updated FM40 raster.

    Returns:
        str: The path to the created output FM40 raster, or None if an error occurs.
    """
    print(f"Updating FM40 raster {original_fm40_path} with DIST raster {dist_raster_path}...")

    # 1. Load the update ruleset from CSV
    update_rules = expand_ruleset(ruleset_csv_path)

    # 2. Open input rasters and get metadata for the output raster
    with rasterio.open(original_fm40_path) as src_fm40, \
         rasterio.open(dist_raster_path) as src_dist:

        # Use FM40 as the reference for grid alignment and output profile
        profile = src_fm40.profile
        # Output FM40 should be uint16 to accommodate a wider range of FM40 codes.
        profile.update(dtype=rasterio.int16, count=1, compress='lzw')
        # Use the nodata from the original FM40, or a sensible default like 0 if not present.
        fm40_nodata = src_fm40.nodata if src_fm40.nodata is not None else 0
        dist_nodata = src_dist.nodata if src_dist.nodata is not None else 0
        profile.update(nodata=fm40_nodata)

        # Check if DIST raster needs to be aligned to the FM40 raster
        needs_alignment = (
            src_dist.crs != src_fm40.crs or
            src_dist.transform != src_fm40.transform or
            src_dist.shape != src_fm40.shape
        )

        # Choose the correct source for DIST data: the original or the warped VRT
        dist_src = aligned_vrt(src_fm40, src_dist) if needs_alignment else src_dist
        if needs_alignment:
            print("DIST raster does not align with FM40 raster. Using on-the-fly reprojection (WarpedVRT).")

        # 3. Create the output raster
        with rasterio.open(output_fm40_path, 'w', **profile) as dst_fm40:
            # 4. Iterate over the raster in chunks (windows)
            for ji in src_fm40.block_windows(1):
                window = ji[1]
                fm40_data = src_fm40.read(1, window=window)
                # Read from the (potentially warped) DIST source using the same window
                dist_data = dist_src.read(1, window=window)

                # Create a vectorized lookup function
                def get_new_fm40(d_code, o_code):
                    both_nodata = (d_code == dist_nodata) and (o_code == fm40_nodata)
                    no_dist = (d_code == dist_nodata)
                    nonburnable = (o_code <= 100)
                    if both_nodata:
                        new_code = fm40_nodata # Propagate nodata
                    elif no_dist or nonburnable:
                        new_code = o_code # leave non-disturbed unchanged
                    else:
                        new_code = update_rules.get((d_code, o_code))
                    return new_code

                vectorized_lookup = np.vectorize(get_new_fm40)

                # Apply the vectorized lookup to the entire chunk
                updated_fm40_chunk = vectorized_lookup(dist_data, fm40_data).astype(profile['dtype'])

                # Ensure nodata values are correctly propagated.
                # updated_fm40_chunk[fm40_data == fm40_nodata] = fm40_nodata
                # updated_fm40_chunk[dist_data == dist_nodata] = fm40_nodata

                # 5. Write the processed chunk to the output raster.
                dst_fm40.write(updated_fm40_chunk, 1, window=window)

    print(f"Successfully created updated FM40 raster at {output_fm40_path}")
    return output_fm40_path


if __name__ == "__main__":
    # update_fm40_raster("inputs/lf2016_fm40_clipped.tif",
    #                    "inputs/dist_combined_2018.tif",
    #                    "fm40_updater/fm40_update_rules.csv",
    #                    "outputs/fm40_updated_2018_clipped.tif")
    update_fm40_raster("inputs/conus_landfire_fbfm40_LF2019_FBFM40_200.tif",
                       "inputs/mtbs_bs_dist_2017_for_2018.tif",
                       "fm40_updater/fm40_update_rules.csv",
                       "outputs/fm40_updated_2018.tif")