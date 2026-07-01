import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import sys
import os

ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class PhDCrawlerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PhD Vacancy Crawler Pro")
        self.geometry("850x650")
        
        # Configure grid layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.process = None
        self.create_widgets()

    def create_widgets(self):
        # --- Left Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="PhD Crawler", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Region Selection
        self.region_label = ctk.CTkLabel(self.sidebar_frame, text="Select Region:", anchor="w")
        self.region_label.grid(row=1, column=0, padx=20, pady=(10, 0))
        self.region_var = ctk.StringVar(value="all")
        self.region_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["all", "europe", "usa", "canada", "australia", "asia", "india"],
                                             variable=self.region_var)
        self.region_menu.grid(row=2, column=0, padx=20, pady=(10, 10))

        # Options
        self.quick_var = ctk.BooleanVar(value=False)
        self.quick_check = ctk.CTkCheckBox(self.sidebar_frame, text="Quick Run (Test)", variable=self.quick_var)
        self.quick_check.grid(row=3, column=0, padx=20, pady=(10, 10))

        self.report_var = ctk.BooleanVar(value=True)
        self.report_check = ctk.CTkCheckBox(self.sidebar_frame, text="Generate HTML Report", variable=self.report_var)
        self.report_check.grid(row=4, column=0, padx=20, pady=(10, 10))

        # Appearance Mode
        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=6, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark", "System"],
                                                      command=self.change_appearance_mode_event)
        self.appearance_mode_menu.grid(row=7, column=0, padx=20, pady=(10, 20))
        self.appearance_mode_menu.set("System")

        # --- Main View (Top Controls) ---
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=1, padx=20, pady=20, sticky="ew")

        self.start_btn = ctk.CTkButton(self.top_frame, text="Start Crawling", command=self.start_crawling, font=ctk.CTkFont(weight="bold"))
        self.start_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(self.top_frame, text="Stop", command=self.stop_crawling, fg_color="red", hover_color="#aa0000", state="disabled")
        self.stop_btn.pack(side="left")

        # --- Main View (Terminal/Logs) ---
        self.log_area = ctk.CTkTextbox(self, font=("Consolas", 12), state="disabled")
        self.log_area.grid(row=1, column=1, padx=20, pady=(0, 20), sticky="nsew")

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def log(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", message + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

    def start_crawling(self):
        if self.process and self.process.poll() is None:
            messagebox.showwarning("Running", "Crawler is already running!")
            return

        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")

        cmd = [sys.executable, "phd_vacancy_finder_pro.py", "--daily"]

        if self.region_var.get() != "all":
            cmd.extend(["--region", self.region_var.get()])
        if self.quick_var.get():
            cmd.append("--quick")
        if self.report_var.get():
            cmd.append("--report")

        self.log(f"[SYSTEM] Starting command: {' '.join(cmd)}\n")

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

        # Run in thread so GUI doesn't freeze
        threading.Thread(target=self.run_process, args=(cmd,), daemon=True).start()

    def run_process(self, cmd):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )

            for line in iter(self.process.stdout.readline, ''):
                if line:
                    self.after(0, self.log, line.rstrip())

            self.process.stdout.close()
            return_code = self.process.wait()

            if return_code == 0:
                self.after(0, self.log, "\n[SYSTEM] --- CRAWL COMPLETED SUCCESSFULLY ---")
            else:
                self.after(0, self.log, f"\n[SYSTEM] --- CRAWL TERMINATED WITH CODE {return_code} ---")

        except Exception as e:
            self.after(0, self.log, f"[SYSTEM ERROR] {str(e)}")

        finally:
            self.after(0, self.reset_buttons)

    def stop_crawling(self):
        if self.process and self.process.poll() is None:
            self.log("\n[SYSTEM] Stopping crawler...")
            self.process.terminate()

    def reset_buttons(self):
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")


if __name__ == "__main__":
    app = PhDCrawlerGUI()
    app.mainloop()
