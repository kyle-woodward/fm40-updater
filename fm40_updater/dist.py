import numpy as np
import rasterio
from utils import time_function, aligned_vrt

import concurrent.futures
import threading

# Define the ranking of DIST codes from most to least impactful.
# Lower rank number = more impactful.
# This ranking prioritizes severity first, then recency.
DIST_IMPACT_RANKING = {
    # High Severity (Sev Code 3)
    131: 1,  # High Sev, <1 yr
    132: 2,  # High Sev, 1-3 yrs
    133: 3,  # High Sev, 3-10 yrs
    # Moderate Severity (Sev Code 2)
    121: 4,  # Mod Sev, <1 yr
    122: 5,  # Mod Sev, 1-3 yrs
    123: 6,  # Mod Sev, 3-10 yrs
    # Low Severity (Sev Code 1)
    111: 7,  # Low Sev, <1 yr
    112: 8,  # Low Sev, 1-3 yrs
    113: 9,  # Low Sev, 3-10 yrs
}
# A large number for values that are not valid DIST codes (like nodata)
# so they are ranked last and never chosen over a valid disturbance.
DEFAULT_RANK = 99

@time_function
def convert_bs_to_dist(
    bs_raster_path: str,
    fire_year: int,
    effective_year: int,
    output_dist_path: str,
    align_to:str
) -> None:
    """Converts a burn severity (BS) raster to a LANDFIRE-style disturbance (DIST) raster.

    This function takes a single-year burn severity raster and converts it to a
    disturbance raster based on a defined schema. The schema encodes disturbance
    type (wildfire), severity, and time since disturbance relative to an
    'effective year'.

    The DIST code is a 3-digit integer calculated as:
    100 + (Severity Code * 10) + (Time Code)

    - Disturbance Type: 1 (Wildfire)
    - Severity Code: 1 (Low), 2 (Moderate), 3 (High), 
    - Time Code: 1 (<1 yr), 2 (2-5 yrs), 3 (6-10 yrs)

    The function processes the raster in chunks to manage memory usage.

    Args:
        bs_raster_path (str): Path to the input burn severity raster.
        fire_year (int): The calendar year the fire occurred.
        effective_year (int): The target year for the fuel update.
        output_dist_path (str): Path to write the output DIST raster.
    Returns:
        output_dist_path (str): Path to write the output DIST raster.
    """
    # --- Input Validation ---
    if fire_year > effective_year:
        raise ValueError(f"Fire year ({fire_year}) cannot be after the effective year ({effective_year}). Check your data and arguments.")

    # Default mapping for MTBS burn severity classes to LANDFIRE severity codes
    bs_to_dist_sev_map = {
        5: 1,  # Increased Greenness -> DIST Sev 1
        4: 3,  # High Severity -> DIST Sev 3
        3: 2,  # Moderate Severity -> DIST Sev 2
        2: 1,  # Low Severity -> DIST Sev 1
        1: 1,  # Unburned to Low Severity -> DIST Sev 1
    }

    # 1. Calculate Time Since Disturbance and determine Time Code
    years_since_fire = effective_year - fire_year
    if years_since_fire < 1:
        time_code = 1
    elif 1 <= years_since_fire <= 5:
        time_code = 2
    elif 5 < years_since_fire <= 10:
        time_code = 3
    else:
        # If outside the 10-year window, this fire is not relevant for the update.
        # We can either raise an error or simply create an empty/nodata raster.
        # For now, let's log a warning and proceed to create a nodata raster.
        print(f"Warning: Fire year {fire_year} is more than 10 years before effective year {effective_year}.")
        time_code = None # This will result in all nodata

    # 2. Open input raster and get metadata for the output raster
    with rasterio.open(bs_raster_path) as src:
        
        # re-align bs raster to alignment source (your FM40 raster)
        with rasterio.open(align_to) as alignment_src:
            aligned_src = aligned_vrt(alignment_src, src)
            
            profile = aligned_src.profile
            profile.update(dtype=rasterio.uint16, 
                           count=1, 
                           compress='lzw', 
                           nodata=0, # Use 0 as nodata for DIST
                           driver='GTiff') 

            # 3. Create the output raster
            with rasterio.open(output_dist_path, 'w', **profile) as dst:
                # 4. Iterate over the raster in chunks (windows)
                for ji in aligned_src.block_windows(1):
                    window = ji[1]
                    bs_data = aligned_src.read(1, window=window)

                    # Initialize output array with nodata value
                    dist_data = np.full(bs_data.shape, profile['nodata'], dtype=profile['dtype'])

                    if time_code is not None:
                        # 5. Apply remapping logic using numpy.select for efficiency
                        
                        # Define conditions based on the input BS values
                        conditions = [
                            bs_data == bs_val for bs_val in bs_to_dist_sev_map.keys()
                        ]
                        
                        # Define corresponding choices for the DIST code
                        choices = [
                            100 + (sev_code * 10) + time_code
                            for sev_code in bs_to_dist_sev_map.values()
                        ]

                        # np.select will apply choices where conditions are met,
                        # and use the default value (nodata) otherwise.
                        dist_data = np.select(conditions, choices, default=profile['nodata']).astype(profile['dtype'])

                    # 6. Write the processed chunk to the output raster
                    # We explicitly write to the first band (index 1). When a single
                    # band index is provided, rasterio's write method correctly
                    # expects a 2D array, which matches our dist_data.
                    dst.write(dist_data, 1, window=window)

    print(f"Successfully created DIST raster at {output_dist_path}")
    return output_dist_path

@time_function
def combine_dist_rasters(dist_raster_paths: list[str], output_path: str) -> str:
    """
    Combines multiple LANDFIRE-style disturbance (DIST) rasters into one.

    This function processes rasters in a memory-efficient, windowed manner.
    The combination rule prioritizes the most impactful disturbance. When pixels
    from multiple rasters overlap, the one with the highest impact is chosen.
    Impact is determined by a ranking system where higher severity is more
    impactful, and for disturbances of the same severity, more recent events
    (i.e., smaller time codes) are more impactful.

    Args:
        dist_raster_paths (list[str]): A list of paths to the DIST rasters to combine.
        output_path (str): The path for the combined output raster.

    Returns:
        str: The path to the created output raster, or None if no inputs were provided.
    """
    if not dist_raster_paths:
        print("Warning: No DIST rasters provided to combine. No output will be generated.")
        return None

    print(f"Combining {len(dist_raster_paths)} DIST rasters into {output_path}...")

    # Open all source files once and keep them in a list.
    src_files = [rasterio.open(p) for p in dist_raster_paths]

    try:
        # 1. Use the first raster to define the output profile (CRS, transform, etc.)
        # This assumes all input rasters are aligned and share the same grid.
        profile = src_files[0].profile
        nodata_val = src_files[0].nodata if src_files[0].nodata is not None else 0

        # 2. Create the output raster file
        with rasterio.open(output_path, 'w', **profile) as dst:
            # 3. Iterate over the raster in chunks (windows)
            for ji in src_files[0].block_windows(1):
                window = ji[1]

                # 4. Read the same window from all (already open) input rasters.
                all_data = np.array([src.read(1, window=window) for src in src_files])

                # 5. Apply the combination logic for the current chunk.
                map_func = np.vectorize(DIST_IMPACT_RANKING.get)
                impact_ranks = map_func(all_data, DEFAULT_RANK)
                min_rank_idx = np.argmin(impact_ranks, axis=0)

                # Use the index array to gather the final pixel values from the original data stack.
                idx_3d = np.expand_dims(min_rank_idx, axis=0)
                final_chunk = np.take_along_axis(all_data, idx_3d, axis=0).squeeze(axis=0)

                # Ensure that pixels that were nodata in ALL inputs remain nodata in the output.
                nodata_mask = (all_data == nodata_val)
                final_chunk[np.all(nodata_mask, axis=0)] = nodata_val

                # 6. Write the combined chunk to the output raster.
                dst.write(final_chunk.astype(profile['dtype']), 1, window=window)
    except Exception as e:
        print(f"Trouble processing {output_path}: {e}")
    # finally:
    #     # Ensure all source files are closed.
    #     for src in src_files:
    #         src.close()

    print(f"Successfully created combined DIST raster at {output_path}")
    return output_path 

@time_function
def combine_dist_rasters_multi(dist_raster_paths: list[str], output_path: str, num_workers:int) -> str:
    """
    NOTE: NOT USING - Have Determined this is actually slower than single-threaded window-based processing due to worker overhead. 

    Same as `combine_dist_rasters()` but use multiprocessing.

    This function processes rasters in a memory-efficient, windowed manner.
    The combination rule prioritizes the most impactful disturbance. When pixels
    from multiple rasters overlap, the one with the highest impact is chosen.
    Impact is determined by a ranking system where higher severity is more
    impactful, and for disturbances of the same severity, more recent events
    (i.e., smaller time codes) are more impactful.

    Args:
        dist_raster_paths (list[str]): A list of paths to the DIST rasters to combine.
        output_path (str): The path for the combined output raster.

    Returns:
        str: The path to the created output raster, or None if no inputs were provided.
    """
    if not dist_raster_paths:
        print("Warning: No DIST rasters provided to combine. No output will be generated.")
        return None

    print(f"Combining {len(dist_raster_paths)} DIST rasters into {output_path}...")

    # Open all source files once and keep them in a list.
    src_files = [rasterio.open(p) for p in dist_raster_paths]

    # 1. Use the first raster to define the output profile (CRS, transform, etc.)
    # This assumes all input rasters are aligned and share the same grid.
    profile = src_files[0].profile
    nodata_val = src_files[0].nodata if src_files[0].nodata is not None else 0

    # 2. Create the output raster file
    with rasterio.open(output_path, 'w', **profile) as dst:
        # store all windows to process in a variable so we can map multiprocessing over
        windows = [window for ij, window in dst.block_windows()]

        # We cannot write to the same file from multiple threads
        # without causing race conditions. To safely read/write
        # from multiple threads, we use a lock to protect the
        # DatasetWriter. Concurrent reads are generally safe.
        write_lock = threading.Lock()
        
        def process(window):
            # 4. Read the same window from all (already open) input rasters.
            all_data = np.array([src.read(1, window=window) for src in src_files])
            # 5. Apply the combination logic for the current chunk.
            map_func = np.vectorize(DIST_IMPACT_RANKING.get)
            impact_ranks = map_func(all_data, DEFAULT_RANK)
            min_rank_idx = np.argmin(impact_ranks, axis=0)

            # Use the index array to gather the final pixel values from the original data stack.
            idx_3d = np.expand_dims(min_rank_idx, axis=0)
            final_chunk = np.take_along_axis(all_data, idx_3d, axis=0).squeeze(axis=0)

            # Ensure that pixels that were nodata in ALL inputs remain nodata in the output.
            nodata_mask = (all_data == nodata_val)
            final_chunk[np.all(nodata_mask, axis=0)] = nodata_val

            # Use a lock to prevent race conditions when writing to the output file.
            with write_lock:
                # Explicitly write to band 1. This was the source of the error.
                dst.write(final_chunk.astype(profile['dtype']), 1, window=window)

        # We map the process() function over the list of
        # windows.
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=num_workers
        ) as executor:
            executor.map(process, windows)

    print(f"Successfully created combined DIST raster at {output_path}")
    return output_path 

if __name__ == "__main__":
    import os
    from pathlib import Path

    # Get the project root directory (which is the parent of this script's directory)
    project_root = Path(__file__).parent.parent

    # Construct absolute paths to the data files
    dist_2016 = project_root / "data/dists/mtbs_CONUS_2016_dist_2016_for_2018_aligntest.tif"
    dist_2017 = project_root / "data/dists/mtbs_CONUS_2017_dist_2017_for_2018_aligntest.tif"
    
    output_combined = project_root / "data/dists/combined_dist_2018_test.tif"

    list_r = [str(dist_2016), str(dist_2017)]
    combined = combine_dist_rasters(list_r, str(output_combined)) # Function 'combine_dist_rasters' : Elapsed time 2044.4889 seconds 
