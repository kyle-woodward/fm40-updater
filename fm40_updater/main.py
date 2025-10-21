from dist import convert_bs_to_dist, combine_dist_rasters
from fm40_updater import update_fm40_raster
import os
import glob
import re
from pathlib import Path
import argparse

if __name__ == "__main__":
    """
    This script will:
    1. Find all burn severity (BS) rasters in the 'bs_folder' directory matching `bs_years` you provide.
    2. For each BS raster, extract the fire year from its filename, and convert it from burn severity to LANDFIRE-style DIST raster, 
        assinging each valid BS pixel with a DIST value in alignment of its fire year in relation to the effective year you provide.
    3. Combine all generated DIST rasters into a single composite DIST raster,
       prioritizing the most recent/significant disturbance in areas of overlap.
    4. Apply an update to your original FM40 raster using the combined DIST raster and ruleset .csv
       to produce a new, updated FM40 raster.
    """
    parser = argparse.ArgumentParser(description="")
    parser.add_argument(
        "--inputfm",
        type=str,
        required=True,
        help="Path to the baseline FM40 raster to be updated"
    )
    parser.add_argument(
        "--bsfolder",
        type=str,
        required=True,
        help="Path to the folder containing burn severity (BS) rasters"
    )
    parser.add_argument(
        "--bsyears",
        type=int,
        nargs="+",
        required=True,
        help="list of BS years rasters to process (e.g. 2017 2018)"
    )
    
    parser.add_argument(
        "--effyear",
        type=int,
        required=True,
        help="The effective year for the fuel update"
    )

    parser.add_argument(
        "--ruleset",
        type=str,
        required=True,
        help="Path to the CSV file containing the update rules"
    )
    args = parser.parse_args()

    # to be CLI args..
    # input_fm40 = Path("/app/data/fm40_inputs/lf2016_fm40_clipped.tif")
    # bs_folder = Path("/app/data/bs_inputs") # get from cli arg otherwise this is default
    # ruleset = Path("/app/fm40_updater/rules.csv") # get from cli arg otherwise this is default
    # bs_years = [2017,2018]
    # effective_year = 2018

    input_fm40 = args.inputfm
    bs_folder = args.bsfolder
    bs_years = args.bsyears
    ruleset = args.ruleset 
    effective_year = args.effyear
    
    out_dists = Path("/app/data/dists")
    out_fm40 = Path("/app/data/outputs")
    
    if ruleset is not None and Path(ruleset).exists():
        ruleset = Path(ruleset)
        print(f"Provided ruleset at {ruleset}")
    else:
        raise ValueError("No valid ruleset csv path was provided")
        
    for folder in [out_dists,out_fm40]:
        folder.mkdir(parents=True, exist_ok=True)
    
    # get the targeted list of BS rasters in bs folder by matching them to bs_years (NOTE: assumption is that year ('YYYY') is in the filename)
    all_bs_rasters = glob.glob(f"{bs_folder}/*.tif")
    dist_paths = []
    bs_rasters = []
    for year in bs_years:
        bs_raster = [filename for filename in all_bs_rasters if (str(year) in filename)]
        if bs_raster:
            bs_rasters.append(bs_raster[0])
    
    assert len(bs_rasters)==len(bs_years), \
    f"Expected {len(bs_years)} files (number of bs_years), but found {len(bs_rasters)} matches."
    
    # --- Step 1: Convert all annual BS rasters to DIST rasters ---
    for bs_path in bs_rasters:
        # Assumes fire year is in the filename like '..._2017.tif'
        fire_year = int(os.path.splitext(bs_path)[0][-4:])
        # Use regex to robustly find a 4-digit year in the filename.
        match = re.search(r'(\d{4})', os.path.basename(bs_path))
        if not match:
            raise ValueError(f"Could not find a 4-digit year in filename '{Path(bs_path).stem}'. Ensure that all of your BS files contain a YYYY formatted year in their filename and try again.")
        
        fire_year = int(match.group(1))

        output_dist_path = os.path.join(out_dists, f"{Path(bs_path).stem}_dist_{fire_year}_for_{effective_year}.tif")
        if Path(output_dist_path).exists():
            print(f"Skipping creation of {output_dist_path}: already exists.")
            dist_paths.append(output_dist_path)
        else:
            dist_path = convert_bs_to_dist(bs_path, fire_year, effective_year, output_dist_path, input_fm40)
            if dist_path:
                dist_paths.append(dist_path)

    # --- Step 2: Combine the individual DIST rasters into a final product ---
    final_output_path = os.path.join(out_dists, f"dist_combined_{effective_year}.tif")
    if Path(final_output_path).exists():
        print(f"Skipping creation of {final_output_path}: already exists.")

    else:
        combined_dist_raster = combine_dist_rasters(dist_paths, final_output_path)

    # --- Step 3: Update the original FM40 raster using the combined DIST raster ---
    updated_fm40_path = os.path.join(out_fm40, f"fm40_updated_{effective_year}.tif")
    if Path(updated_fm40_path).exists():
        print(f"Skipping creation of {updated_fm40_path}: already exists.")
    else:
        update_fm = update_fm40_raster(input_fm40, combined_dist_raster, ruleset, updated_fm40_path)