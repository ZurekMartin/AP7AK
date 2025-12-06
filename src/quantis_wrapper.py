import platform
import logging
import ctypes
import os
from typing import List, Optional, Dict
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuantisDeviceType(Enum):
    PCI = 1
    USB = 2

class QuantisDevice:
    def __init__(self, device_type: QuantisDeviceType, device_number: int, name: str = None):
        self.device_type = device_type
        self.device_number = device_number
        self.name = name or f"{device_type.name} #{device_number}"

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"QuantisDevice({self.device_type.name}, {self.device_number})"

class QuantisError(Exception):
    def __init__(self, message: str, error_code: int = -99):
        super().__init__(message)
        self.error_code = error_code

class QuantisLibrary:
    QUANTIS_SUCCESS = 0
    QUANTIS_ERROR_NO_DRIVER = -1
    QUANTIS_ERROR_INVALID_DEVICE_NUMBER = -2
    QUANTIS_ERROR_INVALID_READ_SIZE = -3
    QUANTIS_ERROR_INVALID_PARAMETER = -4
    QUANTIS_ERROR_NO_MEMORY = -5
    QUANTIS_ERROR_NO_MODULE = -6
    QUANTIS_ERROR_IO = -7
    QUANTIS_ERROR_NO_DEVICE = -8
    QUANTIS_ERROR_OPERATION_NOT_SUPPORTED = -9
    QUANTIS_ERROR_OTHER = -99

    def __init__(self, library_path: Optional[str] = None):
        self.library = None
        self.library_path = library_path or self._find_library()
        self.library_info = None
        self.available_devices = []
        self.selected_device = None

        if not self.library_path:
            raise QuantisError("Quantis knihovna nebyla nalezena", self.QUANTIS_ERROR_NO_DRIVER)
        try:
            self._load_library()
        except Exception as e:
            raise QuantisError(f"Nepodařilo se načíst knihovnu: {e}", self.QUANTIS_ERROR_IO)

        self._refresh_devices()

    def _find_library(self) -> Optional[str]:
        system = platform.system().lower()

        possible_paths = []

        parent_lib_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
        if system == "windows":
            parent_lib = os.path.join(parent_lib_dir, "Quantis.dll")
            if os.path.exists(parent_lib):
                return parent_lib
        elif system == "linux":
            parent_lib = os.path.join(parent_lib_dir, "libQuantis.so")
            if os.path.exists(parent_lib):
                return parent_lib
        elif system == "darwin":
            parent_lib = os.path.join(parent_lib_dir, "libQuantis.dylib")
            if os.path.exists(parent_lib):
                return parent_lib

        local_full_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libQuantis.dylib")
        if os.path.exists(local_full_lib):
            return local_full_lib

        local_nohw_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libQuantis-NoHw.dylib")
        if os.path.exists(local_nohw_lib):
            return local_nohw_lib

        if system == "windows":
            possible_paths = [
                "Quantis.dll",
                "C:\\Program Files\\ID Quantique\\Quantis\\lib\\Quantis.dll",
                "C:\\Program Files (x86)\\ID Quantique\\Quantis\\lib\\Quantis.dll"
            ]
        elif system == "linux":
            possible_paths = [
                "libQuantis.so",
                "/usr/lib/libQuantis.so",
                "/usr/local/lib/libQuantis.so",
                "/opt/quantis/lib/libQuantis.so"
            ]
        elif system == "darwin":
            possible_paths = [
                "libQuantis.dylib",
                "/usr/lib/libQuantis.dylib",
                "/usr/local/lib/libQuantis.dylib",
                "/opt/quantis/lib/libQuantis.dylib"
            ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def _load_library(self):
        try:
            self.library = ctypes.CDLL(self.library_path)

            self.library.QuantisCount.argtypes = [ctypes.c_int]
            self.library.QuantisCount.restype = ctypes.c_int

            self.library.QuantisRead.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t]
            self.library.QuantisRead.restype = ctypes.c_int

            self.library.QuantisGetBoardVersion.argtypes = [ctypes.c_int, ctypes.c_uint]
            self.library.QuantisGetBoardVersion.restype = ctypes.c_int

            self.library.QuantisGetDriverVersion.argtypes = [ctypes.c_int]
            self.library.QuantisGetDriverVersion.restype = ctypes.c_float

            self.library.QuantisGetLibVersion.argtypes = []
            self.library.QuantisGetLibVersion.restype = ctypes.c_float

            self.library.QuantisGetManufacturer.argtypes = [ctypes.c_int, ctypes.c_uint]
            self.library.QuantisGetManufacturer.restype = ctypes.c_char_p

            self.library.QuantisGetModulesDataRate.argtypes = [ctypes.c_int, ctypes.c_uint]
            self.library.QuantisGetModulesDataRate.restype = ctypes.c_int

            self.library.QuantisGetSerialNumber.argtypes = [ctypes.c_int, ctypes.c_uint]
            self.library.QuantisGetSerialNumber.restype = ctypes.c_char_p

            self.library.QuantisOpen.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p)]
            self.library.QuantisOpen.restype = ctypes.c_int

            self.library.QuantisClose.argtypes = [ctypes.c_void_p]
            self.library.QuantisClose.restype = None

            self.library.QuantisReadHandled.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t]
            self.library.QuantisReadHandled.restype = ctypes.c_int

            self.library.QuantisReadShort.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_short)]
            self.library.QuantisReadShort.restype = ctypes.c_int

            self.library.QuantisReadScaledShort.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_short), ctypes.c_short, ctypes.c_short]
            self.library.QuantisReadScaledShort.restype = ctypes.c_int

            self.library.QuantisReadInt.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_int)]
            self.library.QuantisReadInt.restype = ctypes.c_int

            self.library.QuantisReadScaledInt.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int]
            self.library.QuantisReadScaledInt.restype = ctypes.c_int

            self.library.QuantisReadFloat_01.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_float)]
            self.library.QuantisReadFloat_01.restype = ctypes.c_int

            self.library.QuantisReadScaledFloat.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_float), ctypes.c_float, ctypes.c_float]
            self.library.QuantisReadScaledFloat.restype = ctypes.c_int

            self.library.QuantisReadDouble_01.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_double)]
            self.library.QuantisReadDouble_01.restype = ctypes.c_int

            self.library.QuantisReadScaledDouble.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ctypes.c_double), ctypes.c_double, ctypes.c_double]
            self.library.QuantisReadScaledDouble.restype = ctypes.c_int

            self.library.QuantisStrError.argtypes = [ctypes.c_int]
            self.library.QuantisStrError.restype = ctypes.c_char_p

            self.library.QuantisBoardReset.argtypes = [ctypes.c_int, ctypes.c_uint]
            self.library.QuantisBoardReset.restype = ctypes.c_int

            self.library.QuantisGetModulesCount.argtypes = [ctypes.c_int, ctypes.c_uint]
            self.library.QuantisGetModulesCount.restype = ctypes.c_int

            self.library.QuantisGetModulesMask.argtypes = [ctypes.c_int, ctypes.c_uint]
            self.library.QuantisGetModulesMask.restype = ctypes.c_int

            self.library.QuantisGetModulesStatus.argtypes = [ctypes.c_int, ctypes.c_uint]
            self.library.QuantisGetModulesStatus.restype = ctypes.c_int

            self.library.QuantisModulesEnable.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_int]
            self.library.QuantisModulesEnable.restype = ctypes.c_int

            self.library.QuantisModulesDisable.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_int]
            self.library.QuantisModulesDisable.restype = ctypes.c_int

            self.library.QuantisModulesReset.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_int]
            self.library.QuantisModulesReset.restype = ctypes.c_int

            logger.info(f"Úspěšně načtena knihovna: {self.library_path}")

        except Exception as e:
            raise QuantisError(f"Chyba při načítání knihovny: {e}", self.QUANTIS_ERROR_IO)


    def _refresh_devices(self):
        self.available_devices = []

        for device_type in QuantisDeviceType:
            count = self.count_devices(device_type)
            for i in range(count):
                device = QuantisDevice(device_type, i)
                self.available_devices.append(device)

    def count_devices(self, device_type: QuantisDeviceType) -> int:
        if not self.library:
            return 0

        result = self.library.QuantisCount(device_type.value)
        return result if result >= 0 else 0

    def get_library_info(self) -> str:
        return self.library_info or "Knihovna není načtena"

    def get_available_devices_list(self) -> List[QuantisDevice]:
        return self.available_devices.copy()

    def select_device(self, device: QuantisDevice):
        if device not in self.available_devices:
            raise QuantisError("Zařízení není v seznamu dostupných zařízení")
        self.selected_device = device

    def get_selected_device(self) -> Optional[QuantisDevice]:
        return self.selected_device

    def is_device_connected(self, device: Optional[QuantisDevice] = None) -> bool:
        if device is None:
            device = self.selected_device

        if device is None:
            return False

        return self.is_device_available(device.device_type, device.device_number)

    def read_random_bytes(self, size: int, device: Optional[QuantisDevice] = None) -> bytes:
        if device is None:
            device = self.selected_device

        if device is None:
            raise QuantisError("Žádné zařízení není vybráno", self.QUANTIS_ERROR_NO_DEVICE)

        if size <= 0:
            raise QuantisError("Velikost musí být kladná", self.QUANTIS_ERROR_INVALID_PARAMETER)

        if size > 16 * 1024 * 1024:
            raise QuantisError("Příliš velká velikost pro čtení", self.QUANTIS_ERROR_INVALID_READ_SIZE)

        if not self.is_device_available(device.device_type, device.device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        buffer = (ctypes.c_ubyte * size)()

        result = self.library.QuantisRead(device.device_type.value, device.device_number, buffer, size)

        if result < 0:
            raise QuantisError(f"Chyba při čtení: {result}", result)

        if result != size:
            raise QuantisError(f"Přečteno méně bajtů než požadováno: {result} z {size}", self.QUANTIS_ERROR_IO)

        return bytes(buffer)

    def read_int(self, device: Optional[QuantisDevice] = None) -> int:
        if device is None:
            device = self.selected_device

        if device is None:
            raise QuantisError("Žádné zařízení není vybráno", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.is_device_available(device.device_type, device.device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        value = ctypes.c_int()
        result = self.library.QuantisReadInt(device.device_type.value, device.device_number, ctypes.byref(value))

        if result != self.QUANTIS_SUCCESS:
            raise QuantisError(f"Chyba při čtení (QuantisReadInt): {self.get_error_message(result)}", result)

        return value.value

    def read_scaled_int(self, min_val: int, max_val: int, device: Optional[QuantisDevice] = None) -> int:
        if min_val >= max_val:
            raise QuantisError("Minimální hodnota musí být menší než maximální", self.QUANTIS_ERROR_INVALID_PARAMETER)

        if device is None:
            device = self.selected_device

        if device is None:
            raise QuantisError("Žádné zařízení není vybráno", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.is_device_available(device.device_type, device.device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        value = ctypes.c_int()
        result = self.library.QuantisReadScaledInt(device.device_type.value, device.device_number,
                                                   ctypes.byref(value), min_val, max_val)

        if result != self.QUANTIS_SUCCESS:
            raise QuantisError(f"Chyba při čtení (QuantisReadScaledInt): {self.get_error_message(result)}", result)

        return value.value

    def read_float_01(self, device: Optional[QuantisDevice] = None) -> float:
        if device is None:
            device = self.selected_device

        if device is None:
            raise QuantisError("Žádné zařízení není vybráno", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.is_device_available(device.device_type, device.device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        value = ctypes.c_float()
        result = self.library.QuantisReadFloat_01(device.device_type.value, device.device_number, ctypes.byref(value))

        if result != self.QUANTIS_SUCCESS:
            raise QuantisError(f"Chyba při čtení (QuantisReadFloat_01): {self.get_error_message(result)}", result)

        return value.value

    def read_scaled_float(self, min_val: float, max_val: float, device: Optional[QuantisDevice] = None) -> float:
        if min_val >= max_val:
            raise QuantisError("Minimální hodnota musí být menší než maximální", self.QUANTIS_ERROR_INVALID_PARAMETER)

        if device is None:
            device = self.selected_device

        if device is None:
            raise QuantisError("Žádné zařízení není vybráno", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.is_device_available(device.device_type, device.device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        value = ctypes.c_float()
        result = self.library.QuantisReadScaledFloat(device.device_type.value, device.device_number,
                                                     ctypes.byref(value), ctypes.c_float(min_val), ctypes.c_float(max_val))

        if result != self.QUANTIS_SUCCESS:
            raise QuantisError(f"Chyba při čtení (QuantisReadScaledFloat): {self.get_error_message(result)}", result)

        return value.value

    def read_double_01(self, device: Optional[QuantisDevice] = None) -> float:
        if device is None:
            device = self.selected_device

        if device is None:
            raise QuantisError("Žádné zařízení není vybráno", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.is_device_available(device.device_type, device.device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        value = ctypes.c_double()
        result = self.library.QuantisReadDouble_01(device.device_type.value, device.device_number, ctypes.byref(value))

        if result != self.QUANTIS_SUCCESS:
            raise QuantisError(f"Chyba při čtení (QuantisReadDouble_01): {self.get_error_message(result)}", result)

        return value.value

    def read_scaled_double(self, min_val: float, max_val: float, device: Optional[QuantisDevice] = None) -> float:
        if min_val >= max_val:
            raise QuantisError("Minimální hodnota musí být menší než maximální", self.QUANTIS_ERROR_INVALID_PARAMETER)

        if device is None:
            device = self.selected_device

        if device is None:
            raise QuantisError("Žádné zařízení není vybráno", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.is_device_available(device.device_type, device.device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        value = ctypes.c_double()
        result = self.library.QuantisReadScaledDouble(device.device_type.value, device.device_number,
                                                      ctypes.byref(value), ctypes.c_double(min_val), ctypes.c_double(max_val))

        if result != self.QUANTIS_SUCCESS:
            raise QuantisError(f"Chyba při čtení (QuantisReadScaledDouble): {self.get_error_message(result)}", result)

        return value.value

    def is_device_available(self, device_type: QuantisDeviceType, device_number: int) -> bool:
        count = self.count_devices(device_type)
        return 0 <= device_number < count

    def get_board_version(self, device_type: QuantisDeviceType, device_number: int) -> int:
        if not self.is_device_available(device_type, device_number):
            return self.QUANTIS_ERROR_NO_DEVICE

        if not self.library:
            return self.QUANTIS_ERROR_NO_DRIVER

        return self.library.QuantisGetBoardVersion(device_type.value, device_number)

    def get_driver_version(self, device_type: QuantisDeviceType) -> float:
        if not self.library:
            return -1.0

        return self.library.QuantisGetDriverVersion(device_type.value)

    def refresh_devices(self):
        self._refresh_devices()

    def get_device_info(self, device: Optional[QuantisDevice] = None) -> Dict[str, str]:
        if device is None:
            device = self.selected_device

        if device is None:
            return {"error": "Žádné zařízení není vybráno"}

        info = {
            "name": str(device),
            "type": device.device_type.name,
            "number": str(device.device_number),
            "connected": str(self.is_device_connected(device))
        }

        if self.is_device_connected(device):
            try:
                info["board_version"] = str(self.get_board_version(device.device_type, device.device_number))
                info["driver_version"] = str(self.get_driver_version(device.device_type))
                info["manufacturer"] = self.get_manufacturer(device.device_type, device.device_number)
                info["serial_number"] = self.get_serial_number(device.device_type, device.device_number)
                data_rate = self.get_modules_data_rate(device.device_type, device.device_number)
                info["data_rate"] = f"{data_rate} B/s" if data_rate >= 0 else "N/A"
                info["modules_count"] = str(self.get_modules_count(device.device_type, device.device_number))
                modules_mask = self.get_modules_mask(device.device_type, device.device_number)
                info["modules_mask"] = f"0x{modules_mask:08X}" if modules_mask >= 0 else "N/A"
                modules_status = self.get_modules_status(device.device_type, device.device_number)
                info["modules_status"] = f"0x{modules_status:08X}" if modules_status >= 0 else "N/A"
            except:
                info["board_version"] = "N/A"
                info["driver_version"] = "N/A"
                info["manufacturer"] = "N/A"
                info["serial_number"] = "N/A"
                info["data_rate"] = "N/A"
                info["modules_count"] = "N/A"
                info["modules_mask"] = "N/A"
                info["modules_status"] = "N/A"
        else:
            info["board_version"] = "N/A"
            info["driver_version"] = "N/A"

        return info

    def get_library_version(self) -> str:
        if not self.library:
            return "Knihovna není načtena"

        try:
            version = self.library.QuantisGetLibVersion()
            return f"{version:.1f}"
        except:
            return "N/A"

    def get_manufacturer(self, device_type: QuantisDeviceType, device_number: int) -> str:
        if not self.is_device_available(device_type, device_number):
            return "Not available"

        if not self.library:
            return "Not available"

        try:
            result = self.library.QuantisGetManufacturer(device_type.value, device_number)
            if result:
                return result.decode('utf-8')
            else:
                return "Not available"
        except:
            return "Not available"

    def get_modules_data_rate(self, device_type: QuantisDeviceType, device_number: int) -> int:
        if not self.is_device_available(device_type, device_number):
            return self.QUANTIS_ERROR_NO_DEVICE

        if not self.library:
            return self.QUANTIS_ERROR_NO_DRIVER

        return self.library.QuantisGetModulesDataRate(device_type.value, device_number)

    def get_serial_number(self, device_type: QuantisDeviceType, device_number: int) -> str:
        if not self.is_device_available(device_type, device_number):
            return "S/N not available"

        if not self.library:
            return "S/N not available"

        try:
            result = self.library.QuantisGetSerialNumber(device_type.value, device_number)
            if result:
                return result.decode('utf-8')
            else:
                return "S/N not available"
        except:
            return "S/N not available"

    def open_device(self, device_type: QuantisDeviceType, device_number: int) -> Optional[ctypes.c_void_p]:
        if not self.is_device_available(device_type, device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        device_handle = ctypes.c_void_p()
        result = self.library.QuantisOpen(device_type.value, device_number, ctypes.byref(device_handle))

        if result != self.QUANTIS_SUCCESS:
            raise QuantisError(f"Nepodařilo se otevřít zařízení: {self.get_error_message(result)}", result)

        return device_handle

    def close_device(self, device_handle: ctypes.c_void_p):
        if not self.library:
            return

        self.library.QuantisClose(device_handle)

    def read_handled(self, device_handle: ctypes.c_void_p, size: int) -> bytes:
        if size <= 0:
            raise QuantisError("Velikost musí být kladná", self.QUANTIS_ERROR_INVALID_PARAMETER)

        if size > 16 * 1024 * 1024:
            raise QuantisError("Příliš velká velikost pro čtení", self.QUANTIS_ERROR_INVALID_READ_SIZE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        buffer = (ctypes.c_ubyte * size)()
        result = self.library.QuantisReadHandled(device_handle, buffer, size)

        if result < 0:
            raise QuantisError(f"Chyba při čtení: {self.get_error_message(result)}", result)

        if result != size:
            raise QuantisError(f"Přečteno méně bajtů než požadováno: {result} z {size}", self.QUANTIS_ERROR_IO)

        return bytes(buffer)

    def read_short(self, device: Optional[QuantisDevice] = None) -> int:
        if device is None:
            device = self.selected_device

        if device is None:
            raise QuantisError("Žádné zařízení není vybráno", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.is_device_available(device.device_type, device.device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        value = ctypes.c_short()
        result = self.library.QuantisReadShort(device.device_type.value, device.device_number, ctypes.byref(value))

        if result != self.QUANTIS_SUCCESS:
            raise QuantisError(f"Chyba při čtení: {self.get_error_message(result)}", result)

        return value.value

    def read_scaled_short(self, min_val: int, max_val: int, device: Optional[QuantisDevice] = None) -> int:
        if min_val >= max_val:
            raise QuantisError("Minimální hodnota musí být menší než maximální")

        if device is None:
            device = self.selected_device

        if device is None:
            raise QuantisError("Žádné zařízení není vybráno", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.is_device_available(device.device_type, device.device_number):
            raise QuantisError("Zařízení není dostupné", self.QUANTIS_ERROR_NO_DEVICE)

        if not self.library:
            raise QuantisError("Knihovna není načtena", self.QUANTIS_ERROR_NO_DRIVER)

        value = ctypes.c_short()
        result = self.library.QuantisReadScaledShort(device.device_type.value, device.device_number,
                                                    ctypes.byref(value), min_val, max_val)

        if result != self.QUANTIS_SUCCESS:
            raise QuantisError(f"Chyba při čtení: {self.get_error_message(result)}", result)

        return value.value

    def get_error_message(self, error_code: int) -> str:
        if not self.library:
            return f"Neznámý kód chyby: {error_code}"

        try:
            result = self.library.QuantisStrError(error_code)
            if result:
                return result.decode('utf-8')
            else:
                return f"Neznámý kód chyby: {error_code}"
        except:
            return f"Neznámý kód chyby: {error_code}"

    def board_reset(self, device_type: QuantisDeviceType, device_number: int) -> bool:
        if not self.is_device_available(device_type, device_number):
            return False

        if not self.library:
            return False

        result = self.library.QuantisBoardReset(device_type.value, device_number)
        return result == self.QUANTIS_SUCCESS

    def get_modules_count(self, device_type: QuantisDeviceType, device_number: int) -> int:
        if not self.is_device_available(device_type, device_number):
            return self.QUANTIS_ERROR_NO_DEVICE

        if not self.library:
            return self.QUANTIS_ERROR_NO_DRIVER

        return self.library.QuantisGetModulesCount(device_type.value, device_number)

    def get_modules_mask(self, device_type: QuantisDeviceType, device_number: int) -> int:
        if not self.is_device_available(device_type, device_number):
            return self.QUANTIS_ERROR_NO_DEVICE

        if not self.library:
            return self.QUANTIS_ERROR_NO_DRIVER

        return self.library.QuantisGetModulesMask(device_type.value, device_number)

    def get_modules_status(self, device_type: QuantisDeviceType, device_number: int) -> int:
        if not self.is_device_available(device_type, device_number):
            return self.QUANTIS_ERROR_NO_DEVICE

        if not self.library:
            return self.QUANTIS_ERROR_NO_DRIVER

        return self.library.QuantisGetModulesStatus(device_type.value, device_number)

    def modules_enable(self, device_type: QuantisDeviceType, device_number: int, modules_mask: int) -> bool:
        if not self.is_device_available(device_type, device_number):
            return False

        if not self.library:
            return False

        result = self.library.QuantisModulesEnable(device_type.value, device_number, modules_mask)
        return result == self.QUANTIS_SUCCESS

    def modules_disable(self, device_type: QuantisDeviceType, device_number: int, modules_mask: int) -> bool:
        if not self.is_device_available(device_type, device_number):
            return False

        if not self.library:
            return False

        result = self.library.QuantisModulesDisable(device_type.value, device_number, modules_mask)
        return result == self.QUANTIS_SUCCESS

    def modules_reset(self, device_type: QuantisDeviceType, device_number: int, modules_mask: int) -> bool:
        if not self.is_device_available(device_type, device_number):
            return False

        if not self.library:
            return False

        result = self.library.QuantisModulesReset(device_type.value, device_number, modules_mask)
        return result == self.QUANTIS_SUCCESS
