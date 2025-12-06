import random
import math
from utils import build_string_alphabet, string_from_bytes
from constants import STRING_SPECIAL_CHARS

class DataGenerator:
    def __init__(self, quantis=None):
        self.quantis = quantis
        self.rng = random.Random()
        self.seed = None

    def set_seed(self, seed: str) -> None:
        self.seed = seed
        self.rng.seed(seed)

    def _build_alphabet(self, lowercase, uppercase, digits, special):
        return build_string_alphabet(lowercase, uppercase, digits, special, STRING_SPECIAL_CHARS)

    def get_hardware_reader(self, data_type: str, use_scaling: bool,
                            min_int: int = 0, max_int: int = 1,
                            min_float: float = 0.0, max_float: float = 1.0,
                            unsigned: bool = False, length: int = 8,
                            lowercase: bool = True, uppercase: bool = True,
                            digits: bool = True, special: bool = False):
        if use_scaling:
            if data_type == "int":
                if unsigned:
                    def read_scaled_unsigned():
                        min_val, max_val = max(0, int(min_int)), int(max_int)
                        if min_val >= max_val:
                            raise ValueError("Minimální hodnota musí být menší než maximální")
                        rnd = int.from_bytes(self.quantis.read_random_bytes(4), 'big')
                        return (rnd % (max_val - min_val + 1)) + min_val
                    return read_scaled_unsigned
                return lambda: self.quantis.read_scaled_int(min_int, max_int)
            if data_type in ("float", "double"):
                reader = self.quantis.read_scaled_double if data_type == "double" else self.quantis.read_scaled_float
                return lambda: reader(min_float, max_float)

        readers = {
            "int": lambda: int.from_bytes(self.quantis.read_random_bytes(4), 'big') if unsigned else self.quantis.read_int(),
            "float": self.quantis.read_float_01,
            "double": self.quantis.read_double_01,
            "bytes": lambda: self.quantis.read_random_bytes(1)[0],
        }
        if data_type in readers:
            return readers[data_type]

        if data_type == "string":
            alphabet = self._build_alphabet(lowercase, uppercase, digits, special)
            return lambda: string_from_bytes(self.quantis.read_random_bytes(max(0, int(length))), alphabet) if length > 0 else ''

        if data_type == "bits":
            def read_bits():
                bits = max(0, int(length))
                if bits == 0:
                    return ''
                rb = self.quantis.read_random_bytes(math.ceil(bits / 8))
                return ''.join(f'{b:08b}' for b in rb)[:bits]
            return read_bits

        return self.quantis.read_int
    
    def get_software_reader(self, data_type: str, use_scaling: bool,
                            min_int: int = 0, max_int: int = 1,
                            min_float: float = 0.0, max_float: float = 1.0,
                            unsigned: bool = False, length: int = 8,
                            lowercase: bool = True, uppercase: bool = True,
                            digits: bool = True, special: bool = False):
        if use_scaling:
            if data_type == "int":
                return lambda: self.rng.randint(min_int, max_int)
            if data_type in ("float", "double"):
                return lambda: self.rng.uniform(min_float, max_float)

        if data_type == "int":
            return lambda: self.rng.randint(0, 2**32 - 1) if unsigned else self.rng.randint(-2**31, 2**31 - 1)
        if data_type in ("float", "double"):
            return self.rng.random
        if data_type == "bytes":
            return lambda: self.rng.randint(0, 255)
        if data_type == "string":
            alphabet = self._build_alphabet(lowercase, uppercase, digits, special)
            return lambda: ''.join(self.rng.choice(alphabet) for _ in range(max(0, int(length)))) if length > 0 else ''
        if data_type == "bits":
            return lambda: ''.join(str(self.rng.randint(0, 1)) for _ in range(max(0, int(length)))) if length > 0 else ''

        return lambda: self.rng.randint(-2**31, 2**31 - 1)
    
    def get_reader(self, mode: str, data_type: str, use_scaling: bool,
                   min_int: int = 0, max_int: int = 1,
                   min_float: float = 0.0, max_float: float = 1.0,
                   unsigned: bool = False, length: int = 8,
                   lowercase: bool = True, uppercase: bool = True,
                   digits: bool = True, special: bool = False):
        method = self.get_software_reader if mode == "software" else self.get_hardware_reader
        return method(data_type, use_scaling, min_int, max_int, min_float, max_float,
                      unsigned, length, lowercase, uppercase, digits, special)

    def generate_batch(self, mode: str, count: int, data_type: str, use_scaling: bool,
                       min_int: int = 0, max_int: int = 1,
                       min_float: float = 0.0, max_float: float = 1.0,
                       unsigned: bool = False, length: int = 8,
                       lowercase: bool = True, uppercase: bool = True,
                       digits: bool = True, special: bool = False) -> list:
        reader = self.get_reader(mode, data_type, use_scaling, min_int, max_int, min_float, max_float,
                                 unsigned, length, lowercase, uppercase, digits, special)
        return [reader() for _ in range(max(0, count))]
