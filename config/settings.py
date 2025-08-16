"""
config/settings.py
Simple settings wrapper reading/writing settings in DB (via DB.get_setting/set_setting).
"""
from typing import Any


class AppSettings:
    def __init__(self, db):
        self._db = db

    def get(self, key: str, default: Any = None):
        return self._db.get_setting(key, default)

    def set(self, key: str, value: Any):
        self._db.set_setting(key, str(value))

    @property
    def store_name(self):
        return self.get("store_name", "JADOON SHOPPING MART")

    @store_name.setter
    def store_name(self, val):
        self.set("store_name", val)

    @property
    def default_tax_percent(self) -> float:
        return float(self.get("default_tax_percent", "0") or 0)

    @default_tax_percent.setter
    def default_tax_percent(self, v: float):
        self.set("default_tax_percent", v)

    @property
    def receipt_footer(self):
        return self.get("receipt_footer", "Thank you for shopping with Jadoon Shopping Mart!")

    @receipt_footer.setter
    def receipt_footer(self, v: str):
        self.set("receipt_footer", v)

    @property
    def low_stock_threshold(self) -> int:
        return int(self.get("low_stock_threshold", "5") or 5)

    @low_stock_threshold.setter
    def low_stock_threshold(self, v: int):
        self.set("low_stock_threshold", v)
