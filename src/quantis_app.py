import customtkinter as ctk
import threading
import hashlib
import time
import os
import sys
from utils import format_bits, get_bits_per_value, format_value, calculate_entropy, calculate_compression_ratio
from constants import (
    DataFormat, MAX_DISPLAY_VALUES, TYPE_NAMES, NON_SCALABLE_TYPES, VARIABLE_LENGTH_TYPES,
    UI_BUTTON_HEIGHT, UI_ENTRY_HEIGHT, UI_ICON_SIZE, UI_FONT_NORMAL, UI_FONT_TITLE,
    UI_PADDING_SECTION, UI_PADDING_SMALL
)
from dialogs import InfoDialog, StatsDialog
from tkinter import messagebox, filedialog
from data_generator import DataGenerator
from stats_manager import StatsManager
from PIL import Image

try:
    from quantis_wrapper import QuantisLibrary, QuantisError
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from quantis_wrapper import QuantisLibrary, QuantisError

class QuantisApp:
    def __init__(self):
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("green")

        self.root = ctk.CTk()
        self.root.title("Quantis TRNG")
        self.root.resizable(True, True)

        self._init_state_variables()
        self._init_ui_variables()
        self._init_managers()
        self.load_icons()
        self.init_quantis()
        self.setup_ui()
        self.center_window()
        self.start_device_monitoring()

    def _init_state_variables(self):
        self.current_screen = "main"
        self.quantis = None
        self.generated_values = []
        self.is_generating = False
        self.continuous_thread = None
        self.monitor_thread = None
        self.stop_monitoring = False
        self.continuous_data_type = None
        self.continuous_use_scaling = None
        self.mode = "hardware"
        self.is_collecting = False
        self.collected_data = []
        self.seed = None
        self.captured_bits = 0
        self.software_seed_ready = False
        self.generation_start_time = None
        self.generation_elapsed = 0.0
        self.timer_running = False
        self._timer_after_id = None
        self._generate_thread = None
        self.mode_label = None
        self.collect_button = None
        self.seed_label = None
        self.software_frame = None
        self._generation_in_progress = False

    def _init_ui_variables(self):
        self.device_var = ctk.StringVar()
        self.data_format_var = ctk.StringVar(value=DataFormat.ONE_PER_LINE.value)
        self.count_var = ctk.IntVar(value=100)
        self.use_scaling_var = ctk.BooleanVar(value=False)
        self.min_int_var = ctk.IntVar(value=0)
        self.max_int_var = ctk.IntVar(value=1)
        self.min_float_var = ctk.DoubleVar(value=0.0)
        self.max_float_var = ctk.DoubleVar(value=1.0)
        self.data_type_var = ctk.StringVar(value="int")
        self.length_var = ctk.IntVar(value=8)
        self.string_lowercase_var = ctk.BooleanVar(value=True)
        self.string_uppercase_var = ctk.BooleanVar(value=True)
        self.string_digits_var = ctk.BooleanVar(value=True)
        self.string_special_var = ctk.BooleanVar(value=False)
        self.unsigned_var = ctk.BooleanVar(value=False)

    def _init_managers(self):
        self.stats_manager = StatsManager("stats/stats.json")
        self.data_generator = None

    def _font(self, size=UI_FONT_NORMAL, bold=False):
        return ctk.CTkFont(size=size, weight="bold" if bold else "normal")

    def _create_button(self, parent, text="", command=None, icon=None, width=None, height=UI_BUTTON_HEIGHT):
        kwargs = {"text": text, "command": command, "height": height, "font": self._font()}
        if icon:
            kwargs["image"] = icon
        if width:
            kwargs["width"] = width
        return ctk.CTkButton(parent, **kwargs)

    def _create_label(self, parent, text, bold=False, size=UI_FONT_NORMAL, **kwargs):
        return ctk.CTkLabel(parent, text=text, font=self._font(size, bold), **kwargs)

    def load_icons(self):
        self.info_icon = self._create_icon("info.png")
        self.trash_icon = self._create_icon("trash.png")
        self.copy_icon = self._create_icon("copy.png")
        self.icons_loaded = any((self.info_icon, self.trash_icon, self.copy_icon))

    def _create_icon(self, filename):
        try:
            path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "icons", filename))
            with Image.open(path) as img:
                resized = img.resize((UI_ICON_SIZE, UI_ICON_SIZE), Image.LANCZOS)
                return ctk.CTkImage(light_image=resized, dark_image=resized, size=(UI_ICON_SIZE, UI_ICON_SIZE))
        except Exception as exc:
            print(f"Chyba při načítání ikony {filename}: {exc}")
            return None

    def _enable_device_modules(self, device):
        if not device or not self.quantis:
            return
        try:
            modules_mask = self.quantis.get_modules_mask(device.device_type, device.device_number)
            if modules_mask > 0:
                self.quantis.modules_enable(device.device_type, device.device_number, modules_mask)
        except Exception:
            pass

    def init_quantis(self):
        try:
            self.quantis = QuantisLibrary()
            self.data_generator = DataGenerator(self.quantis)
        except QuantisError as e:
            messagebox.showerror("Chyba", f"Nepodařilo se inicializovat Quantis knihovnu:\n{e}")
            self.root.quit()
            return

        devices = self.quantis.get_available_devices_list()
        if devices:
            self.quantis.select_device(devices[0])
            self._enable_device_modules(devices[0])
            self.device_var.set(str(devices[0]))

    def setup_ui(self):
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        self.setup_main_screen()
        self.show_main_screen()

    def setup_main_screen(self):
        self.main_screen = ctk.CTkFrame(self.content_frame, fg_color="transparent")

        self.main_screen.grid_columnconfigure(0, weight=1, minsize=320)
        self.main_screen.grid_columnconfigure(1, weight=7, minsize=320)

        self._setup_left_panel()
        self._setup_right_panel()

        self.update_scaling_controls()

    def _setup_left_panel(self):
        left_panel = ctk.CTkFrame(self.main_screen, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        self.left_panel = left_panel

        self._setup_device_section(left_panel)
        self._setup_config_section(left_panel)
        self._setup_size_label(left_panel)
        self._setup_actions_section(left_panel)

    def _setup_device_section(self, parent):
        device_section = ctk.CTkFrame(parent)
        device_section.pack(fill=ctk.X, pady=(0, 10))
        self.device_section = device_section

        self._create_label(device_section, "Zařízení", bold=True, size=UI_FONT_TITLE).pack(pady=(UI_PADDING_SECTION, UI_PADDING_SMALL))

        self.device_combo = ctk.CTkComboBox(
            device_section, variable=self.device_var, state="readonly",
            command=lambda v: self.on_device_changed(), height=UI_BUTTON_HEIGHT
        )
        self.device_combo.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

        btn_frame = ctk.CTkFrame(device_section, fg_color="transparent")
        btn_frame.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

        self._create_button(btn_frame, "Aktualizovat", self.refresh_devices).pack(side=ctk.LEFT, fill=ctk.X, expand=True)
        self.info_button = self._create_button(btn_frame, "", self.show_info_window, self.info_icon, width=UI_BUTTON_HEIGHT)
        self.info_button.pack(side=ctk.RIGHT, padx=(5, 0))

        self.status_frame = ctk.CTkFrame(device_section, fg_color="transparent")
        self.status_frame.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

        self.status_label = self._create_label(self.status_frame, "", text_color="white")
        self.status_label.pack(side=ctk.LEFT)
        self.device_count_label = self._create_label(self.status_frame, "", text_color="white")
        self.device_count_label.pack(side=ctk.LEFT)
        self.captured_bits_label = self._create_label(self.status_frame, "", text_color="white")

        self.software_frame = ctk.CTkFrame(device_section, fg_color="transparent")

    def _setup_config_section(self, parent):
        config_section = ctk.CTkFrame(parent)
        config_section.pack(fill=ctk.X, pady=(0, UI_PADDING_SMALL))

        self._create_label(config_section, "Konfigurace", bold=True, size=UI_FONT_TITLE).pack(pady=(0, UI_PADDING_SMALL))

        self.format_combo = ctk.CTkComboBox(
            config_section, variable=self.data_format_var,
            values=[f.value for f in DataFormat], state="readonly", height=UI_BUTTON_HEIGHT
        )
        self.format_combo.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

        self._create_label(config_section, "Datový typ:").pack(padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL), anchor=ctk.W)
        self.type_combo = ctk.CTkComboBox(
            config_section, variable=self.data_type_var, values=TYPE_NAMES,
            state="readonly", command=lambda v: self.on_data_type_changed(), height=UI_BUTTON_HEIGHT
        )
        self.type_combo.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

        self._setup_scaling_section(config_section)
        self._setup_count_section(config_section)

    def _setup_scaling_section(self, parent):
        self.scaling_section = ctk.CTkFrame(parent, fg_color="transparent")
        self.scaling_section.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

        self.scaling_controls_frame = ctk.CTkFrame(self.scaling_section, fg_color="transparent")
        self.scaling_controls_frame.pack(fill=ctk.X, pady=(UI_PADDING_SMALL, 0))

        self.scaling_top_row = ctk.CTkFrame(self.scaling_section, fg_color="transparent")
        self.scaling_top_row.pack(fill=ctk.X)
        self.scaling_top_row.grid_columnconfigure(0, weight=1)
        self.scaling_top_row.grid_columnconfigure(1, weight=1)

        self.scaling_checkbox = ctk.CTkCheckBox(
            self.scaling_top_row, text="Použít škálování",
            variable=self.use_scaling_var, command=self.on_scaling_changed, font=self._font()
        )
        self.scaling_checkbox.grid(row=0, column=0, sticky="w", padx=(0, 5))

        self.unsigned_checkbox = ctk.CTkCheckBox(
            self.scaling_top_row, text="Unsigned", variable=self.unsigned_var, font=self._font()
        )
        self.unsigned_checkbox.grid(row=0, column=1, sticky="e", padx=(UI_PADDING_SMALL, 0))

        self.string_options_frame = ctk.CTkFrame(self.scaling_section, fg_color="transparent")
        self.string_options_frame.grid_columnconfigure(0, weight=1)
        self.string_options_frame.grid_columnconfigure(1, weight=1)
        self.string_lowercase_cb = ctk.CTkCheckBox(self.string_options_frame, text="Malá písmena", variable=self.string_lowercase_var)
        self.string_uppercase_cb = ctk.CTkCheckBox(self.string_options_frame, text="Velká písmena", variable=self.string_uppercase_var)
        self.string_digits_cb = ctk.CTkCheckBox(self.string_options_frame, text="Číslice", variable=self.string_digits_var)
        self.string_special_cb = ctk.CTkCheckBox(self.string_options_frame, text="Speciální znaky", variable=self.string_special_var)

    def _setup_count_section(self, parent):
        self.count_label = self._create_label(parent, "Počet záznamů:")
        self.count_label.pack(padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL), anchor=ctk.W)

        self.count_entry = ctk.CTkEntry(parent, textvariable=self.count_var, height=UI_ENTRY_HEIGHT)
        self.count_entry.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))
        self.count_var.trace_add("write", lambda *a: self.on_count_changed())

        self.length_label = self._create_label(parent, "Délka záznamu:")
        self.length_entry = ctk.CTkEntry(parent, textvariable=self.length_var, height=UI_ENTRY_HEIGHT)
        try:
            self.length_var.trace_add("write", lambda *a: self.update_size_estimate())
        except Exception:
            pass

    def _setup_size_label(self, parent):
        self.size_label = self._create_label(parent, "Odhadovaná velikost: 0 b")
        self.size_label.pack(padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL), anchor=ctk.W)

    def _setup_actions_section(self, parent):
        actions_section = ctk.CTkFrame(parent)
        actions_section.pack(fill=ctk.X, pady=(0, 10))

        self._setup_generate_buttons(actions_section)
        self._setup_save_buttons(actions_section)

    def _setup_generate_buttons(self, parent):
        gen_frame = ctk.CTkFrame(parent, fg_color="transparent")
        gen_frame.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(10, UI_PADDING_SMALL))

        self.generate_button = self._create_button(gen_frame, "Generovat", self.generate_data)
        self.generate_button.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

        self.stats_button = self._create_button(gen_frame, "", self.show_stats_window, self.info_icon, width=UI_BUTTON_HEIGHT)
        self.stats_button.pack(side=ctk.RIGHT, padx=(5, 0))

        self.continuous_button = self._create_button(parent, "Spustit kontinuální generování", self.toggle_continuous)
        self.continuous_button.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

    def _setup_save_buttons(self, parent):
        save_frame = ctk.CTkFrame(parent, fg_color="transparent")
        save_frame.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

        self.save_button = self._create_button(save_frame, "Uložit do souboru", self.save_to_file)
        self.save_button.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

        self.copy_button = self._create_button(save_frame, "", self.copy_to_clipboard, self.copy_icon, width=40)
        self.save_clear_button = self._create_button(save_frame, "", self.clear_generated_data, self.trash_icon, width=40)

        self.save_clear_button.pack(side=ctk.RIGHT, padx=(5, 0))
        self.save_clear_button.pack_forget()
        self.copy_button.pack(side=ctk.RIGHT, padx=(5, 0))
        self.copy_button.pack_forget()

    def _setup_right_panel(self):
        right_panel = ctk.CTkFrame(self.main_screen, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew")

        results_section = ctk.CTkFrame(right_panel)
        results_section.pack(fill=ctk.BOTH, expand=True)

        title_frame = ctk.CTkFrame(results_section, fg_color="transparent")
        title_frame.pack(pady=(UI_PADDING_SECTION, 10), fill=ctk.X)
        self._create_label(title_frame, "Vygenerovaná data", bold=True, size=UI_FONT_TITLE).pack()

        self.results_text = ctk.CTkTextbox(
            results_section, font=ctk.CTkFont(family="Courier", size=12), wrap=ctk.WORD, state="disabled"
        )
        self.results_text.pack(fill=ctk.BOTH, expand=True, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SECTION))

        self.stats_frame = ctk.CTkFrame(results_section, fg_color="transparent")
        self.stats_frame.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SECTION))

        self.entropy_label = self._create_label(self.stats_frame, "Entropie: N/A")
        self.entropy_label.pack(side=ctk.LEFT)
        self.timer_label = self._create_label(self.stats_frame, "Čas: 0.0 s")
        self.timer_label.pack(side=ctk.LEFT, expand=True)
        self.compression_label = self._create_label(self.stats_frame, "Kompresní poměr: N/A")
        self.compression_label.pack(side=ctk.RIGHT)

    def show_main_screen(self):
        self.main_screen.pack(fill=ctk.BOTH, expand=True)
        self.current_screen = "main"
        self.update_ui()

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'+{x}+{y}')

    def start_device_monitoring(self):
        self.stop_monitoring = False
        self.monitor_thread = threading.Thread(target=self.monitor_device_status, daemon=True)
        self.monitor_thread.start()

    def stop_device_monitoring(self):
        self.stop_monitoring = True
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)

    def monitor_device_status(self):
        last_connection_status = None
        last_device_count = 0

        while not self.stop_monitoring:
            try:
                current_status = self._get_connection_status_text()
                current_device_count = len(self.quantis.get_available_devices_list()) if self.quantis else 0

                if current_status != last_connection_status or current_device_count != last_device_count:
                    self.update_connection_status()
                    if current_device_count != last_device_count:
                        self.update_device_list()

                    last_connection_status = current_status
                    last_device_count = current_device_count
            except Exception as e:
                print(f"Chyba při monitorování: {e}")

            time.sleep(2)

    def _get_connection_status_text(self):
        if not self.quantis:
            return "Knihovna není načtena"

        try:
            is_connected = self.quantis.is_device_connected()
            if is_connected:
                return "Zařízení připojeno"
            else:
                device_count = len(self.quantis.get_available_devices_list())
                return f"Zařízení odpojeno ({device_count} zařízení k dispozici)"
        except Exception:
            return "Chyba"

    def update_connection_status(self):
        if self.mode == "software":
            self.status_label.configure(text="Softwarový režim", text_color="green")
            self.device_count_label.configure(text="", text_color="white")
            self._update_captured_bits()
            return

        if not self.quantis:
            return

        try:
            is_connected = self.quantis.is_device_connected()
            if is_connected:
                self.status_label.configure(text="Zařízení připojeno", text_color="green")
                self.device_count_label.configure(text="", text_color="white")
            else:
                count = len(self.quantis.get_available_devices_list())
                self.status_label.configure(text="Zařízení odpojeno", text_color="red")
                self.device_count_label.configure(text=f" ({count} zařízení k dispozici)", text_color="white")
        except Exception as e:
            self.status_label.configure(text=f"Chyba ({e})", text_color="red")
            self.device_count_label.configure(text="", text_color="white")

    def update_device_list(self):
        if not self.quantis:
            return

        try:
            devices = self.quantis.get_available_devices_list()
            device_names = ["Zvolit zařízení", "Softwarový režim"] + [str(device) for device in devices]

            self.device_combo.configure(values=device_names)

            current_device = self.device_var.get()
            if not current_device or current_device not in device_names:
                if devices:
                    self.device_var.set(str(devices[0]))
                    self.quantis.select_device(devices[0])
                else:
                    self.device_var.set("Zvolit zařízení")

        except Exception as e:
            print(f"Chyba při aktualizaci seznamu zařízení: {e}")

    def update_software_ui(self):
        if self.software_frame is None:
            if hasattr(self, 'device_section'):
                self.software_frame = ctk.CTkFrame(self.device_section, fg_color="transparent")
            else:
                return
        if self.mode == "software":
            if getattr(self, 'collect_button', None) is None:
                self.collect_button = self._create_button(self.software_frame, "Spustit sběr dat pro seed", self.toggle_collection)
            if getattr(self, 'seed_label', None) is None:
                self.seed_label = self._create_label(self.software_frame, "", text_color="white", size=12, anchor='center')

            self.software_frame.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))
            try:
                self.collect_button.pack(fill=ctk.X, pady=(0, 6))
                self.seed_label.pack(fill=ctk.X, pady=(0, 0))
                try:
                    self.captured_bits_label.pack(side=ctk.RIGHT)
                except Exception:
                    pass
            except Exception:
                pass
        elif self.software_frame:
            self.software_frame.pack_forget()
            try:
                self.captured_bits_label.pack_forget()
            except Exception:
                pass

    def toggle_collection(self):
        if self.is_collecting:
            self.stop_collection()
        else:
            self.start_collection()

    def start_collection(self):
        self.is_collecting = True
        self.collect_button.configure(text="Zastavit sběr dat pro seed")
        self.collected_data = []
        self.captured_bits = 0
        self.seed = None
        self.software_seed_ready = False
        self._update_captured_bits()
        self.seed_label.configure(text="")
        for ev, handler in [('<Key>', self.on_key_event), ('<Motion>', self.on_motion_event),
                            ('<ButtonPress>', self.on_button_press), ('<ButtonRelease>', self.on_button_release)]:
            self.root.bind(ev, handler)

    def stop_collection(self):
        self.is_collecting = False
        self.collect_button.configure(text="Spustit sběr dat pro seed")
        for ev in ['<Key>', '<Motion>', '<ButtonPress>', '<ButtonRelease>']:
            self.root.unbind(ev)
        self.software_seed_ready = False
        if self.collected_data:
            data_str = ''.join(str(d) for d in self.collected_data)
            self.seed = hashlib.sha3_512(data_str.encode()).hexdigest()
            self.data_generator.set_seed(self.seed)
            display = self.seed[:8] + "..." + self.seed[-3:] if len(self.seed) > 11 else self.seed
            self.seed_label.configure(text=display)
            self.software_seed_ready = True
        self._update_captured_bits()

    def _software_seed_is_ready(self):
        return bool(self.seed) and bool(getattr(self, "software_seed_ready", False))

    def _ensure_software_seed_ready(self):
        if self.mode != "software":
            return True
        if self.is_collecting:
            messagebox.showwarning("Varování", "Nejprve dokončete sběr dat pro seed.")
            return False
        if not self._software_seed_is_ready():
            messagebox.showwarning("Varování", "Pro softwarový režim spusťte sběr dat pro nový seed.")
            return False
        return True

    def _consume_software_seed(self):
        if self.mode != "software":
            return
        self.software_seed_ready = False
        self.seed = None
        if getattr(self, 'seed_label', None):
            self.seed_label.configure(text="")

    def _update_captured_bits(self):
        try:
            self.captured_bits_label.configure(text=f"Zachyceno: {format_bits(self.captured_bits)}")
        except Exception:
            pass

    def _add_collected_item(self, item):
        if self.is_collecting:
            self.collected_data.append(item)
            self.captured_bits += len(str(item).encode('utf-8')) * 8
            self._update_captured_bits()

    def on_key_event(self, event):
        self._add_collected_item(('key', event.keysym, time.time()))

    def on_motion_event(self, event):
        self._add_collected_item(('move', event.x_root, event.y_root, time.time()))

    def on_button_press(self, event):
        self._add_collected_item(('press', event.x_root, event.y_root, event.num, time.time()))

    def on_button_release(self, event):
        self._add_collected_item(('release', event.x_root, event.y_root, event.num, time.time()))

    def on_device_changed(self, event=None):
        if not self.quantis:
            return

        device_name = self.device_var.get()
        if not device_name:
            return

        if device_name == "Softwarový režim":
            self.mode = "software"
            self.update_software_ui()
            self.update_connection_status()
            self.update_window_size()
            return

        self.mode = "hardware"
        self.update_software_ui()
        self.update_window_size()

        try:
            if device_name == "Zvolit zařízení":
                self.quantis.selected_device = None
                self.update_connection_status()
                self.update_window_size()
                return

            devices = self.quantis.get_available_devices_list()
            for device in devices:
                if str(device) == device_name:
                    self.quantis.select_device(device)
                    self._enable_device_modules(device)
                    self.update_connection_status()
                    self.update_window_size()
                    break
        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo vybrat zařízení:\n{e}")

    def refresh_devices(self):
        if self.quantis:
            self.quantis.refresh_devices()
            self.update_device_list()
            self.update_connection_status()

    def on_data_type_changed(self, event=None):
        data_type = self.data_type_var.get()
        if data_type in NON_SCALABLE_TYPES and self.use_scaling_var.get():
            self.use_scaling_var.set(False)
            self.data_format_var.set(DataFormat.ONE_PER_LINE.value)
        self.update_scaling_controls()
        self.update_size_estimate()

    def on_scaling_changed(self):
        self.update_scaling_controls()
        self.update_size_estimate()

    def on_count_changed(self):
        self.update_size_estimate()

    def update_scaling_controls(self):
        for attr in ('int_scaling_row', 'float_scaling_row'):
            try:
                getattr(self, attr).pack_forget()
            except AttributeError:
                pass
        self.scaling_controls_frame.pack_forget()

        data_type = self.data_type_var.get()

        if data_type in NON_SCALABLE_TYPES:
            self.scaling_checkbox.configure(state="disabled", text="Škálování není dostupné pro tento typ")
        else:
            self.scaling_checkbox.configure(state="normal", text="Použít škálování")

        try:
            self.unsigned_checkbox.grid_forget()
        except Exception:
            pass
        if data_type == "int":
            self.unsigned_checkbox.grid(row=0, column=1, sticky="e", padx=(UI_PADDING_SMALL, 0))

        try:
            self.string_options_frame.pack_forget()
            for cb in (self.string_lowercase_cb, self.string_uppercase_cb, self.string_digits_cb, self.string_special_cb):
                cb.grid_forget()
        except Exception:
            pass
        if data_type == "string":
            self.string_options_frame.pack(fill=ctk.X, pady=(UI_PADDING_SMALL, 4))
            self.string_lowercase_cb.grid(row=0, column=0, sticky="w", padx=(0, UI_PADDING_SMALL))
            self.string_uppercase_cb.grid(row=0, column=1, sticky="e", padx=(UI_PADDING_SMALL, 0))
            self.string_digits_cb.grid(row=1, column=0, sticky="w", padx=(0, UI_PADDING_SMALL), pady=(UI_PADDING_SMALL, 0))
            self.string_special_cb.grid(row=1, column=1, sticky="e", padx=(UI_PADDING_SMALL, 0), pady=(UI_PADDING_SMALL, 0))

        try:
            self.length_label.pack_forget()
            self.length_entry.pack_forget()
        except Exception:
            pass
        self.count_label.pack_forget()
        self.count_entry.pack_forget()

        if data_type in VARIABLE_LENGTH_TYPES:
            self.length_label.pack(padx=UI_PADDING_SECTION, pady=(0, 4), anchor=ctk.W)
            self.length_entry.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

        self.count_label.pack(padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL), anchor=ctk.W)
        self.count_entry.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SMALL))

        if self.use_scaling_var.get() and data_type not in NON_SCALABLE_TYPES:
            self.scaling_controls_frame.pack(fill=ctk.X)
            if data_type == "int":
                if not hasattr(self, 'int_scaling_row'):
                    self.int_scaling_row = self.create_scaling_row_frame(self.scaling_controls_frame, self.min_int_var, self.max_int_var)
                self.int_scaling_row.pack(fill=ctk.X, pady=(UI_PADDING_SMALL, UI_PADDING_SMALL))
            elif data_type in ("float", "double"):
                if not hasattr(self, 'float_scaling_row'):
                    self.float_scaling_row = self.create_scaling_row_frame(self.scaling_controls_frame, self.min_float_var, self.max_float_var)
                self.float_scaling_row.pack(fill=ctk.X, pady=(UI_PADDING_SMALL, UI_PADDING_SMALL))

        self.update_window_size()

    def create_scaling_row_frame(self, parent, min_var, max_var):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._create_label(frame, "Min:", width=30).pack(side=ctk.LEFT)
        ctk.CTkEntry(frame, textvariable=min_var, width=80, height=UI_ENTRY_HEIGHT).pack(side=ctk.LEFT, padx=(UI_PADDING_SMALL, UI_PADDING_SECTION))
        self._create_label(frame, "Max:", width=30).pack(side=ctk.LEFT, padx=(UI_PADDING_SECTION, 0))
        ctk.CTkEntry(frame, textvariable=max_var, width=80, height=UI_ENTRY_HEIGHT).pack(side=ctk.LEFT, padx=(UI_PADDING_SMALL, 0))
        return frame

    def update_window_size(self):
        data_type = self.data_type_var.get()
        scaling_visible = self.use_scaling_var.get() and data_type not in NON_SCALABLE_TYPES
        is_software = getattr(self, 'mode', None) == 'software'
        base = 780 if is_software else 700
        if scaling_visible:
            h = 830 if is_software else 750
        elif data_type == "string":
            h = 925 if is_software else 840
        elif data_type == "bits":
            h = 855 if is_software else 775
        else:
            h = base
        self.root.geometry(f"1080x{h}")

    def update_size_estimate(self):
        count = self.count_var.get()
        data_type = self.data_type_var.get()

        bits_per_value = get_bits_per_value(data_type, self.length_var.get())
        total_bits = count * bits_per_value
        size_text = format_bits(total_bits)

        self.size_label.configure(text=f"Odhadovaná velikost: {size_text}")

    def update_ui(self):
        self.update_scaling_controls()
        self.update_size_estimate()
        self.update_connection_status()
        self.update_device_list()
        self.update_save_clear_button_visibility()

    def _update_timer_label(self):
        if not hasattr(self, 'timer_label'):
            return
        elapsed = time.time() - self.generation_start_time if self.timer_running and self.generation_start_time else self.generation_elapsed
        self.timer_label.configure(text=f"Čas: {elapsed:.1f} s")
        if self.timer_running:
            self._timer_after_id = self.root.after(100, self._update_timer_label)

    def start_timer(self):
        if self.timer_running:
            return
        self.generation_start_time = time.time() - self.generation_elapsed
        self.timer_running = True
        self._update_timer_label()

    def stop_timer(self):
        if not self.timer_running:
            return
        if self.generation_start_time is not None:
            self.generation_elapsed = time.time() - self.generation_start_time
        self.timer_running = False
        try:
            if self._timer_after_id:
                self.root.after_cancel(self._timer_after_id)
        except Exception:
            pass
        self._timer_after_id = None
        if hasattr(self, 'timer_label'):
            self.timer_label.configure(text=f"Čas: {self.generation_elapsed:.1f} s")

    def reset_timer(self):
        self.stop_timer()
        self.generation_elapsed = 0.0
        self.generation_start_time = None
        if hasattr(self, 'timer_label'):
            self.timer_label.configure(text="Čas: 0.0 s")

    def _get_generation_params(self):
        return {
            'data_type': self.data_type_var.get(),
            'use_scaling': self.use_scaling_var.get(),
            'min_int': self.min_int_var.get(),
            'max_int': self.max_int_var.get(),
            'min_float': self.min_float_var.get(),
            'max_float': self.max_float_var.get(),
            'unsigned': self.unsigned_var.get(),
            'length': self.length_var.get(),
            'lowercase': self.string_lowercase_var.get(),
            'uppercase': self.string_uppercase_var.get(),
            'digits': self.string_digits_var.get(),
            'special': self.string_special_var.get()
        }

    def _validate_string_checkboxes(self):
        if self.data_type_var.get() != "string":
            return True
        if not any([self.string_lowercase_var.get(), self.string_uppercase_var.get(), 
                    self.string_digits_var.get(), self.string_special_var.get()]):
            messagebox.showwarning("Varování", "Pro generování řetězců musí být zvolen alespoň jeden checkbox!")
            return False
        return True

    def generate_data(self):
        if self._generation_in_progress:
            return

        if self.mode == "hardware" and (not self.quantis or not self.quantis.is_device_connected()):
            messagebox.showwarning("Varování", "Zařízení není připojeno!")
            return

        if not self._ensure_software_seed_ready():
            return

        if not self._validate_string_checkboxes():
            return

        try:
            count = int(self.count_var.get())
            params = self._get_generation_params()
            self.generated_values = []
            self.display_results()
            self.update_save_clear_button_visibility()
            self._generation_in_progress = True

            if self.mode == "software":
                self._consume_software_seed()

            def worker(count, params):
                try:
                    if self.mode == "hardware" and self.quantis and self.quantis.selected_device:
                        self._enable_device_modules(self.quantis.selected_device)
                    reader = self.data_generator.get_reader(self.mode, **params)
                    temp = []
                    for _ in range(max(0, count)):
                        for attempt in range(3):
                            try:
                                temp.append(reader())
                                break
                            except Exception as read_err:
                                if attempt == 2:
                                    raise read_err
                                time.sleep(0.05)
                    bits_per = get_bits_per_value(params['data_type'], params['length'])
                    entropy = calculate_entropy(temp, params['data_type'])
                    compression = calculate_compression_ratio(temp, params['data_type'])
                    self.stats_manager.update_stats(params['data_type'], len(temp), len(temp) * int(bits_per), self.mode, entropy, compression)

                    def finish():
                        self._generation_in_progress = False
                        self.generated_values = temp[-MAX_DISPLAY_VALUES:] if len(temp) > MAX_DISPLAY_VALUES else temp
                        self.display_results()
                        self.update_save_clear_button_visibility()
                        self.stop_timer()

                    self.root.after(0, finish)
                except Exception as e:
                    def on_error():
                        self._generation_in_progress = False
                        messagebox.showerror("Chyba", f"Neočekávaná chyba:\n{e}")
                        self.stop_timer()
                    self.root.after(0, on_error)

            self.reset_timer()
            self.start_timer()
            self._generate_thread = threading.Thread(target=worker, args=(count, params), daemon=True)
            self._generate_thread.start()
        except Exception as e:
            self._generation_in_progress = False
            messagebox.showerror("Chyba", f"Neočekávaná chyba:\n{e}")

    def display_results(self):
        self.results_text.configure(state="normal")
        self.results_text.delete("0.0", ctk.END)

        if not self.generated_values:
            self.results_text.configure(state="disabled")
            try:
                self.entropy_label.configure(text="Entropie: N/A")
                self.compression_label.configure(text="Kompresní poměr: N/A")
            except Exception:
                pass
            return

        data_type = self.data_type_var.get()
        is_csv = self.data_format_var.get() == DataFormat.CSV.value
        formatted = [format_value(v, data_type, is_csv) for v in self.generated_values]
        content = ",".join(formatted) if is_csv else "\n".join(formatted) + "\n"

        self.results_text.insert(ctk.END, content)
        self.results_text.see(ctk.END)
        self.results_text.configure(state="disabled")

        entropy = calculate_entropy(self.generated_values, data_type)
        compression = calculate_compression_ratio(self.generated_values, data_type)
        self.entropy_label.configure(text=f"Entropie: {entropy:.10f} b/bit")
        self.compression_label.configure(text=f"Kompresní poměr: {compression:.10f}")

    def toggle_continuous(self):
        if self.is_generating:
            self.stop_continuous()
        else:
            self.start_continuous()

    def start_continuous(self):
        if self.mode == "hardware" and (not self.quantis or not self.quantis.is_device_connected()):
            messagebox.showwarning("Varování", "Zařízení není připojeno!")
            return

        if not self._ensure_software_seed_ready():
            return

        if not self._validate_string_checkboxes():
            return

        self.is_generating = True
        self.continuous_button.configure(text="Zastavit kontinuální generování")
        self.generated_values.clear()
        self.reset_timer()
        self.start_timer()
        self.display_results()
        self.update_save_clear_button_visibility()
        self.continuous_data_type = self.data_type_var.get()
        self.continuous_use_scaling = self.use_scaling_var.get()
        if self.mode == "software":
            self._consume_software_seed()
        self.continuous_thread = threading.Thread(target=self.continuous_generation_loop, daemon=True)
        self.continuous_thread.start()

    def stop_continuous(self):
        self.is_generating = False
        self.continuous_button.configure(text="Spustit kontinuální generování")
        self.continuous_data_type = None
        self.continuous_use_scaling = None
        self.stop_timer()

    def continuous_generation_loop(self):
        while self.is_generating:
            if self.mode == "hardware" and (not self.quantis or not self.quantis.is_device_connected()):
                self.root.after(0, lambda: messagebox.showerror("Chyba", "Zařízení odpojeno"))
                self.root.after(0, self.stop_continuous)
                break
            try:
                self.generate_single_value()
                time.sleep(0.55)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Chyba", f"Chyba při generování:\n{e}"))
                self.root.after(0, self.stop_continuous)
                break

    def generate_single_value(self):
        if not self.quantis:
            return

        try:
            current_dt = self.data_type_var.get()
            current_scaling = self.use_scaling_var.get()

            if self.continuous_data_type != current_dt or self.continuous_use_scaling != current_scaling:
                self.generated_values.clear()
                self.continuous_data_type = current_dt
                self.continuous_use_scaling = current_scaling

            params = self._get_generation_params()
            
            value = None
            for attempt in range(3):
                try:
                    value = self.data_generator.get_reader(self.mode, **params)()
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(0.05)
            
            if value is None:
                return
                
            bits_per = get_bits_per_value(current_dt, params['length'])
            
            temp_values = self.generated_values + [value]
            entropy = calculate_entropy(temp_values, current_dt)
            compression = calculate_compression_ratio(temp_values, current_dt)
            self.stats_manager.update_stats(current_dt, 1, bits_per, self.mode, entropy, compression)

            self.generated_values.append(value)
            if len(self.generated_values) > MAX_DISPLAY_VALUES:
                self.generated_values = self.generated_values[-MAX_DISPLAY_VALUES:]

            self.display_results()
            self.update_save_clear_button_visibility()
        except Exception as e:
            print(f"Chyba při generování hodnoty: {e}")

    def copy_to_clipboard(self):
        if not self.generated_values:
            messagebox.showwarning("Varování", "Žádná data ke zkopírování!")
            return
        try:
            content = self.results_text.get("0.0", ctk.END).strip()
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.root.update()
        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo zkopírovat data:\n{e}")

    def save_to_file(self):
        if not self.generated_values:
            messagebox.showwarning("Varování", "Žádná data k uložení!")
            return
        try:
            path = filedialog.asksaveasfilename(
                title="Uložit data", defaultextension=".txt",
                filetypes=[("Textové soubory", "*.txt"), ("CSV soubory", "*.csv")]
            )
            if not path:
                return

            data_type = self.data_type_var.get()
            with open(path, 'w', encoding='utf-8') as f:
                if path.lower().endswith('.csv'):
                    f.write("value\n")
                    f.write(",".join(format_value(v, data_type, True) for v in self.generated_values))
                else:
                    f.writelines(f"{format_value(v, data_type)}\n" for v in self.generated_values)
            messagebox.showinfo("Úspěch", f"Data byla uložena do souboru:\n{path}")
        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo uložit data:\n{e}")

    def clear_generated_data(self):
        if not self.generated_values:
            messagebox.showinfo("Informace", "Žádná data ke smazání!")
            return

        if messagebox.askyesno("Potvrzení", f"Opravdu chcete smazat všechny vygenerované hodnoty?"):
            self.generated_values.clear()
            self.reset_timer()
        self.results_text.configure(state="normal")
        self.results_text.delete("0.0", ctk.END)
        self.results_text.configure(state="disabled")
        self.entropy_label.configure(text="Entropie: N/A")
        self.compression_label.configure(text="Kompresní poměr: N/A")
        self.update_save_clear_button_visibility()

    def update_save_clear_button_visibility(self):
        has_data = bool(self.generated_values)
        self._set_widget_visibility(getattr(self, 'save_clear_button', None), has_data, side=ctk.RIGHT, padx=(5, 0))
        self._set_widget_visibility(getattr(self, 'copy_button', None), has_data, side=ctk.RIGHT, padx=(5, 0))

    def _set_widget_visibility(self, widget, visible, **pack_options):
        if widget:
            widget.pack(**pack_options) if visible else widget.pack_forget()

    def show_info_window(self):
        InfoDialog(self.root, self.quantis)

    def show_stats_window(self):
        StatsDialog(self.root, self.stats_manager)

    def on_closing(self):
        self.stop_device_monitoring()
        if self.is_generating:
            self.stop_continuous()
        if self.is_collecting:
            self.stop_collection()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

def main():
    try:
        app = QuantisApp()
        app.run()
    except Exception as e:
        messagebox.showerror("Kritická chyba", f"Aplikace se nezdařila spustit:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
