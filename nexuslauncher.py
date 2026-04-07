import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import json, os, subprocess, threading, time, psutil, datetime, re
import requests
from PIL import Image, ImageTk
from io import BytesIO

DATA_FILE = "nexus_data.json"

THEMES = {
    "Dark": {"bg": "#0B0B0B", "fg": "white", "panel": "#121212", "border": "#222"},
    "Light": {"bg": "#F0F0F0", "fg": "#111", "panel": "#E0E0E0", "border": "#CCC"},
    "Glass": {"bg": "#0D1117", "fg": "#C9D1D9", "panel": "#161B22", "border": "#30363D"},
    "Metal": {"bg": "#2B2B2B", "fg": "#E0E0E0", "panel": "#333333", "border": "#555"}
}

class NexusLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Nexus V2.0 - Design & Performance")
        self.root.geometry("1100x780")
        
        self.load_data()
        self.apply_theme_vars()
        self.root.configure(bg=self.theme["bg"])
        
        self.ram_hist, self.cpu_hist = [0]*30, [0]*30
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.show_library())

        self.create_ui()
        self.start_monitors()

    def load_data(self):
        defaults = {
            "games": [], 
            "theme_color": "#00ffff", 
            "settings": {"theme": "Dark", "view": "grid"},
            "arsenal": {
                "clean_temp": False, "kill_telemetry": False, 
                "stop_services": False, "low_priority_sys": False,
                "kill_explorer": False, "disable_defender": False
            }
        }
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f: self.data = json.load(f)
                for k, v in defaults.items():
                    if k not in self.data: self.data[k] = v
            except: self.data = defaults
        else:
            self.data = defaults

    def save_data(self):
        with open(DATA_FILE, "w") as f: json.dump(self.data, f, indent=4)

    def apply_theme_vars(self):
        t_name = self.data["settings"].get("theme", "Dark")
        self.theme = THEMES.get(t_name, THEMES["Dark"])
        self.accent = self.data.get("theme_color", "#00ffff")

    def create_ui(self):
        # SIDEBAR
        self.sidebar = tk.Frame(self.root, bg=self.theme["panel"], width=230, highlightthickness=1, highlightbackground=self.theme["border"])
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.lbl_clock = tk.Label(self.sidebar, text="00:00", fg=self.theme["fg"], bg=self.theme["panel"], font=("Consolas", 26, "bold"))
        self.lbl_clock.pack(pady=(25, 20))

        for txt, cmd in [("🎮 BIBLIOTECA", self.show_library), ("⚙️ CONFIGURAÇÕES", self.show_settings)]:
            btn = tk.Button(self.sidebar, text=txt, command=cmd, bg=self.theme["panel"], fg=self.theme["fg"], bd=0, font=("Segoe UI", 10, "bold"), pady=15, anchor="w", padx=25)
            btn.pack(fill="x")
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.theme["border"], fg=self.accent))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.theme["panel"], fg=self.theme["fg"]))

        self.perf_f = tk.Frame(self.sidebar, bg=self.theme["panel"], pady=20)
        self.perf_f.pack(side="bottom", fill="x", padx=20)
        self.cpu_canv = tk.Canvas(self.perf_f, height=40, bg=self.theme["bg"], highlightthickness=0)
        self.cpu_canv.pack(fill="x", pady=(0, 10))
        self.ram_canv = tk.Canvas(self.perf_f, height=40, bg=self.theme["bg"], highlightthickness=0)
        self.ram_canv.pack(fill="x")

        # ÁREA CENTRAL
        self.main_area = tk.Frame(self.root, bg=self.theme["bg"])
        self.main_area.pack(side="right", fill="both", expand=True)

        self.top_bar = tk.Frame(self.main_area, bg=self.theme["bg"], padx=25, pady=15)
        self.top_bar.pack(fill="x")
        self.search_ent = tk.Entry(self.top_bar, textvariable=self.search_var, bg=self.theme["panel"], fg=self.theme["fg"], insertbackground=self.accent, bd=0, font=("Segoe UI", 11))
        self.search_ent.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 15))
        tk.Button(self.top_bar, text="+ NOVO JOGO", bg=self.accent, fg="black", bd=0, font=("Segoe UI", 9, "bold"), padx=20, command=self.add_game_window).pack(side="right")

        self.lib_container = tk.Frame(self.main_area, bg=self.theme["bg"])
        self.lib_container.pack(fill="both", expand=True, padx=10)
        self.canvas = tk.Canvas(self.lib_container, bg=self.theme["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.lib_container, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=self.theme["bg"])
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self.show_library()

    # --- 🎮 BIBLIOTECA ---
    def show_library(self):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        query = self.search_var.get().lower()
        games = [g for g in self.data["games"] if query in g["name"].lower()]

        for i, game in enumerate(games):
            card = tk.Frame(self.scroll_frame, bg=self.theme["panel"], width=200, height=260, highlightthickness=1, highlightbackground=self.theme["border"])
            card.grid(row=i//4, column=i%4, padx=15, pady=15)
            card.pack_propagate(False)

            photo = None
            if game.get("icon") and os.path.exists(game["icon"]):
                try:
                    resample = getattr(Image, 'LANCZOS', getattr(Image, 'ANTIALIAS', 1))
                    photo = ImageTk.PhotoImage(Image.open(game["icon"]).resize((200, 150), resample))
                except: pass
            
            lbl_img = tk.Label(card, image=photo, bg="#000", height=150)
            lbl_img.image = photo; lbl_img.pack(fill="x")
            lbl_img.bind("<Button-3>", lambda e, g=game: self.context_menu(e, g))

            tk.Label(card, text=game["name"].upper(), fg=self.theme["fg"], bg=self.theme["panel"], font=("Segoe UI", 9, "bold")).pack(pady=10)
            tk.Button(card, text="EXECUTAR", bg=self.theme["border"], fg=self.accent, bd=0, font=("Segoe UI", 8, "bold"), command=lambda g=game: self.launch(g)).pack(side="bottom", fill="x", padx=10, pady=10)

    # --- ⚙️ CONFIGURAÇÕES (INCLUI ARSENAL) ---
    def show_settings(self):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        
        # Seção Arsenal
        tk.Label(self.scroll_frame, text="🚀 ARSENAL TÁTICO", fg=self.accent, bg=self.theme["bg"], font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(20, 10), padx=20)
        ars_f = tk.Frame(self.scroll_frame, bg=self.theme["panel"], padx=20, pady=10, highlightthickness=1, highlightbackground=self.theme["border"])
        ars_f.pack(fill="x", padx=20, pady=10)

        options = [
            ("Limpeza de Temporários", "clean_temp"), ("Matar Telemetria", "kill_telemetry"),
            ("Parar Serviços (Win 7)", "stop_services"), ("Prioridade Inversa", "low_priority_sys"),
            ("Suspender Explorer", "kill_explorer"), ("Desligar Defender", "disable_defender")
        ]

        for i, (txt, key) in enumerate(options):
            var = tk.BooleanVar(value=self.data["arsenal"].get(key, False))
            c = tk.Checkbutton(ars_f, text=txt, variable=var, bg=self.theme["panel"], fg=self.theme["fg"], 
                               selectcolor="#333", activebackground=self.theme["panel"], activeforeground=self.accent,
                               command=lambda k=key, v=var: (self.data["arsenal"].update({k: v.get()}), self.save_data()))
            c.grid(row=i//2, column=i%2, sticky="w", padx=20, pady=8)

        # Seção Visual
        tk.Label(self.scroll_frame, text="🎨 CUSTOMIZAÇÃO", fg=self.accent, bg=self.theme["bg"], font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(30, 10), padx=20)
        vis_f = tk.Frame(self.scroll_frame, bg=self.theme["panel"], padx=20, pady=20, highlightthickness=1, highlightbackground=self.theme["border"])
        vis_f.pack(fill="x", padx=20)
        
        tk.Label(vis_f, text="TEMAS:", fg=self.theme["fg"], bg=self.theme["panel"], font=("Segoe UI", 10, "bold")).pack(side="left")
        for t in THEMES.keys():
            tk.Button(vis_f, text=t.upper(), bg=self.theme["border"], fg=self.theme["fg"], bd=0, padx=15, command=lambda n=t: self.set_theme(n)).pack(side="left", padx=5)
        
        tk.Button(self.scroll_frame, text="MUDAR COR DE ACENTO", bg=self.accent, fg="black", bd=0, padx=25, pady=12, font=("Segoe UI", 9, "bold"), command=self.set_color).pack(pady=20, padx=20, anchor="w")

    # --- 📦 JANELA NOVO JOGO ---
    def add_game_window(self):
        win = tk.Toplevel(self.root); win.title("Registrar Jogo"); win.geometry("450x450"); win.configure(bg=self.theme["bg"]); win.transient(self.root); win.grab_set()
        
        fields = {}
        for label, key in [("NOME DO JOGO:", "name"), ("CAMINHO (.EXE):", "path"), ("ÍCONE (OPCIONAL):", "icon")]:
            tk.Label(win, text=label, fg=self.theme["fg"], bg=self.theme["bg"], font=("Segoe UI", 9, "bold")).pack(pady=(15, 5), padx=40, anchor="w")
            f = tk.Frame(win, bg=self.theme["bg"]); f.pack(fill="x", padx=40)
            e = tk.Entry(f, bg=self.theme["panel"], fg=self.theme["fg"], bd=0, font=("Segoe UI", 10)); e.pack(side="left", fill="x", expand=True, ipady=6); fields[key] = e
            if key != "name":
                tk.Button(f, text="...", bg=self.theme["border"], fg=self.theme["fg"], bd=0, padx=10, command=lambda k=key, ent=e: ent.insert(0, filedialog.askopenfilename() or "")).pack(side="right")

        tk.Button(win, text="SALVAR NO NEXUS", bg=self.accent, fg="black", bd=0, pady=12, font=("Segoe UI", 10, "bold"), 
                  command=lambda: (self.data["games"].append({k: v.get() for k, v in fields.items()}), self.save_data(), self.show_library(), win.destroy())).pack(side="bottom", fill="x", padx=40, pady=30)

    # --- 🌐 BUSCA DE CAPA COM GALERIA ---
    def fetch_cover(self, game):
        search_win = tk.Toplevel(self.root); search_win.title("Escolha uma Capa"); search_win.geometry("700x550"); search_win.configure(bg=self.theme["bg"])
        canv = tk.Canvas(search_win, bg=self.theme["bg"], highlightthickness=0); scroll = ttk.Scrollbar(search_win, orient="vertical", command=canv.yview)
        thumb_f = tk.Frame(canv, bg=self.theme["bg"]); canv.create_window((0,0), window=thumb_f, anchor="nw")
        canv.configure(yscrollcommand=scroll.set); canv.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")

        def load_images():
            try:
                query = f"{game['name'].replace(' ', '+')}+game+icon+image"
                r = requests.get(f"https://www.bing.com/images/search?q={query}", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                links = re.findall(r'murl&quot;:&quot;(http.*?)&quot;', r.text)[:12]
                for i, url in enumerate(links):
                    try:
                        res = requests.get(url, timeout=3).content
                        resample = getattr(Image, 'LANCZOS', getattr(Image, 'ANTIALIAS', 1))
                        img = ImageTk.PhotoImage(Image.open(BytesIO(res)).resize((150, 150), resample))
                        btn = tk.Button(thumb_f, image=img, bg=self.theme["panel"], bd=2, relief="flat", command=lambda u=url: self.save_cover(game, u, search_win))
                        btn.image = img; btn.grid(row=i//4, column=i%4, padx=10, pady=10)
                    except: pass
            except: messagebox.showerror("Erro", "Falha na conexão com o servidor de imagens.")
        
        threading.Thread(target=load_images, daemon=True).start()

    def save_cover(self, game, url, win):
        if not os.path.exists("icons"): os.makedirs("icons")
        path = os.path.abspath(f"icons/{game['name'].replace(' ','_')}.png")
        with open(path, "wb") as f: f.write(requests.get(url).content)
        game["icon"] = path; self.save_data(); win.destroy(); self.show_library()

    # --- MOTOR ---
    def launch(self, game):
        def r():
            ars = self.data["arsenal"]
            if ars.get("clean_temp"): os.system('del /q /s /f %temp%\\* >nul 2>&1')
            if ars.get("kill_explorer"): os.system("taskkill /f /im explorer.exe")
            self.root.iconify()
            subprocess.Popen(f'"{game["path"]}"', shell=True).wait()
            if ars.get("kill_explorer"): subprocess.Popen("explorer.exe")
            self.root.deiconify()
        threading.Thread(target=r, daemon=True).start()

    def context_menu(self, event, game):
        m = tk.Menu(self.root, tearoff=0, bg=self.theme["panel"], fg=self.theme["fg"], activebackground=self.accent)
        m.add_command(label="🌐 Buscar Capa Online", command=lambda: self.fetch_cover(game))
        m.add_command(label="❌ Remover", command=lambda: (self.data["games"].remove(game), self.save_data(), self.show_library()))
        m.post(event.x_root, event.y_root)

    def set_theme(self, n): self.data["settings"]["theme"] = n; self.save_data(); self.root.destroy(); main()
    def set_color(self): 
        c = colorchooser.askcolor()[1]
        if c: self.data["theme_color"] = c; self.save_data(); self.root.destroy(); main()

    def start_monitors(self):
        def run():
            while self.root.winfo_exists():
                cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
                self.cpu_hist.pop(0); self.cpu_hist.append(cpu)
                self.ram_hist.pop(0); self.ram_hist.append(ram)
                t = datetime.datetime.now().strftime("%H:%M")
                self.root.after(0, lambda: self.update_monitors(t))
                time.sleep(2)
        threading.Thread(target=run, daemon=True).start()

    def update_monitors(self, t):
        self.lbl_clock.config(text=t)
        for canv, hist, color in [(self.cpu_canv, self.cpu_hist, "#ff4444"), (self.ram_canv, self.ram_hist, self.accent)]:
            canv.delete("all")
            pts = []
            for i, v in enumerate(hist): pts.extend([(i/29)*190, 40 - (v/100)*40])
            if len(pts) >= 4: canv.create_line(pts, fill=color, width=2)

def main():
    root = tk.Tk(); NexusLauncher(root); root.mainloop()

if __name__ == "__main__": main()
