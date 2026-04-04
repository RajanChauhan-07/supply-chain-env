# backend/app/data/__init__.py

import json
import os

# Path to data directory
DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def load_suppliers() -> dict:
    """Load all supplier data from JSON"""
    with open(os.path.join(DATA_DIR, "suppliers.json"), "r") as f:
        return json.load(f)


def load_orders() -> dict:
    """Load all order data from JSON"""
    with open(os.path.join(DATA_DIR, "orders.json"), "r") as f:
        return json.load(f)


def load_disruptions() -> dict:
    """Load all disruption scenarios from JSON"""
    with open(os.path.join(DATA_DIR, "disruptions.json"), "r") as f:
        return json.load(f)