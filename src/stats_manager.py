import json
import os
from constants import TYPE_NAMES

class StatsManager:
    def __init__(self, stats_file: str = "stats/stats.json"):
        self.stats_file = stats_file
        self.stats = self.load_stats()

    def _create_empty_stats(self) -> dict:
        return {
            "total_numbers": 0,
            "total_bits": 0,
            "types": {t: {"numbers": 0, "bits": 0} for t in TYPE_NAMES},
            "hw_stats": {t: {"entropy_sum": 0.0, "compression_sum": 0.0, "count": 0} for t in TYPE_NAMES},
            "sw_stats": {t: {"entropy_sum": 0.0, "compression_sum": 0.0, "count": 0} for t in TYPE_NAMES}
        }

    def load_stats(self) -> dict:
        try:
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "hw_stats" not in data:
                    data["hw_stats"] = {t: {"entropy_sum": 0.0, "compression_sum": 0.0, "count": 0} for t in TYPE_NAMES}
                if "sw_stats" not in data:
                    data["sw_stats"] = {t: {"entropy_sum": 0.0, "compression_sum": 0.0, "count": 0} for t in TYPE_NAMES}
                return data
        except Exception:
            return self._create_empty_stats()

    def save_stats(self) -> None:
        os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=4)

    def _migrate_bytes_to_bits(self, data: dict, key: str = "total") -> int:
        bits_key = "total_bits" if key == "total" else "bits"
        bytes_key = "total_bytes" if key == "total" else "bytes"
        if bits_key not in data and bytes_key in data:
            data[bits_key] = data.pop(bytes_key) * 8
        return data.get(bits_key, 0)

    def update_stats(self, data_type: str, numbers: int, bits_count: int, mode: str = None, entropy: float = None, compression: float = None) -> None:
        self.stats["total_numbers"] += numbers
        self._migrate_bytes_to_bits(self.stats, "total")
        self.stats["total_bits"] = self.stats.get("total_bits", 0) + bits_count

        type_stats = self.stats["types"][data_type]
        type_stats["numbers"] += numbers
        self._migrate_bytes_to_bits(type_stats, "type")
        type_stats["bits"] = type_stats.get("bits", 0) + bits_count

        if mode and entropy is not None and compression is not None:
            stats_key = "hw_stats" if mode == "hardware" else "sw_stats"
            if stats_key not in self.stats:
                self.stats[stats_key] = {t: {"entropy_sum": 0.0, "compression_sum": 0.0, "count": 0} for t in TYPE_NAMES}
            if data_type not in self.stats[stats_key]:
                self.stats[stats_key][data_type] = {"entropy_sum": 0.0, "compression_sum": 0.0, "count": 0}
            mode_stats = self.stats[stats_key][data_type]
            mode_stats["entropy_sum"] = mode_stats.get("entropy_sum", 0.0) + entropy
            mode_stats["compression_sum"] = mode_stats.get("compression_sum", 0.0) + compression
            mode_stats["count"] = mode_stats.get("count", 0) + 1

        self.save_stats()

    def reset_stats(self) -> None:
        self.stats = self._create_empty_stats()
        self.save_stats()

    def get_total_numbers(self) -> int:
        return self.stats.get("total_numbers", 0)

    def get_total_bits(self) -> int:
        return self._migrate_bytes_to_bits(self.stats, "total") or 0

    def get_type_stats(self, type_name: str) -> dict:
        ts = self.stats["types"].get(type_name, {"numbers": 0, "bits": 0})
        return {"numbers": ts.get("numbers", 0), "bits": self._migrate_bytes_to_bits(ts, "type") or 0}

    def get_all_type_stats(self) -> dict:
        return {t: self.get_type_stats(t) for t in TYPE_NAMES}

    def get_mode_stats(self, mode: str) -> dict:
        stats_key = "hw_stats" if mode == "hardware" else "sw_stats"
        if stats_key not in self.stats:
            return {t: {"avg_entropy": 0.0, "avg_compression": 0.0} for t in TYPE_NAMES}
        result = {}
        for t in TYPE_NAMES:
            mode_data = self.stats[stats_key].get(t, {"entropy_sum": 0.0, "compression_sum": 0.0, "count": 0})
            count = mode_data.get("count", 0)
            if count > 0:
                result[t] = {
                    "avg_entropy": mode_data.get("entropy_sum", 0.0) / count,
                    "avg_compression": mode_data.get("compression_sum", 0.0) / count
                }
            else:
                result[t] = {"avg_entropy": 0.0, "avg_compression": 0.0}
        return result
