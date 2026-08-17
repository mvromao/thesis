"""Analysis pipeline for the 4G/5G testbed measurement campaigns.

Replaces the 19 ad-hoc scripts in ../scripts/, which all hardcoded a data root
(`thesis/Thesis/testing_data/`) that no longer exists.

Three stages:

    extract.py          raw logs          -> extracted/<log_unit>/*.csv.gz
    build_tables.py     extracted/ + iperf-> data_v2/*.csv
    compare_baseline.py data_v2/ vs data/ -> regression report

Pure standard library (plus optional numpy). No pandas, no pyarrow: the lab and
write-up machines do not have them, and a thesis artefact should run anywhere a
CPython interpreter does.
"""

__all__ = ["paths", "units", "logscan", "console", "iperf", "extract"]
