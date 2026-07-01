import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import sys
import os

class PhDCrawlerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PhD Vacancy Crawler Pro")
        self.root.geometry("800x600")
        self.root.configure(padx=20, pady=20)
        
        self.process = None
        self.create_widgets()
        
    def create_widgets(self):
        # Top Frame for controls
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Region Selection
        ttk.Label(control_frame, text="Region:").pack(side=tk.LEFT, padx=(0, 5))
        self.region_var = tk.StringVar(value="all")
        regions = ["all", "europe", "usa", "canada", "australia", "asia", "india"]
        self.region_combo = ttk.Combobox(control_frame, textvariable=self.region_var, values=regions, state="readonly", width=10)
        self.region_combo.pack(side=tk.LEFT, padx=(0, 20))
        
        # Options
        self.quick_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="Quick Run (Test)", variable=self.quick_var).pack(side=tk.LEFT, padx=(0, 10))
        
        self.report_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="Generate HTML Report", variable=self.report_var).pack(side=tk.LEFT, padx=(0, 20))
        
        # Buttons
        self.start_btn = ttk.Button(control_frame, text="Start Crawling", command=self.start_crawling)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_crawling, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        
        # Bottom Frame for Log Output
        log_frame = ttk.LabelFrame(self.root, text="Live Log Output")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_area.config(state=tk.DISABLED)
        
    def log(self, message):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)
        
    def start_crawling(self):
        if self.process and self.process.poll() is None:
            messagebox.showwarning("Running", "Crawler is already running!")
            return
            
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state=tk.DISABLED)
        
        cmd = [sys.executable, "phd_vacancy_finder_pro.py", "--daily"]
        
        if self.region_var.get() != "all":
            cmd.extend(["--region", self.region_var.get()])
        if self.quick_var.get():
            cmd.append("--quick")
        if self.report_var.get():
            cmd.append("--report")
            
        self.log(f"Starting command: {' '.join(cmd)}")
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # Run in thread so GUI doesn't freeze
        threading.Thread(target=self.run_process, args=(cmd,), daemon=True).start()

    def run_process(self, cmd):
        # We need to unbuffer python output to see it in real-time
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
                    self.root.after(0, self.log, line.rstrip())
                    
            self.process.stdout.close()
            return_code = self.process.wait()
            
            if return_code == 0:
                self.root.after(0, self.log, "--- CRAWL COMPLETED SUCCESSFULLY ---")
            else:
                self.root.after(0, self.log, f"--- CRAWL TERMINATED WITH CODE {return_code} ---")
                
        except Exception as e:
            self.root.after(0, self.log, f"Error launching process: {str(e)}")
            
        finally:
            self.root.after(0, self.reset_buttons)
            
    def stop_crawling(self):
        if self.process and self.process.poll() is None:
            self.log("Stopping crawler...")
            self.process.terminate()
            
    def reset_buttons(self):
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = PhDCrawlerGUI(root)
    root.mainloop()
