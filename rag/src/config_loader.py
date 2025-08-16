import yaml
import os

def load_config(config_path: str) -> dict:
    """
    Loads and parses the YAML configuration file.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)
