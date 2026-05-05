import os
import shutil
import json
import threading
import time
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from datetime import datetime
import vlc # New powerful audio engine
import drag_source
import pythoncom
import ctypes
from ctypes import windll
import requests
import subprocess
import sys

CURRENT_VERSION = "1.0.0"

# Remove winmm since we are upgrading to VLC

# Corporate Trust - Dark Edition Design Tokens
COLORS = {
    "bg_main": "#14100C",      # Warm Dark Slate
    "bg_surface": "#211A14",   # Warm Surface
    "bg_sidebar": "#0D0A08",   # Deepest Warm Navy/Brown
    "primary": "#FF910B",      # Requested Brand Amber/Yellow
    "secondary": "#D97706",    # Deeper Amber for hovers
    "text_main": "#FDF8F3",    # Tinted Off-White
    "text_muted": "#A89C90",   # Warm Muted Gray
    "border": "#362B21",       # Warm Border
    "success": "#10B981",      # Emerald
    "warning": "#EF4444"       # Red (since primary is orange)
}

# Typography Tokens
FONTS = {
    "title": "Space Grotesk",
    "text": "JetBrains Mono"
}

def load_custom_fonts():
    """Nạp font từ thư mục assets/fonts mà không cần cài đặt vào hệ thống Windows."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    font_dir = os.path.join(script_dir, "assets", "fonts")
    
    if not os.path.exists(font_dir):
        # Nếu chưa có thư mục, tạo sẵn để người dùng copy vào
        os.makedirs(font_dir, exist_ok=True)
        return

    # Constants cho GDI (Windows Font System)
    FR_PRIVATE = 0x10 # Font chỉ tồn tại trong tiến trình này, không cài vào máy
    
    loaded_count = 0
    for font_file in os.listdir(font_dir):
        if font_file.lower().endswith((".ttf", ".otf")):
            font_path = os.path.normpath(os.path.join(font_dir, font_file))
            try:
                # Gọi Windows API để nạp font vào bộ nhớ của App
                res = windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(font_path), FR_PRIVATE, 0)
                if res > 0:
                    loaded_count += 1
            except Exception as e:
                print(f"Lỗi nạp font {font_file}: {e}")
    
    if loaded_count > 0:
        print(f"DEBUG: Successfully loaded {loaded_count} fonts from assets/fonts")

# Set appearance and theme
ctk.set_appearance_mode("Dark")

class MusicOrganizerApp(ctk.CTk):
    def __init__(self):
        # Nạp font trước khi vẽ UI
        load_custom_fonts()
        
        super().__init__()
        
        # Initialize OLE for Drag and Drop
        try:
            import pythoncom
            pythoncom.OleInitialize()
        except:
            pass

        self.title("Power Music")
        self.geometry("1200x750")
        self.configure(fg_color=COLORS["bg_main"])

        # Load configuration
        # Ensure we look for config.json in the same directory as this script on Drive F
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(script_dir, "config.json")
        self.load_config()

        # State
        self.all_files = []
        self.filtered_files = []
        self.selected_cat_to_action = None
        self.current_source_path = self.config.get('source_dir')
        self.current_folder_name = "THƯ MỤC GỐC"
        
        # VLC Player Setup with Fallback
        try:
            self.vlc_instance = vlc.Instance('--no-video')
            self.player = self.vlc_instance.media_player_new()
            self.vlc_available = True
        except Exception:
            self.vlc_available = False
            self.vlc_instance = None
            self.player = None
        
        self.current_playing = None
        self.is_playing = False
        self.song_length_ms = 0

        # UI Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar (Deep Dark)
        self.sidebar_frame = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=COLORS["bg_sidebar"], border_width=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1) # The folder list should be the flexible one

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="P O W E R   M U S I C", 
            font=ctk.CTkFont(family=FONTS["title"], size=20, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        self.stats_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="0 Files Selected", 
            text_color=COLORS["text_muted"],
            font=ctk.CTkFont(family=FONTS["text"], size=13)
        )
        self.stats_label.grid(row=1, column=0, padx=20, pady=(0, 20))
        
        self.refresh_button = ctk.CTkButton(
            self.sidebar_frame, 
            text="🏠 Thư mục gốc", 
            fg_color=COLORS["primary"],
            hover_color=COLORS["secondary"],
            height=40,
            font=ctk.CTkFont(family=FONTS["text"], weight="bold"),
            command=self.view_root_folder
        )

        # Quick Add in Sidebar (Defined first)
        self.add_cat_label = ctk.CTkLabel(self.sidebar_frame, text="THÊM FOLDER MỚI", font=ctk.CTkFont(family=FONTS["title"], size=11, weight="bold"), text_color=COLORS["text_muted"])
        self.add_cat_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        
        self.new_cat_entry = ctk.CTkEntry(
            self.add_cat_frame, 
            placeholder_text="Tên folder...", 
            height=35, 
            fg_color=COLORS["bg_surface"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(family=FONTS["text"], size=12)
        )
        self.new_cat_entry.grid(row=0, column=0, padx=(0, 5), sticky="ew")
        self.new_cat_entry.bind("<Return>", lambda e: self.add_category_event())

        self.add_cat_btn = ctk.CTkButton(
            self.add_cat_frame, text="+", width=35, height=35, 
            fg_color=COLORS["bg_surface"], 
            border_width=1,
            border_color=COLORS["border"],
            hover_color=COLORS["primary"],
            command=self.add_category_event
        )
        self.add_cat_btn.grid(row=0, column=1)

        # Layout in Sidebar
        self.refresh_button.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.nav_label = ctk.CTkLabel(self.sidebar_frame, text="THƯ VIỆN ĐÃ PHÂN LOẠI", font=ctk.CTkFont(family=FONTS["title"], size=11, weight="bold"), text_color=COLORS["text_muted"])
        self.nav_label.grid(row=3, column=0, padx=20, pady=(20, 5), sticky="w")

        self.nav_frame = ctk.CTkScrollableFrame(self.sidebar_frame, fg_color="transparent", height=250)
        self.nav_frame.grid(row=4, column=0, padx=10, pady=5, sticky="nsew")
        
        self.add_cat_label.grid(row=5, column=0, padx=20, pady=(20, 5), sticky="w")
        self.add_cat_frame.grid(row=6, column=0, padx=20, pady=5, sticky="ew")
        self.add_cat_frame.grid_columnconfigure(0, weight=1)

        # Bottom Sidebar Buttons Frame
        self.bottom_sidebar_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.bottom_sidebar_frame.grid(row=7, column=0, padx=20, pady=(10, 20), sticky="ew")

        # Appearance Menu
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(
            self.bottom_sidebar_frame, 
            values=["Dark", "Light"],
            width=100,
            fg_color=COLORS["bg_surface"],
            button_color=COLORS["bg_surface"],
            button_hover_color=COLORS["primary"],
            command=self.change_appearance_mode_event
        )
        self.appearance_mode_optionemenu.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.settings_btn = ctk.CTkButton(
            self.bottom_sidebar_frame, 
            text="⚙️", 
            width=40,
            fg_color=COLORS["bg_surface"],
            hover_color=COLORS["primary"],
            command=self.open_settings_dialog
        )
        self.settings_btn.pack(side="right")

        # Check config on startup
        self.after(500, self.check_initial_config)
        
        # Check for updates
        self.after(2000, self.check_for_updates)

        # Main Content
        self.main_frame = ctk.CTkFrame(self, corner_radius=16, fg_color=COLORS["bg_surface"], border_width=1, border_color=COLORS["border"])
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)

        self.search_entry = ctk.CTkEntry(
            self.main_frame, 
            placeholder_text="🔍 Tìm kiếm file âm thanh...", 
            height=45,
            fg_color=COLORS["bg_main"],
            border_color=COLORS["border"],
            corner_radius=10
        )
        self.search_entry.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.search_entry.bind("<KeyRelease>", self.filter_files)

        self.file_list_label = ctk.CTkLabel(self.main_frame, text="THƯ MỤC GỐC", font=ctk.CTkFont(family=FONTS["title"], size=12, weight="bold"), text_color=COLORS["primary"])
        self.file_list_label.grid(row=1, column=0, padx=25, pady=(5, 5), sticky="w")

        # List Containers (Cached for Speed)
        self.list_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="nsew")
        
        # Frame for Root Folder (Always kept in memory)
        self.root_scroll = ctk.CTkScrollableFrame(self.list_frame, fg_color="transparent")
        self.root_scroll.pack(fill="both", expand=True)
        
        # Frame for Subfolders (Rebuilt on switch)
        self.sub_scroll = ctk.CTkScrollableFrame(self.list_frame, fg_color="transparent")
        # sub_scroll is not packed by default
        
        self.root_widgets = {}
        self.sub_widgets = {}
        self.song_widgets = {} # Pointer to the currently active widget set
        self.selected_files = set()
        self.root_loaded = False
        
        # Drag and Drop State
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        # Right Panel (Categories) REMOVED for Power Bin layout
        
        # Custom Action Popup (Replacing native Menu)
        self.action_popup = ctk.CTkFrame(
            self, 
            fg_color=COLORS["bg_surface"], 
            border_width=1, 
            border_color=COLORS["border"],
            corner_radius=8,
            width=220
        )
        self.action_popup.grid_columnconfigure(0, weight=1)

        self.rename_btn = ctk.CTkButton(
            self.action_popup, 
            text="✏️  Đổi tên thể loại", 
            fg_color="transparent",
            hover_color=COLORS["border"], # Subtle structural hover, not loud primary
            text_color=COLORS["text_main"],
            anchor="w",
            height=36,
            font=ctk.CTkFont(family=FONTS["text"], size=13),
            command=self.rename_category_event
        )
        self.rename_btn.pack(fill="x", padx=8, pady=(8, 2))

        self.delete_btn = ctk.CTkButton(
            self.action_popup, 
            text="🗑️  Xóa thể loại này", 
            fg_color="transparent",
            hover_color="#5A1A1A", # Deep muted red
            text_color="#FCA5A5", # Soft red text for destructive action
            anchor="w",
            height=36,
            font=ctk.CTkFont(family=FONTS["text"], size=13),
            command=self.delete_category_event
        )
        self.delete_btn.pack(fill="x", padx=8, pady=(2, 8))

        self.action_popup.place_forget() # Hide initially
        self.selected_cat_to_action = None

        # Bind to hide popup when clicking elsewhere (only if clicking on main window)
        self.bind("<Button-1>", self.check_hide_popup)

        # Player Bar (Cinematic Player)
        self.player_frame = ctk.CTkFrame(self, height=100, fg_color=COLORS["bg_sidebar"], corner_radius=0, border_width=1, border_color=COLORS["border"])
        self.player_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        
        # Waveform Canvas
        self.wave_canvas = tk.Canvas(self.player_frame, height=60, bg=COLORS["bg_sidebar"], highlightthickness=0, borderwidth=0)
        self.wave_canvas.pack(side="left", fill="both", expand=True, padx=20)
        self.wave_canvas.bind("<Button-1>", self.on_wave_click)
        self.wave_canvas.bind("<B1-Motion>", self.on_wave_drag)
        self.wave_canvas.bind("<ButtonRelease-1>", self.on_song_release)
        
        self.song_length_ms = 0
        
        self.player_controls = ctk.CTkFrame(self.player_frame, fg_color="transparent")
        self.player_controls.pack(side="right", padx=20)

        self.play_btn = ctk.CTkButton(self.player_controls, text="▶ PLAY", width=100, height=40, font=ctk.CTkFont(family=FONTS["text"], weight="bold"), command=self.toggle_play)
        self.play_btn.pack(side="left", padx=5)

        self.stop_btn = ctk.CTkButton(self.player_controls, text="⏹", width=40, height=40, fg_color="#334155", command=self.stop_music)
        self.stop_btn.pack(side="left", padx=5)

        self.now_playing_label = ctk.CTkLabel(self.player_frame, text="Chọn bài hát để nghe thử...", font=ctk.CTkFont(family=FONTS["text"], size=12, slant="italic"), text_color=COLORS["text_muted"])
        self.now_playing_label.place(relx=0.5, rely=0.2, anchor="center")

        # Status Bar
        self.status_bar_frame = ctk.CTkFrame(self, height=25, fg_color="#020617", corner_radius=0)
        self.status_bar_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        
        self.status_bar = ctk.CTkLabel(self.status_bar_frame, text="Sẵn sàng", font=ctk.CTkFont(family=FONTS["text"], size=11), text_color=COLORS["text_muted"])
        self.status_bar.pack(side="left", padx=20)

        # Bindings
        self.bind("<F5>", lambda e: self.refresh_file_list())
        self.bind("<space>", lambda e: self.toggle_play_hotkey())
        self.bind("<Delete>", lambda e: self.delete_selected_files_event())
        self.bind("<Up>", self.on_key_up)
        self.bind("<Down>", self.on_key_down)
        self.bind("<Return>", self.on_key_enter)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.update_nav_links()
        self.refresh_file_list()

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception:
            self.config = {"source_dir": "", "dest_root": "", "categories": []}

    def save_config(self):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.update_status(f"Lỗi khi lưu cấu hình: {str(e)}", "error")

    # def create_category_buttons(self): ... Removed

    def check_initial_config(self):
        if not self.config.get("source_dir") or not self.config.get("dest_root"):
            self.open_settings_dialog()

    def open_settings_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Cài đặt Thư mục")
        dialog.geometry("550x450")
        dialog.grab_set()
        dialog.attributes('-topmost', 'true')
        
        # Source Dir
        ctk.CTkLabel(dialog, text="Thư mục Kho Nhạc Gốc (Nơi chứa nhạc chưa phân loại):", font=ctk.CTkFont(family=FONTS["title"], weight="bold", size=13)).pack(pady=(20, 5), padx=20, anchor="w")
        src_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        src_frame.pack(fill="x", padx=20)
        src_entry = ctk.CTkEntry(src_frame, height=35)
        src_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        src_entry.insert(0, self.config.get("source_dir", ""))
        
        def browse_src():
            d = filedialog.askdirectory()
            if d:
                src_entry.delete(0, tk.END)
                src_entry.insert(0, d)
        ctk.CTkButton(src_frame, text="Chọn", width=60, height=35, command=browse_src).pack(side="right")
        
        # Dest Root
        ctk.CTkLabel(dialog, text="Thư mục Đích (Nơi phần mềm tạo các Thư mục phân loại):", font=ctk.CTkFont(family=FONTS["title"], weight="bold", size=13)).pack(pady=(20, 5), padx=20, anchor="w")
        dest_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        dest_frame.pack(fill="x", padx=20)
        dest_entry = ctk.CTkEntry(dest_frame, height=35)
        dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        dest_entry.insert(0, self.config.get("dest_root", ""))
        
        def browse_dest():
            d = filedialog.askdirectory()
            if d:
                dest_entry.delete(0, tk.END)
                dest_entry.insert(0, d)
        ctk.CTkButton(dest_frame, text="Chọn", width=60, height=35, command=browse_dest).pack(side="right")
        
        # Update URL
        ctk.CTkLabel(dialog, text="Đường dẫn kiểm tra cập nhật (URL file version.json):", font=ctk.CTkFont(family=FONTS["title"], weight="bold", size=13)).pack(pady=(20, 5), padx=20, anchor="w")
        update_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        update_frame.pack(fill="x", padx=20)
        update_entry = ctk.CTkEntry(update_frame, height=35)
        update_entry.pack(side="left", fill="x", expand=True)
        update_entry.insert(0, self.config.get("update_url", ""))
        
        def save():
            self.config["source_dir"] = src_entry.get().strip()
            self.config["dest_root"] = dest_entry.get().strip()
            self.config["update_url"] = update_entry.get().strip()
            if not self.config.get("categories"):
                self.config["categories"] = ["Nhạc Nền", "Hiệu Ứng Âm Thanh", "Meme"] # Defaults for new users
            self.save_config()
            dialog.destroy()
            self.update_nav_links()
            self.view_root_folder()
            self.update_status("Đã lưu cài đặt!", "success")
            
        ctk.CTkButton(dialog, text="Lưu Cài Đặt", height=40, font=ctk.CTkFont(family=FONTS["text"], weight="bold"), command=save, fg_color=COLORS["primary"]).pack(pady=30)

    def update_nav_links(self):
        for widget in self.nav_frame.winfo_children():
            widget.destroy()
        
        self.nav_buttons = {}
        for cat in self.config.get('categories', []):
            btn = ctk.CTkButton(
                self.nav_frame, 
                text=f"📁 {cat}", 
                fg_color="transparent",
                text_color=COLORS["text_main"], # Brighter for main interaction
                hover_color=COLORS["primary"],
                height=40, # Taller for easier dropping
                anchor="w",
                font=ctk.CTkFont(family=FONTS["text"], size=13, weight="bold"),
                command=lambda k=cat: self.view_category_folder(k)
            )
            btn.pack(fill="x", padx=5, pady=2)
            btn.bind("<Button-3>", lambda e, c=cat: self.show_cat_menu(e, c))
            self.nav_buttons[cat] = btn

    def view_root_folder(self):
        self.current_source_path = self.config.get('source_dir')
        self.current_folder_name = "THƯ MỤC GỐC"
        self.file_list_label.configure(text=self.current_folder_name)
        self.refresh_file_list()

    def view_category_folder(self, category):
        self.current_source_path = os.path.join(self.config.get('dest_root'), category)
        self.current_folder_name = f"THƯ MỤC: {category.upper()}"
        self.file_list_label.configure(text=self.current_folder_name)
        if not os.path.exists(self.current_source_path):
            os.makedirs(self.current_source_path)
        self.refresh_file_list()

    def show_cat_menu(self, event, category):
        self.selected_cat_to_action = category
        
        # Adjust for DPI Scaling
        scaling = self._get_window_scaling()
        x = (self.winfo_pointerx() - self.winfo_rootx()) / scaling
        y = (self.winfo_pointery() - self.winfo_rooty()) / scaling
        
        self.action_popup.place(x=x-5, y=y-5)
        self.action_popup.lift()

    def check_hide_popup(self, event):
        if hasattr(self, 'action_popup') and self.action_popup.winfo_ismapped():
            x, y = event.x_root, event.y_root
            px = self.action_popup.winfo_rootx()
            py = self.action_popup.winfo_rooty()
            pw = self.action_popup.winfo_width()
            ph = self.action_popup.winfo_height()
            
            # If click is outside the popup, hide it
            if not (px <= x <= px+pw and py <= y <= py+ph):
                self.hide_action_popup()

    def hide_action_popup(self, event=None):
        if hasattr(self, 'action_popup'):
            self.action_popup.place_forget()

    def add_category_event(self):
        new_cat = self.new_cat_entry.get().strip()
        if new_cat and new_cat not in self.config['categories']:
            self.config['categories'].insert(0, new_cat)
            self.save_config()
            self.update_nav_links()
            self.new_cat_entry.delete(0, tk.END)
            self.update_status(f"Đã thêm: {new_cat}", "success")

    def delete_category_event(self):
        self.hide_action_popup()
        if self.selected_cat_to_action and messagebox.askyesno("Xác nhận", f"Xóa '{self.selected_cat_to_action}'?"):
            self.config['categories'].remove(self.selected_cat_to_action)
            self.save_config()
            self.update_nav_links()
            self.update_status(f"Đã xóa: {self.selected_cat_to_action}")

    def rename_category_event(self):
        self.hide_action_popup()
        if not self.selected_cat_to_action: return
        old_name = self.selected_cat_to_action
        dialog = ctk.CTkInputDialog(text=f"Tên mới cho '{old_name}':", title="Đổi tên")
        new_name = dialog.get_input()
        
        if new_name and new_name.strip() and new_name != old_name:
            new_name = new_name.strip()
            # Disk logic
            old_dir = os.path.join(self.config['dest_root'], old_name)
            new_dir = os.path.join(self.config['dest_root'], new_name)
            if os.path.exists(old_dir):
                try:
                    if os.path.exists(new_dir):
                        for item in os.listdir(old_dir):
                            shutil.move(os.path.join(old_dir, item), os.path.join(new_dir, item))
                        os.rmdir(old_dir)
                    else:
                        os.rename(old_dir, new_dir)
                except Exception as e:
                    messagebox.showwarning("Lỗi", str(e))

            idx = self.config['categories'].index(old_name)
            self.config['categories'][idx] = new_name
            self.save_config()
            self.update_nav_links()
            self.update_status(f"Đã đổi tên: {new_name}", "success")

    def refresh_file_list(self):
        source = self.current_source_path
        if not source or not os.path.exists(source):
            self.update_status(f"Lỗi: Không tìm thấy thư mục", "error")
            return
        
        is_root = (source == self.config.get('source_dir'))
        
        # If root is already loaded, just switch view
        if is_root and self.root_loaded:
            self.show_root_view()
            return

        extensions = ('.mp3', '.wav', '.m4a', '.flac', '.mp4', '.mov', '.aac', '.mkv')
        try:
            self.all_files = sorted([f for f in os.listdir(source) if os.path.isfile(os.path.join(source, f)) and f.lower().endswith(extensions)])
            
            if is_root:
                self.create_widgets_for_frame(self.root_scroll, self.root_widgets)
                self.root_loaded = True
                self.show_root_view()
            else:
                self.create_widgets_for_frame(self.sub_scroll, self.sub_widgets)
                self.show_sub_view()
                
            self.stats_label.configure(text=f"{len(self.all_files)} Files in {self.current_folder_name}")
            self.update_status(f"Đã tải {len(self.all_files)} file.", "success")
        except Exception as e:
            self.update_status(f"Lỗi đọc file: {str(e)}", "error")

    def show_root_view(self):
        self.sub_scroll.pack_forget()
        self.root_scroll.pack(fill="both", expand=True)
        self.song_widgets = self.root_widgets
        self.filter_files()

    def show_sub_view(self):
        self.root_scroll.pack_forget()
        self.sub_scroll.pack(fill="both", expand=True)
        self.song_widgets = self.sub_widgets
        self.filter_files()

    def create_widgets_for_frame(self, scroll_frame, widget_dict):
        # TỐI ƯU HÓA: Sử dụng Widget Pool (Tái sử dụng thay vì phá hủy/tạo mới)
        if not hasattr(self, '_widget_pools'):
            self._widget_pools = {}
            
        pool_id = id(scroll_frame)
        if pool_id not in self._widget_pools:
            self._widget_pools[pool_id] = []
            
        pool = self._widget_pools[pool_id]
        widget_dict.clear()
        
        # Ẩn tất cả widget đang có trong pool
        for bar, name_label, bullet in pool:
            bar.pack_forget()
            
        # Tạo thêm widget nếu pool chưa đủ số lượng
        while len(pool) < len(self.all_files):
            song_bar = ctk.CTkFrame(scroll_frame, fg_color="transparent", height=45, corner_radius=8)
            bullet = ctk.CTkLabel(song_bar, text="•", font=ctk.CTkFont(family=FONTS["text"], size=18, weight="bold"), text_color=COLORS["primary"])
            bullet.pack(side="left", padx=(15, 10))
            name_label = ctk.CTkLabel(song_bar, text="", font=ctk.CTkFont(family=FONTS["title"], size=14, weight="bold"), anchor="w", justify="left")
            name_label.pack(side="left", fill="x", expand=True, padx=(0, 20))
            
            # Gán sự kiện (chỉ thực hiện 1 lần lúc khởi tạo widget để tránh tràn bộ nhớ)
            def make_click_handler():
                return lambda e, w=song_bar: self.on_song_click(e, getattr(w, '_current_filename', ''))
            
            def make_drag_handler():
                return lambda e, w=song_bar: self.on_song_drag(e, getattr(w, '_current_filename', ''))
                
            def make_dbl_handler():
                return lambda e, w=song_bar: self.play_music(os.path.join(self.current_source_path, getattr(w, '_current_filename', '')))

            for w in [song_bar, name_label, bullet]:
                w.bind("<Button-1>", make_click_handler(), add="+")
                w.bind("<B1-Motion>", make_drag_handler(), add="+")
                w.bind("<ButtonRelease-1>", self.on_song_release, add="+")
                w.bind("<Double-Button-1>", make_dbl_handler(), add="+")
                
            pool.append((song_bar, name_label, bullet))
            
        # Cập nhật dữ liệu cho các widget đang được sử dụng
        for i, f in enumerate(self.all_files):
            song_bar, name_label, bullet = pool[i]
            
            # Lưu tên file vào widget để các sự kiện có thể truy xuất
            song_bar._current_filename = f
            name_label.configure(text=f, text_color=COLORS["text_main"])
            
            # Đảm bảo visual state được reset nếu trước đó file bị chọn
            if f in getattr(self, 'selected_files', set()):
                song_bar.configure(fg_color=COLORS["primary"])
                name_label.configure(text_color="white")
            else:
                song_bar.configure(fg_color="transparent")
                
            widget_dict[f] = (song_bar, name_label)

    def filter_files(self, event=None):
        query = self.search_entry.get().lower()
        self.filtered_files = []
        
        for f, (bar, label) in self.song_widgets.items():
            if query in f.lower():
                bar.pack(fill="x", padx=10, pady=2)
                self.filtered_files.append(f)
            else:
                bar.pack_forget()

    def clear_selection(self):
        for f in list(self.selected_files):
            if f in self.song_widgets:
                self.song_widgets[f][0].configure(fg_color="transparent")
                self.song_widgets[f][1].configure(text_color=COLORS["text_main"])
        self.selected_files.clear()

    def select_file_visuals(self, filename, add=False):
        if not add:
            self.clear_selection()
        self.selected_files.add(filename)
        if filename in self.song_widgets:
            self.song_widgets[filename][0].configure(fg_color=COLORS["primary"])
            self.song_widgets[filename][1].configure(text_color="white")

    def on_song_click(self, event, filename):
        ctrl_pressed = (event.state & 0x0004) or (event.state & 0x20000) # Control or Command
        shift_pressed = (event.state & 0x0001) # Shift
        
        # Focus to window so arrow keys work
        self.focus_set()
        
        if shift_pressed and hasattr(self, 'last_clicked_filename') and self.last_clicked_filename in self.all_files:
            try:
                start_idx = self.all_files.index(self.last_clicked_filename)
                end_idx = self.all_files.index(filename)
                if not ctrl_pressed:
                    self.clear_selection()
                step = 1 if start_idx <= end_idx else -1
                for i in range(start_idx, end_idx + step, step):
                    self.select_file_visuals(self.all_files[i], add=True)
            except ValueError:
                self.select_file_visuals(filename)
                self.last_clicked_filename = filename
        elif ctrl_pressed:
            self.last_clicked_filename = filename
            if filename in self.selected_files:
                self.selected_files.remove(filename)
                if filename in self.song_widgets:
                    self.song_widgets[filename][0].configure(fg_color="transparent")
                    self.song_widgets[filename][1].configure(text_color=COLORS["text_main"])
            else:
                self.select_file_visuals(filename, add=True)
        else:
            self.last_clicked_filename = filename
            self.select_file_visuals(filename)
            self.play_music(os.path.join(self.current_source_path, filename))

        # Store start position for potential drag
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.is_dragging = False

    def on_song_release(self, event):
        self.configure(cursor="")
        self.is_dragging = False

    def on_key_up(self, event):
        if not self.all_files: return
        if isinstance(self.focus_get(), (ctk.CTkEntry, tk.Entry)): return
        
        idx = -1
        if hasattr(self, 'last_clicked_filename') and self.last_clicked_filename in self.all_files:
            idx = self.all_files.index(self.last_clicked_filename)
        elif self.selected_files:
            # Get the first selected file's index
            idx = self.all_files.index(list(self.selected_files)[0])
            
        new_idx = max(0, idx - 1)
        filename = self.all_files[new_idx]
        self.last_clicked_filename = filename
        
        shift_pressed = (event.state & 0x0001)
        if shift_pressed and idx != -1:
            self.select_file_visuals(filename, add=True)
        else:
            self.select_file_visuals(filename)
            
        # Optional: Auto-scroll to ensure visibility could be added here

    def on_key_down(self, event):
        if not self.all_files: return
        if isinstance(self.focus_get(), (ctk.CTkEntry, tk.Entry)): return
        
        idx = -1
        if hasattr(self, 'last_clicked_filename') and self.last_clicked_filename in self.all_files:
            idx = self.all_files.index(self.last_clicked_filename)
        elif self.selected_files:
            idx = self.all_files.index(list(self.selected_files)[-1])
            
        new_idx = min(len(self.all_files) - 1, idx + 1)
        filename = self.all_files[new_idx]
        self.last_clicked_filename = filename
        
        shift_pressed = (event.state & 0x0001)
        if shift_pressed and idx != -1:
            self.select_file_visuals(filename, add=True)
        else:
            self.select_file_visuals(filename)

    def on_key_enter(self, event):
        if isinstance(self.focus_get(), (ctk.CTkEntry, tk.Entry)): return
        if self.selected_files:
            # Play the last clicked one or the first selected one
            target = getattr(self, 'last_clicked_filename', list(self.selected_files)[0])
            if target in self.selected_files:
                self.play_music(os.path.join(self.current_source_path, target))

    def on_song_drag(self, event, filename):
        if self.is_dragging:
            return

        # Check threshold (Lowered to 5 for better feel)
        dx = abs(event.x_root - self.drag_start_x)
        dy = abs(event.y_root - self.drag_start_y)
        
        if dx > 5 or dy > 5:
            self.is_dragging = True
            # Visual feedback
            self.configure(cursor="fleur") # Change cursor to indicate moving
            
            # Prepare file list
            files_to_drag = []
            if filename in self.selected_files:
                files_to_drag = [os.path.join(self.current_source_path, f) for f in self.selected_files]
            else:
                files_to_drag = [os.path.join(self.current_source_path, filename)]
            
            # Start OLE Drag on the main thread
            self.update_status(f"Đang kéo {len(files_to_drag)} file...", "info")
            try:
                # Pass a feedback callback to handle hover effects during drag
                res = drag_source.start_drag(files_to_drag, feedback_cb=self.on_drag_feedback)
                # Check for internal drop if it wasn't handled externally
                if res in (0, 0x00040101): # DROPEFFECT_NONE or DRAGDROP_S_CANCEL
                    self.check_internal_drop(files_to_drag)
            except Exception as e:
                print(f"DEBUG: Drag error: {e}")
            finally:
                self.is_dragging = False
                self.reset_nav_highlights()
                self.configure(cursor="") # Restore cursor

    def on_drag_feedback(self):
        import win32api
        x, y = win32api.GetCursorPos()
        
        changed = False
        for cat, btn in self.nav_buttons.items():
            bx = btn.winfo_rootx()
            by = btn.winfo_rooty()
            bw = btn.winfo_width()
            bh = btn.winfo_height()
            
            is_hovered = (bx <= x <= bx + bw and by <= y <= by + bh)
            current_state = getattr(btn, "_is_drag_hovered", False)
            
            if is_hovered != current_state:
                btn._is_drag_hovered = is_hovered
                if is_hovered:
                    btn.configure(fg_color=COLORS["primary"], text_color="white")
                else:
                    btn.configure(fg_color="transparent", text_color=COLORS["text_main"])
                changed = True
        
        # Only force-update UI if a state actually changed
        if changed:
            self.update_idletasks()

    def reset_nav_highlights(self):
        for btn in self.nav_buttons.values():
            btn.configure(fg_color="transparent", text_color=COLORS["text_main"])

    def check_internal_drop(self, files_to_drag):
        import win32api
        x, y = win32api.GetCursorPos()
        scaling = self._get_window_scaling()
        
        for cat, btn in self.nav_buttons.items():
            bx = btn.winfo_rootx()
            by = btn.winfo_rooty()
            bw = btn.winfo_width()
            bh = btn.winfo_height()
            
            if bx <= x <= bx + bw and by <= y <= by + bh:
                # Select these files explicitly to move them
                self.selected_files = set([os.path.basename(f) for f in files_to_drag])
                self.move_files_event(cat)
                return

    def toggle_play_hotkey(self):
        if self.selected_files:
            filename = list(self.selected_files)[0]
            filepath = os.path.join(self.current_source_path, filename)
            if self.is_playing and self.current_playing == filepath:
                self.stop_music()
            else:
                self.play_music(filepath)

    def move_files_event(self, category):
        if not self.selected_files:
            self.update_status("Chưa chọn file nào để phân loại!", "warning")
            return
        
        # CRITICAL: Stop music to unlock files on Windows
        self.stop_music()
        
        count = 0
        files_to_move = list(self.selected_files)
        for f in files_to_move:
            if self.move_single_file(f, category): 
                count += 1
                if f in self.all_files: self.all_files.remove(f)
                # Immediate visual removal (No full refresh)
                if f in self.song_widgets:
                    self.song_widgets[f][0].destroy()
                    del self.song_widgets[f]
        
        self.selected_files.clear()
        
        if count:
            self.update_status(f"Đã di chuyển {count} file vào '{category}'", "success")

    def delete_selected_files_event(self):
        if not hasattr(self, 'selected_files') or not self.selected_files:
            return
            
        # Prevent deletion if the user is typing in a text box
        focused = self.focus_get()
        if isinstance(focused, (ctk.CTkEntry, tk.Entry)):
            return

        count = len(self.selected_files)
        confirm = messagebox.askyesno("Xác nhận xóa", f"Chuyển {count} file nhạc này vào Thùng rác (Recycle Bin)?\n\nBạn có thể khôi phục lại từ thùng rác sau này.", icon="warning")
        if confirm:
            self.stop_music() # Stop in case it's currently playing
            deleted_count = 0
            
            # Windows API to send to recycle bin
            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_SILENT = 0x0004
            
            class SHFILEOPSTRUCTW(ctypes.Structure):
                from ctypes import wintypes
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.WORD),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR)
                ]

            for filename in list(self.selected_files):
                filepath = os.path.join(self.current_source_path, filename)
                try:
                    # pFrom must be double-null terminated
                    pFrom = filepath + '\0\0'
                    shfos = SHFILEOPSTRUCTW()
                    shfos.hwnd = None
                    shfos.wFunc = FO_DELETE
                    shfos.pFrom = pFrom
                    shfos.pTo = None
                    shfos.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
                    
                    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(shfos))
                    if result == 0:
                        deleted_count += 1
                        if filename in self.all_files: self.all_files.remove(filename)
                        if filename in self.song_widgets:
                            self.song_widgets[filename][0].pack_forget() # Hide visually
                except Exception as e:
                    print(f"Lỗi xóa file {filename}: {e}")
                    
            self.selected_files.clear()
            self.update_status(f"Đã chuyển {deleted_count} file vào Thùng rác.", "success")
            # Don't trigger full refresh to save performance, just hide the UI elements (done above)
            self.stats_label.configure(text=f"{len(self.all_files)} Files in {self.current_folder_name}")

    def move_single_file(self, filename, category):
        src = os.path.join(self.current_source_path, filename)
        dest_dir = os.path.join(self.config['dest_root'], category)
        if not os.path.exists(dest_dir): os.makedirs(dest_dir)
        
        dest = os.path.join(dest_dir, filename)
        if os.path.exists(dest):
            base, ext = os.path.splitext(filename)
            dest = os.path.join(dest_dir, f"{base}_{datetime.now().strftime('%H%M%S')}{ext}")
            
        try:
            shutil.move(src, dest)
            return True
        except: return False

    def update_status(self, text, type="info"):
        self.status_bar.configure(text=text)
        color = COLORS["text_muted"]
        if type == "success": color = COLORS["success"]
        elif type == "error": color = "#EF4444"
        elif type == "warning": color = COLORS["warning"]
        self.status_bar.configure(text_color=color)

    def on_song_select(self, event):
        selection = self.file_listbox.curselection()
        if selection:
            filename = self.file_listbox.get(selection[0])
            self.now_playing_label.configure(text=f"Ready: {filename}")
            self.draw_waveform()

    def on_wave_click(self, event):
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.is_dragging = False
        self.seek_music(event)

    def on_wave_drag(self, event):
        if self.is_dragging:
            return
            
        dx = abs(event.x_root - self.drag_start_x)
        dy = abs(event.y_root - self.drag_start_y)
        
        if (dx > 15 or dy > 15) and self.current_playing:
            self.is_dragging = True
            self.configure(cursor="fleur")
            self.update_status(f"Đang kéo file đang phát...", "info")
            try:
                drag_source.start_drag([self.current_playing])
            finally:
                self.is_dragging = False
                self.configure(cursor="")
        else:
            # Continue seeking if not dragging yet
            self.seek_music(event)

    def draw_waveform(self):
        self.wave_canvas.delete("all")
        w = self.wave_canvas.winfo_width()
        h = self.wave_canvas.winfo_height()
        if w < 10: w = 400
        
        import random
        for i in range(0, w, 4):
            bar_h = random.randint(10, h-10)
            self.wave_canvas.create_rectangle(i, (h-bar_h)//2, i+2, (h+bar_h)//2, fill=COLORS["primary"], outline="")

    def toggle_play(self):
        if self.selected_files:
            filename = list(self.selected_files)[0]
            filepath = os.path.join(self.current_source_path, filename)
            
            if self.is_playing and self.current_playing == filepath:
                self.stop_music()
            else:
                self.play_music(filepath)

    def play_music(self, path):
        if not self.vlc_available:
            self.update_status("Vui lòng cài VLC để nghe thử nhạc", "warning")
            return

        self.stop_music()
        media = self.vlc_instance.media_new(path)
        self.player.set_media(media)
        self.player.play()
        
        self.current_playing = path
        self.is_playing = True
        self.play_btn.configure(text="⏸ PAUSE")
        filename = os.path.basename(path)
        self.now_playing_label.configure(text=f"Playing: {filename}", text_color=COLORS["primary"])
        
        self.draw_waveform() # Restore the cinematic waveform!
        
        # Start checking for length (VLC needs a moment to load)
        self.after(200, self.get_vlc_length)
        self.update_playhead()

    def get_vlc_length(self):
        length = self.player.get_length()
        if length > 0:
            self.song_length_ms = length
        else:
            self.after(200, self.get_vlc_length)

    def seek_music(self, event):
        if not self.is_playing or self.song_length_ms == 0: return
        
        w = self.wave_canvas.winfo_width()
        if w == 0: return
        
        percent = event.x / w
        self.player.set_position(percent) # VLC uses 0.0 to 1.0
        self.draw_playhead(event.x)

    def update_playhead(self):
        if self.is_playing:
            curr_pos = self.player.get_position() # Returns 0.0 to 1.0
            if curr_pos >= 0:
                w = self.wave_canvas.winfo_width()
                x = curr_pos * w
                self.draw_playhead(x)
                
                # Check if ended
                if curr_pos >= 0.999:
                    self.stop_music()
            
            self.after(100, self.update_playhead)

    def draw_playhead(self, x):
        self.wave_canvas.delete("playhead")
        h = self.wave_canvas.winfo_height()
        self.wave_canvas.create_line(x, 0, x, h, fill="#ffffff", width=2, tags="playhead")

    def stop_music(self):
        if self.vlc_available and self.player:
            self.player.stop()
        self.is_playing = False
        self.play_btn.configure(text="▶ PLAY")
        self.wave_canvas.delete("playhead")
        if self.current_playing:
            filename = os.path.basename(self.current_playing)
            self.now_playing_label.configure(text=f"Stopped: {filename}", text_color=COLORS["text_muted"])

    def on_closing(self):
        self.stop_music()
        if self.vlc_available:
            if self.player: self.player.release()
            if self.vlc_instance: self.vlc_instance.release()
        self.destroy()

    def change_appearance_mode_event(self, mode):
        ctk.set_appearance_mode(mode)

    def check_for_updates(self):
        update_url = self.config.get('update_url')
        if not update_url:
            return
            
        def update_thread():
            try:
                response = requests.get(update_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    remote_version = data.get("version")
                    # Simple version comparison
                    def parse_version(v): return tuple(map(int, (v.split("."))))
                    
                    if remote_version and parse_version(remote_version) > parse_version(CURRENT_VERSION):
                        self.after(0, lambda: self.prompt_update(data))
            except Exception as e:
                print(f"Lỗi kiểm tra cập nhật: {e}")
                
        threading.Thread(target=update_thread, daemon=True).start()

    def prompt_update(self, update_data):
        remote_version = update_data.get("version")
        changelog = update_data.get("changelog", "Không có chi tiết.")
        
        msg = f"Phiên bản mới {remote_version} đã sẵn sàng!\n\nChi tiết:\n{changelog}\n\nBạn có muốn cập nhật phần mềm không?"
        
        # Use simple tk messagebox
        if messagebox.askyesno("Cập nhật phần mềm", msg):
            self.perform_update(update_data)

    def perform_update(self, update_data):
        files_to_update = update_data.get("files", {})
        if not files_to_update:
            return
            
        self.update_status("Đang tải bản cập nhật...", "info")
        
        def download_and_apply():
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                temp_dir = os.path.join(script_dir, ".update_tmp")
                os.makedirs(temp_dir, exist_ok=True)
                
                # Download files
                for filename, url in files_to_update.items():
                    res = requests.get(url, timeout=15)
                    if res.status_code == 200:
                        temp_path = os.path.join(temp_dir, filename)
                        with open(temp_path, "wb") as f:
                            f.write(res.content)
                            
                # Create batch file to replace and restart
                bat_path = os.path.join(script_dir, "apply_update.bat")
                
                # Wait 2 seconds for app to close, then copy
                bat_content = f'''@echo off
timeout /t 2 /nobreak > NUL
xcopy /Y /E "{temp_dir}\\*" "{script_dir}\\"
rmdir /S /Q "{temp_dir}"
start "" /B "{sys.executable}" "{os.path.join(script_dir, 'music_organizer.py')}"
del "%~f0"
'''
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(bat_content)
                    
                # Run batch file and exit
                self.after(0, lambda: self.update_status("Đang khởi động lại để cập nhật...", "success"))
                time.sleep(1)
                
                subprocess.Popen(bat_path, shell=True, cwd=script_dir)
                os._exit(0) # Force immediate exit to release files
                
            except Exception as e:
                self.after(0, lambda: self.update_status(f"Lỗi tải cập nhật: {e}", "error"))
                print(f"Lỗi tải cập nhật: {e}")
                
        threading.Thread(target=download_and_apply, daemon=True).start()

if __name__ == "__main__":
    app = MusicOrganizerApp()
    app.mainloop()
