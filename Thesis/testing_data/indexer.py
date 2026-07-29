import os
import re
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import pandas as pd

# Regex patterns for srsRAN log layers
LAYER_PATTERN = re.compile(r'\[(PHY|MAC|RLC|RRC|NGAP|S1AP|GTPU)\s*\]')
SINR_PATTERN = re.compile(r'sinr=([\d\.]+)dB')
MCS_PATTERN = re.compile(r'mod=(QPSK|16QAM|64QAM|256QAM)')
TBS_PATTERN = re.compile(r'tbs=(\d+)')

def process_experiment_folder(folder_path: Path):
    """Processes a single leaf experiment directory."""
    parts = folder_path.parts
    # Extract metadata: ./4G or 5G / Loc_X_Ym / TCP or UDP / DL or UL
    tech, loc, protocol, direction = parts[-4], parts[-3], parts[-2], parts[-1]
    
    dist_match = re.search(r'(\d+)m$', loc)
    distance_m = int(dist_match.group(1)) if dist_match else None
    
    # Locate main log file (enb.log or gnb.log)
    raw_log = next((folder_path / f for f in ["gnb.log", "enb.log"] if (folder_path / f).exists()), None)
    
    parsed_lines = []
    time_series_kpis = []
    
    if raw_log:
        split_dir = folder_path / "split"
        split_dir.mkdir(exist_ok=True)
        
        # Dictionary of file handles for layer splitting
        split_files = {}
        
        with open(raw_log, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = LAYER_PATTERN.search(line)
                layer = match.group(1) if match else "OTHER"
                
                # 1. Write to split text log
                if layer not in split_files:
                    split_files[layer] = open(split_dir / f"{layer}.log", "w")
                split_files[layer].write(line)
                
                # 2. Extract structured log record for Parquet indexing
                parsed_lines.append({
                    "layer": layer,
                    "raw_text": line.strip()
                })
                
                # 3. Extract KPIs for Time-Series Analysis
                if layer == "PHY":
                    sinr_m = SINR_PATTERN.search(line)
                    mcs_m = MCS_PATTERN.search(line)
                    tbs_m = TBS_PATTERN.search(line)
                    
                    if sinr_m or mcs_m or tbs_m:
                        time_series_kpis.append({
                            "tech": tech,
                            "distance_m": distance_m,
                            "protocol": protocol,
                            "direction": direction,
                            "layer": layer,
                            "sinr_db": float(sinr_m.group(1)) if sinr_m else None,
                            "modulation": mcs_m.group(1) if mcs_m else None,
                            "tbs": int(tbs_m.group(1)) if tbs_m else None,
                        })

        # Close split file handles
        for fh in split_files.values():
            fh.close()
            
        # Save indexed log lines to Parquet for Thesis 2
        df_parsed = pd.DataFrame(parsed_lines)
        df_parsed.to_parquet(folder_path / "parsed_logs.parquet", compression="snappy")

    # Return summary data for Master Index
    return {
        "metadata": {
            "tech": tech,
            "distance_m": distance_m,
            "protocol": protocol,
            "direction": direction,
            "path": str(folder_path)
        },
        "kpis": time_series_kpis
    }

def main():
    root = Path(".")
    # Locate all leaf directories containing a trace.log
    leaf_folders = [p.parent for p in root.glob("**/*/trace.log")]
    
    print(f"Found {len(leaf_folders)} experiment folders. Processing in parallel...")
    
    all_kpis = []
    manifest = []
    
    with ProcessPoolExecutor() as executor:
        results = executor.map(process_experiment_folder, leaf_folders)
        for res in results:
            manifest.append(res["metadata"])
            all_kpis.extend(res["kpis"])
            
    # Save master manifest and KPI dataset
    with open("dataset_manifest.json", "w") as f:
        json.dump(manifest, f, indent=4)
        
    df_kpis = pd.DataFrame(all_kpis)
    df_kpis.to_csv("master_kpis.csv", index=False)
    print("Dataset successfully indexed, split, and extracted!")

if __name__ == "__main__":
    main()
