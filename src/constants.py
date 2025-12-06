from enum import Enum

class DataFormat(Enum):
    ONE_PER_LINE = "Jeden záznam na řádek"
    CSV = "CSV formát"

MAX_DISPLAY_VALUES = 10000
TYPE_NAMES = ["int", "float", "double", "bytes", "string", "bits"]
NON_SCALABLE_TYPES = ("bytes", "string", "bits")
VARIABLE_LENGTH_TYPES = ("string", "bits")

BITS_PER_TYPE = {
    "bytes": 8,
    "int": 32,
    "float": 32,
    "double": 64
}

STRING_SPECIAL_CHARS = "!@#$%^&*()-_=+[]{};:,.<>/?\\|`~"

DEFAULT_STATS = {
    "total_numbers": 0,
    "total_bits": 0,
    "types": {t: {"numbers": 0, "bits": 0} for t in TYPE_NAMES}
}

UI_BUTTON_HEIGHT = 35
UI_ENTRY_HEIGHT = 35
UI_ICON_SIZE = 20
UI_FONT_NORMAL = 13
UI_FONT_TITLE = 16
UI_PADDING_SECTION = 15
UI_PADDING_SMALL = 8
UI_PADDING_TINY = 5
