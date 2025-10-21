import pandas as pd
from fm40classes import ClassMap
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT


def expand_ruleset(ruleset_csv_path: str):
        try:
            rules_df = pd.read_csv(ruleset_csv_path)
            # Expand class-based rules into a numeric lookup dictionary.
            # Keys: (DIST_code, original_FM40_code) numeric tuple
            # Values: new_FM40_code (numeric)
            update_rules = {}
            for _, row in rules_df.iterrows():
                dist_code = int(row['DIST_code'])
                original_fm40_class = row['original_FM40_code']
                new_fm40_class = row['new_FM40_code']

                original_fm40_codes = ClassMap.get(original_fm40_class)
                if not original_fm40_codes:
                    print(f"Warning: Original FM40 class '{original_fm40_class}' in ruleset not found in ClassMap. Skipping rule.")
                    continue

                # Determine the new numeric code. If new_FM40_class is blank/NaN,
                # new_fm40_code will be None, signifying 'no change'.
                new_fm40_code = None
                if pd.notna(new_fm40_class):
                    new_fm40_code_list = ClassMap.get(new_fm40_class)
                    if new_fm40_code_list:
                        # IMPORTANT NOTE HERE: Per convention, the new code is the first value in the class list.
                        # we are not accommodating within-group specificity in the updates atm
                        new_fm40_code = new_fm40_code_list[0]
                    else:
                        print(f"Warning: New FM40 class '{new_fm40_class}' in ruleset not found in ClassMap. Treating as 'no change'.")

                # Expand the class-based rule into numeric rules
                for original_code in original_fm40_codes:
                    update_rules[(dist_code, original_code)] = new_fm40_code
            print(f"Loaded and expanded {len(rules_df)} class-based rules from {ruleset_csv_path} into {len(update_rules)} numeric rules.")

        except FileNotFoundError:
            print(f"Error: Ruleset CSV not found at {ruleset_csv_path}")
            return None
        except Exception as e:
            print(f"Error loading ruleset CSV: {e}")
            return None
        return update_rules

import time
import functools

def time_function(func):
    """
    A decorator that measures and prints the execution time of the decorated function.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()  # Use perf_counter for more precise timing
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"Function '{func.__name__}' : Elapsed time {duration:.4f} seconds ")
        return result
    return wrapper


def aligned_vrt(src:rasterio.io.DatasetReader,
                dst:rasterio.io.DatasetReader
                ) -> rasterio.vrt.WarpedVRT:
    """Align destination raster with source raster, returning an in-memory virtual raster (VRT) """

    dist_nodata = src.nodata if src.nodata is not None else 0
    return WarpedVRT(dst,
                    crs=src.crs,
                    transform=src.transform,
                    width=src.width,
                    height=src.height,
                    resampling=Resampling.nearest, # all of our datasets are categorical
                    nodata=dist_nodata)


if __name__ == "__main__":
    src = rasterio.open("/app/data/fm40_inputs/conus_landfire_fbfm40_LF2019_FBFM40_200.tif")
    dst = rasterio.open("/app/data/bs_inputs/mtbs_CONUS_2016.tif")
    print(type(src), type(dst))
    print(src.shape , dst.shape)
    print(src.crs, dst.crs)
    print(src.transform, dst.transform)

    print('='*20)
    v = aligned_vrt(src,dst)
    print(type(v))
    print(v.shape)
    print(v.crs)
    print(v.transform)

    # Read the data from the WarpedVRT into a NumPy array in memory.
    # This avoids a GDAL error when trying to write directly from a VRT source.
    data_to_write = v.read()

    with rasterio.open("/app/data/test_vrt.tif", 'w', **src.profile) as dst_file: # must use src.profile bc v.profile indicates 'VRT' as driver which is unsupported
        dst_file.write(data_to_write)
    