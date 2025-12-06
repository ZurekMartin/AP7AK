import struct
import math
import zlib
from constants import BITS_PER_TYPE

def format_bits(bits_count: int) -> str:
    if bits_count < 1024:
        return f"{bits_count} b"
    bytes_count = bits_count / 8
    for unit, div in [("B", 1), ("KB", 1024), ("MB", 1024**2), ("GB", 1024**3), ("TB", 1024**4)]:
        val = bytes_count / div
        if val < 1024 or unit == "TB":
            s = f"{val:.2f}".rstrip('0').rstrip('.')
            return f"{s} {unit}"
    return f"{bytes_count} B"

def get_bits_per_value(data_type: str, length_var_value: int = 8) -> int:
    if data_type in BITS_PER_TYPE:
        return BITS_PER_TYPE[data_type]
    if data_type == "string":
        return max(0, length_var_value) * 8
    if data_type == "bits":
        return max(0, length_var_value)
    return 32

def int_to_bytes(value: int) -> tuple:
    if -2**31 <= value <= 2**31 - 1:
        return value.to_bytes(4, 'big', signed=True), 32
    if value >= 0:
        width = max(1, (int(value).bit_length() + 7) // 8)
        return value.to_bytes(width, 'big', signed=False), width * 8
    width = max(1, (value.bit_length() + 8) // 8)
    return value.to_bytes(width, 'big', signed=True), width * 8

def value_to_bytes(value, data_type: str) -> tuple:
    converters = {
        'bytes': lambda v: (bytes([int(v) & 0xFF]), 8),
        'int': lambda v: int_to_bytes(int(v)),
        'float': lambda v: (struct.pack('>f', float(v)), 32),
        'double': lambda v: (struct.pack('>d', float(v)), 64),
        'string': lambda v: (v.encode('utf-8'), len(v.encode('utf-8')) * 8),
    }
    if data_type == 'bits':
        raise ValueError("Bits type is handled separately")
    conv = converters.get(data_type)
    if conv:
        return conv(value)
    data = str(value).encode('utf-8')
    return data, len(data) * 8

def format_value(value, data_type: str, is_hex: bool = False) -> str:
    if data_type == "bytes":
        return f"0x{value:02X}" if is_hex else f"{value:02X}"
    return str(value)

def gather_binary_data(generated_values: list, data_type: str) -> tuple:
    if data_type == 'bits':
        raw_bits = ''.join(generated_values)
        total_bits = len(raw_bits)
        if total_bits == 0:
            return bytearray(), 0, raw_bits
        pad_len = (8 - (total_bits % 8)) % 8
        padded = raw_bits + ('0' * pad_len)
        return bytearray(int(padded[i:i+8], 2) for i in range(0, len(padded), 8)), total_bits, raw_bits

    byte_data, total_bits = bytearray(), 0
    for value in generated_values:
        chunk, bits = value_to_bytes(value, data_type)
        byte_data.extend(chunk)
        total_bits += bits
    return byte_data, total_bits, None

def binary_entropy(zeros: int, ones: int) -> float:
    total = zeros + ones
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in (zeros, ones):
        if count:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy

def calculate_entropy(generated_values: list, data_type: str) -> float:
    if not generated_values:
        return 0.0
    byte_data, total_bits, raw_bits = gather_binary_data(generated_values, data_type)
    if total_bits == 0:
        return 0.0
    ones = raw_bits.count('1') if raw_bits else sum(b.bit_count() for b in byte_data)
    return binary_entropy(total_bits - ones, ones)

def calculate_compression_ratio(generated_values: list, data_type: str) -> float:
    if not generated_values:
        return 0.0
    byte_data, total_bits, _ = gather_binary_data(generated_values, data_type)
    if not byte_data:
        return 0.0
    compressed = zlib.compress(bytes(byte_data))
    return len(byte_data) / len(compressed) if compressed else 0.0

def build_string_alphabet(lowercase: bool = True, uppercase: bool = True,
                          digits: bool = True, special: bool = False,
                          special_chars: str = "!@#$%^&*()-_=+[]{};:,.<>/?\\|`~") -> str:
    parts = []
    if lowercase:
        parts.append('abcdefghijklmnopqrstuvwxyz')
    if uppercase:
        parts.append('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    if digits:
        parts.append('0123456789')
    if special:
        parts.append(special_chars)
    return ''.join(parts) or 'abcdefghijklmnopqrstuvwxyz0123456789'

def string_from_bytes(data: bytes, alphabet: str) -> str:
    if not alphabet:
        alphabet = build_string_alphabet()
    return ''.join(alphabet[b % len(alphabet)] for b in data)
