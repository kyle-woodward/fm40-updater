# FM40 Updater 

Simplified, annualized FM40 updates from a baseline Landfire FM40 using MTBS Burn Severity-derived Landfire DIST rasters and a user-defined ruleset.

## Description

This project implements a simplified FM40 update process compared to LANDFIRE's actual fuel update methods (Landfire Total Fuel Change Tool). Rulesets can be user-defined in a rules.csv file. Currently the process supports only parent fuel group remappings, meaning that while all possible unique combo of (`DIST_code`,`original_FM40_code`) encountered in the raster data is mapped,
possible output fuel class is one of (GR, GS, SH, TU, TL, SB). Any combo of (`DIST_code`,`original_FM40_code`) not covered in the `rules.csv` will be treated as no disturbance and that pixel will remain `original_fm40_code`.



## Required Data 

You will need:
* Baseline FM40 .tif
* Folder containing MTBS annual burn severity raster .tifs
* A ruleset.csv. We have both a `rules_template.csv` and the user-defined `rules.csv` tracked in the repo currently. If you make another one, it must follow the same schema as those examples and you should provide its filepath to the `--ruleset` argument. 

The annual MTBS tifs and LF2019 FM40 are sitting on cloud storage, but others are retrievable from MTBS and Landfire.

`data` Directory should look like this, intermdiate and output folders will be generated automatically in the container upon runtime.
```
./data/
    fm40_inputs/
        conus_landfire_fbfm40_LF2019_FBFM40_200.tif
    bs_inputs/
        mtbs_CONUS_2016.tif
        mtbs_CONUS_2017.tif
        mtbs_CONUS_2018.tif
        etc...
```

## Docker container

At root, run:

```bash
sudo make build
sudo make run
```

## Runtime

`main.py` is the command-line utility allowing us to create any particular effective-year fm40 update. 

```
usage: main.py [-h] --inputfm INPUTFM --bsfolder BSFOLDER --bsyears BSYEARS [BSYEARS ...] --effyear EFFYEAR --ruleset RULESET

options:
  -h, --help            show this help message and exit
  --inputfm INPUTFM     Path to the baseline FM40 raster to be updated
  --bsfolder BSFOLDER   Path to the folder containing burn severity (BS) rasters
  --bsyears BSYEARS [BSYEARS ...]
                        list of BS years rasters to process (e.g. 2017 2018)
  --effyear EFFYEAR     The effective year for the fuel update
  --ruleset RULESET     Path to the CSV file containing the update rules
```

example:

```python
python fm40_updater/main.py --inputfm /path/to/baseline/fm40.tif --bsfolder /path/to/bs_folder --bsyears 2017 2018 -eff_year 2019 

```

## Batch processing

TO produce an annual product stack in one batch process, see [`batch.sh`](/batch.sh). This is also what produced the data delivered.

## Code Breaking Assumptions

* We assume that files in `--bsfolder` are named such that the year (YYYY) of the file is in the filename. This is the case by default for teh MTBS data available at mtbs.gov. This implementation allows us to store all BS data in the same folder, but for a given run we change `--bsyears` and `--effyear` arguments. So if that filename convention condition is not met, we raise an exception asking you to fix that. 

* We will also check that `-effyear` is greater than all years provided to `--bsyears` as a logic check. Same thing, we'll just raise an exception to call it to your attention.



