#!/bin/bash

# Define fixed parameters
INPUT_FM40="/app/data/fm40_inputs/conus_landfire_fbfm40_LF2019_FBFM40_200.tif"
BS_FOLDER="/app/data/bs_inputs"
RULESET="/app/fm40_updater/rules.csv"

# Define arrays for varying parameters
BS_YEARS=(
    "2017"
    "2017 2018"
    "2017 2018 2019"
    "2017 2018 2019 2020"
    "2017 2018 2019 2020 2021"
    "2017 2018 2019 2020 2021 2022"
    "2017 2018 2019 2020 2021 2022 2023"
    )

EFF_YEARS=(
    "2018"
    "2019"
    "2020"
    "2021"
    "2022"
    "2023"
    "2024"
    )

# Loop through the indices of the EFF_YEARS array to run 7 jobs.
for i in "${!EFF_YEARS[@]}"; do
  # Get the corresponding values for this run
  eff_year="${EFF_YEARS[$i]}"
  bs_year_group="${BS_YEARS[$i]}"

  echo "--- RUN $((i+1))/7 ---"
  echo "Running main.py with --effyear $eff_year and --bsyears $bs_year_group"
  python /app/fm40_updater/main.py \
    --inputfm "$INPUT_FM40" \
    --bsfolder "$BS_FOLDER" \
    --ruleset "$RULESET" \
    --bsyears $bs_year_group \
    --effyear "$eff_year"
  echo "----------------------------------------------------"
done

echo "All runs completed."
