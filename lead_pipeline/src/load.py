import os
from datetime import datetime
from pathlib import Path
import pandas as pd
from loguru import logger

def save_leads_to_csv(df: pd.DataFrame, filepath: str, add_timestamp_backup: bool = True) -> str:
    """
    Saves the leads dataframe to the specified CSV filepath.
    Optionally creates a backup with a timestamp to prevent accidental data loss.
    """
    if df is None:
        logger.warning("No dataframe provided to save.")
        return ""

    out_path = Path(filepath)
    # Ensure output directories exist
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save main master file
    try:
        df.to_csv(out_path, index=False, encoding="utf-8")
        logger.success(f"Successfully saved data to master file: {out_path.resolve()}")
    except Exception as e:
        logger.error(f"Failed to save master file to {out_path}: {e}")
        raise e

    # Create a timestamped backup file if requested
    if add_timestamp_backup and not df.empty:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{out_path.stem}_{timestamp}{out_path.suffix}"
        backup_path = out_path.parent / backup_filename
        
        try:
            df.to_csv(backup_path, index=False, encoding="utf-8")
            logger.info(f"Saved timestamped backup to: {backup_path.resolve()}")
        except Exception as e:
            logger.warning(f"Could not create timestamped backup file: {e}")

    return str(out_path.resolve())
