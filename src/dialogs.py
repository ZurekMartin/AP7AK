import customtkinter as ctk
from constants import TYPE_NAMES, UI_FONT_NORMAL, UI_FONT_TITLE, UI_PADDING_SECTION, UI_BUTTON_HEIGHT
from tkinter import messagebox
from utils import format_bits

class BaseDialog:
    def __init__(self, parent, title: str, width: int = 450, height: int = 550):
        self.window = ctk.CTkToplevel(parent)
        self.window.title(title)
        self.window.geometry(f"{width}x{height}")
        self.window.resizable(False, False)
        self.window.grab_set()
        self._center_window()
        self._setup_main_frame()

    def _center_window(self):
        self.window.update_idletasks()
        w, h = self.window.winfo_width(), self.window.winfo_height()
        x = (self.window.winfo_screenwidth() - w) // 2
        y = (self.window.winfo_screenheight() - h) // 2
        self.window.geometry(f'+{x}+{y}')

    def _setup_main_frame(self):
        self.main_frame = ctk.CTkFrame(self.window)
        self.main_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)
        self.content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=(0, 20))

    def _create_label(self, parent, text, bold=False, size=UI_FONT_NORMAL, **kwargs):
        font = ctk.CTkFont(size=size, weight="bold" if bold else "normal")
        return ctk.CTkLabel(parent, text=text, font=font, **kwargs)

    def _add_section(self, title: str, info_dict: dict):
        self._create_label(self.content_frame, title, bold=True, size=UI_FONT_TITLE).pack(anchor=ctk.CENTER, pady=(UI_PADDING_SECTION, 10))
        info_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        info_frame.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SECTION))

        for key, value in info_dict.items():
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill=ctk.X, pady=2)
            self._create_label(row, key, bold=True, anchor="w").pack(side=ctk.LEFT, padx=(5, 10))
            self._create_label(row, str(value), anchor="e").pack(side=ctk.RIGHT, padx=(10, 5))

class InfoDialog(BaseDialog):
    def __init__(self, parent, quantis=None):
        height = 450 if quantis and quantis.selected_device else 310
        super().__init__(parent, "Informace", height=height)
        self.quantis = quantis
        self._add_section("Knihovna Quantis", self._get_library_info())
        self._add_section("Zařízení", self._get_device_info())

    def _get_library_info(self) -> dict:
        if not self.quantis:
            return {"Stav": "Knihovna není načtena"}
        from quantis_wrapper import QuantisDeviceType
        info = {"Cesta": self.quantis.library_path, "Verze knihovny": self.quantis.get_library_version()}
        for dt in QuantisDeviceType:
            ver = self.quantis.get_driver_version(dt)
            if ver > 0:
                info[f"Verze ovladače {dt.name}"] = f"{ver:.1f}"
        return info

    def _get_device_info(self) -> dict:
        if not self.quantis or not self.quantis.selected_device:
            return {"Stav": "Žádné zařízení není vybráno"}
        di = self.quantis.get_device_info()
        return {
            "Výrobce": di.get("manufacturer", "N/A"),
            "Název": "Quantis " + di.get("name", "N/A"),
            "Sériové číslo (S/N)": di.get("serial_number", "N/A"),
            "Verze desky": di.get("board_version", "N/A"),
            "Datová rychlost": di.get("data_rate", "N/A"),
        }

class StatsDialog(BaseDialog):
    def __init__(self, parent, stats_manager, on_reset_callback=None):
        super().__init__(parent, "Statistiky", width=550, height=600)
        self.stats_manager = stats_manager
        self.on_reset_callback = on_reset_callback
        self.current_view = "size"
        self.compare_mode = False
        self._add_section("Celkové statistiky", {
            "Počet záznamů": f"{self.stats_manager.get_total_numbers():,}",
            "Počet bitů": format_bits(self.stats_manager.get_total_bits())
        })
        self._add_type_stats_section()
        self._add_action_buttons()

    def update_window_size(self):
        is_compare = hasattr(self, 'compare_mode') and self.compare_mode
        width = 1000 if is_compare else 550
        self.window.geometry(f"{width}x600")

    def _add_type_stats_section(self):
        self._create_label(self.content_frame, "Statistiky vygenerovaných dat", bold=True, size=UI_FONT_TITLE).pack(anchor=ctk.CENTER, pady=(UI_PADDING_SECTION, 10))
        
        btn_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        btn_frame.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, 10))
        btn_frame.grid_columnconfigure(0, weight=1, uniform="stats_btn")
        btn_frame.grid_columnconfigure(1, weight=1, uniform="stats_btn")
        btn_frame.grid_columnconfigure(2, weight=1, uniform="stats_btn")
        
        self.size_btn = ctk.CTkButton(btn_frame, text="Velikost", command=lambda: self._switch_view("size"), height=UI_BUTTON_HEIGHT, font=ctk.CTkFont(size=UI_FONT_NORMAL))
        self.size_btn.grid(row=0, column=0, padx=2, sticky="ew")
        self.hw_btn = ctk.CTkButton(btn_frame, text="HW", command=lambda: self._switch_view("hw"), height=UI_BUTTON_HEIGHT, font=ctk.CTkFont(size=UI_FONT_NORMAL))
        self.hw_btn.grid(row=0, column=1, padx=2, sticky="ew")
        self.sw_btn = ctk.CTkButton(btn_frame, text="SW", command=lambda: self._switch_view("sw"), height=UI_BUTTON_HEIGHT, font=ctk.CTkFont(size=UI_FONT_NORMAL))
        self.sw_btn.grid(row=0, column=2, padx=2, sticky="ew")
        
        self.table_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.table_frame.pack(fill=ctk.X, padx=UI_PADDING_SECTION, pady=(0, UI_PADDING_SECTION))
        
        self._build_view()

    def _switch_view(self, view: str):
        self.current_view = view
        self._build_view()
        self.update_window_size()

    def _clear_table_frame(self):
        for widget in self.table_frame.winfo_children():
            widget.destroy()

    def _build_view(self):
        self._clear_table_frame()
        if self.current_view == "size":
            self._build_size_table()
        elif self.compare_mode:
            self._build_compare_table()
        else:
            self._build_mode_table("hardware" if self.current_view == "hw" else "software")

    def _build_size_table(self):
        table = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        table.pack(fill=ctk.X, pady=(5, 0))
        for i in range(3):
            table.grid_columnconfigure(i, weight=1, uniform="stats_table")

        headers = ["Datový typ", "Počet záznamů", "Počet bitů"]
        for col, text in enumerate(headers):
            self._create_label(table, text, bold=True).grid(row=0, column=col, padx=5, pady=5, sticky="w" if col == 0 else "e")

        all_stats = self.stats_manager.get_all_type_stats()
        for row, type_name in enumerate(TYPE_NAMES, 1):
            ts = all_stats.get(type_name, {"numbers": 0, "bits": 0})
            self._create_label(table, type_name).grid(row=row, column=0, padx=5, pady=2, sticky="w")
            self._create_label(table, f"{ts['numbers']:,}", anchor="e").grid(row=row, column=1, padx=5, pady=2, sticky="e")
            self._create_label(table, format_bits(ts['bits']), anchor="e").grid(row=row, column=2, padx=5, pady=2, sticky="e")

    def _build_mode_table(self, mode: str):
        table = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        table.pack(fill=ctk.X, pady=(5, 0))
        for i in range(3):
            table.grid_columnconfigure(i, weight=1, uniform="stats_table")

        headers = ["Datový typ", "Průměrná entropie", "Průměrná komprese"]
        for col, text in enumerate(headers):
            self._create_label(table, text, bold=True).grid(row=0, column=col, padx=5, pady=5, sticky="w" if col == 0 else "e")

        mode_stats = self.stats_manager.get_mode_stats(mode)
        for row, type_name in enumerate(TYPE_NAMES, 1):
            ts = mode_stats.get(type_name, {"avg_entropy": 0.0, "avg_compression": 0.0})
            self._create_label(table, type_name).grid(row=row, column=0, padx=5, pady=2, sticky="w")
            entropy_text = f"{ts['avg_entropy']:.10f}" if ts['avg_entropy'] > 0 else "N/A"
            compression_text = f"{ts['avg_compression']:.10f}" if ts['avg_compression'] > 0 else "N/A"
            self._create_label(table, entropy_text, anchor="e").grid(row=row, column=1, padx=5, pady=2, sticky="e")
            self._create_label(table, compression_text, anchor="e").grid(row=row, column=2, padx=5, pady=2, sticky="e")

    def _build_compare_table(self):
        table = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        table.pack(fill=ctk.X, pady=(5, 0))
        for i in range(7):
            table.grid_columnconfigure(i, weight=1, uniform="stats_table")

        headers = [
            "Datový typ",
            "HW entropie",
            "SW entropie",
            "Rozdíl entropie",
            "HW komprese",
            "SW komprese",
            "Rozdíl komprese",
        ]
        for col, text in enumerate(headers):
            self._create_label(table, text, bold=True).grid(row=0, column=col, padx=5, pady=5, sticky="w" if col == 0 else "e")

        hw_stats = self.stats_manager.get_mode_stats("hardware")
        sw_stats = self.stats_manager.get_mode_stats("software")
        for row, type_name in enumerate(TYPE_NAMES, 1):
            hw = hw_stats.get(type_name, {"avg_entropy": 0.0, "avg_compression": 0.0})
            sw = sw_stats.get(type_name, {"avg_entropy": 0.0, "avg_compression": 0.0})
            hw_e = hw.get('avg_entropy', 0.0)
            sw_e = sw.get('avg_entropy', 0.0)
            hw_c = hw.get('avg_compression', 0.0)
            sw_c = sw.get('avg_compression', 0.0)

            def fmt(v):
                return f"{v:.10f}"

            e_text_hw = fmt(hw_e) if hw_e else "N/A"
            e_text_sw = fmt(sw_e) if sw_e else "N/A"
            c_text_hw = fmt(hw_c) if hw_c else "N/A"
            c_text_sw = fmt(sw_c) if sw_c else "N/A"

            diff_e = None if (not hw_e or not sw_e) else (hw_e - sw_e)
            diff_c = None if (not hw_c or not sw_c) else (hw_c - sw_c)

            values = [
                type_name,
                e_text_hw,
                e_text_sw,
                diff_e,
                c_text_hw,
                c_text_sw,
                diff_c,
            ]

            for col, val in enumerate(values):
                sticky = "w" if col == 0 else "e"
                if col in (3, 6):
                    if val is None:
                        lbl = self._create_label(table, "N/A")
                        lbl.grid(row=row, column=col, padx=5, pady=2, sticky=sticky)
                    else:
                        sign = "+" if val >= 0 else "-"
                        text = f"{sign}{abs(val):.10f}"
                        color = "#10b981" if val >= 0 else "#ef4444"
                        lbl = self._create_label(table, text, anchor="e", **{"text_color": color})
                        lbl.grid(row=row, column=col, padx=5, pady=2, sticky=sticky)
                else:
                    self._create_label(table, val).grid(row=row, column=col, padx=5, pady=2, sticky=sticky)

    def _add_action_buttons(self):
        frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        frame.pack(pady=(20, 0), fill=ctk.X)
        for i in range(2):
            frame.grid_columnconfigure(i, weight=1, uniform="stats_actions")
        ctk.CTkButton(frame, text="Resetovat statistiky", command=self._on_reset_click, height=UI_BUTTON_HEIGHT, font=ctk.CTkFont(size=UI_FONT_NORMAL)).grid(row=0, column=0, padx=8, sticky="ew")
        self.compare_button = ctk.CTkButton(frame, text="Porovnat statistiky", command=self._toggle_compare, height=UI_BUTTON_HEIGHT, font=ctk.CTkFont(size=UI_FONT_NORMAL))
        self.compare_button.grid(row=0, column=1, padx=8, sticky="ew")

    def _on_reset_click(self):
        if messagebox.askyesno("Potvrzení", "Opravdu chcete resetovat statistiky?"):
            self.stats_manager.reset_stats()
            if self.on_reset_callback:
                self.on_reset_callback()
            self.window.destroy()

    def _toggle_compare(self):
        self.compare_mode = not self.compare_mode
        if self.compare_mode and self.current_view == "size":
            self.current_view = "hw"
        self._build_view()
        self.update_window_size()
