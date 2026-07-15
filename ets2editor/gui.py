"""Graphical interface (Tkinter) for the ETS2/ATS save editor.

Layout inspired by TS-SE Tool: a right-hand "Profiles & Saves" panel with a
profile avatar, big Load/Save buttons and a MAX-ALL "god mode" button, plus a
tabbed editor (Profile, Company, Garages, Trucks, Explorer, Text).
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .save import (
    SaveFile, find_profiles, add_custom_dir, SKILL_MAX, XP_MAX, MONEY_MAX,
)

try:
    import sv_ttk
    _HAVE_SVTTK = True
except ImportError:
    _HAVE_SVTTK = False

ACCENT = "#e0a020"

# Skill (icon, display name, economy field key). Icons are Unicode glyphs so
# no game assets need to be shipped; Windows renders them via Segoe UI Emoji.
SKILLS = [
    ("☢", "ADR (dangerous goods)", "adr"),
    ("\U0001F6E3", "Long Distance", "long_dist"),
    ("\U0001F48E", "High Value Cargo", "heavy"),
    ("\U0001F377", "Fragile Cargo", "fragile"),
    ("⏱", "Just-In-Time Delivery", "urgent"),
    ("\U0001F33F", "Ecodriving", "mechanical"),
]

_AVATAR_COLORS = ["#e0a020", "#4a90d9", "#5cb85c", "#d9534f",
                  "#9b59b6", "#16a085", "#e67e22"]


class SkillBar(tk.Canvas):
    """A segmented, clickable skill-level control (0..maxpts)."""

    def __init__(self, master, maxpts, on_change=None, box=26, gap=4):
        w = maxpts * (box + gap) + gap
        super().__init__(master, width=w, height=box + 6,
                         highlightthickness=0, bg=master["bg"]
                         if "bg" in master.keys() else "#1c1c1c")
        self.maxpts = maxpts
        self.box = box
        self.gap = gap
        self.value = 0
        self.on_change = on_change
        self.bind("<Button-1>", self._click)
        self._draw()

    def _draw(self):
        self.delete("all")
        for i in range(self.maxpts):
            x = self.gap + i * (self.box + self.gap)
            filled = i < self.value
            self.create_rectangle(
                x, 3, x + self.box, 3 + self.box,
                fill=ACCENT if filled else "#3a3a3a",
                outline="#666", width=1)

    def _click(self, event):
        idx = int((event.x - self.gap) // (self.box + self.gap)) + 1
        idx = max(0, min(self.maxpts, idx))
        # clicking the current top box clears it (lets you go down)
        self.set(idx if idx != self.value else idx - 1)
        if self.on_change:
            self.on_change()

    def set(self, value):
        try:
            self.value = max(0, min(self.maxpts, int(value)))
        except (TypeError, ValueError):
            self.value = 0
        self._draw()

    def get(self):
        return self.value


class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ETS2 / ATS Save Editor 2026")
        self.geometry("1060x720")
        self.minsize(960, 660)

        if _HAVE_SVTTK:
            sv_ttk.set_theme("dark")

        self.save = None
        self.profiles = []
        self.game_filter = tk.StringVar(value="Euro Truck Simulator 2")
        self.backup_var = tk.BooleanVar(value=True)
        self.skill_bars = {}
        self._avatar_img = None

        self._init_styles()
        self._build_sidebar()
        self._build_main()
        self._build_statusbar()
        self.refresh_profiles()

    def _init_styles(self):
        st = ttk.Style()
        st.configure("Big.TButton", font=("Segoe UI", 12, "bold"), padding=10)
        st.configure("God.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        st.configure("Card.TLabel", font=("Segoe UI", 10))
        st.configure("H1.TLabel", font=("Segoe UI", 14, "bold"))

    # ================================================================
    # Sidebar
    # ================================================================
    def _build_sidebar(self):
        side = ttk.Frame(self, padding=10, width=300)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)

        game = ttk.Frame(side)
        game.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(game, text="ETS 2", value="Euro Truck Simulator 2",
                        variable=self.game_filter, command=self.refresh_profiles
                        ).pack(side="left", expand=True, fill="x")
        ttk.Radiobutton(game, text="ATS", value="American Truck Simulator",
                        variable=self.game_filter, command=self.refresh_profiles
                        ).pack(side="left", expand=True, fill="x")

        # avatar + name
        head = ttk.Frame(side)
        head.pack(fill="x", pady=4)
        self.avatar = tk.Canvas(head, width=64, height=64,
                                highlightthickness=0, bg="#2a2a2a")
        self.avatar.pack(side="left")
        self.lbl_pname = ttk.Label(head, text="—", style="H1.TLabel")
        self.lbl_pname.pack(side="left", padx=10)

        ttk.Button(side, text="Add Custom Folder...",
                   command=self._add_custom_folder).pack(fill="x", pady=(6, 8))

        grp = ttk.LabelFrame(side, text="Profiles && Saves", padding=8)
        grp.pack(fill="x")
        ttk.Label(grp, text="Profile:").pack(anchor="w")
        self.cb_profile = ttk.Combobox(grp, state="readonly")
        self.cb_profile.pack(fill="x", pady=(0, 6))
        self.cb_profile.bind("<<ComboboxSelected>>", self._on_profile_change)
        ttk.Label(grp, text="Save:").pack(anchor="w")
        self.cb_save = ttk.Combobox(grp, state="readonly")
        self.cb_save.pack(fill="x", pady=(0, 6))
        row = ttk.Frame(grp)
        row.pack(fill="x", pady=2)
        ttk.Button(row, text="Reload", command=self.refresh_profiles).pack(
            side="left", expand=True, fill="x", padx=1)
        ttk.Button(row, text="Open folder", command=self._open_folder).pack(
            side="left", expand=True, fill="x", padx=1)
        ttk.Button(grp, text="Open file manually...",
                   command=self.open_dialog).pack(fill="x", pady=(2, 0))

        # summary card
        self.card = ttk.LabelFrame(side, text="Summary", padding=8)
        self.card.pack(fill="x", pady=8)
        self.lbl_summary = ttk.Label(self.card, text="No save loaded.",
                                     style="Card.TLabel", justify="left")
        self.lbl_summary.pack(anchor="w")

        ttk.Checkbutton(side, text="Make backup before saving",
                        variable=self.backup_var).pack(anchor="w", pady=4)
        ttk.Button(side, text="LOAD", style="Big.TButton",
                   command=self.do_load).pack(fill="x", pady=(6, 4))
        ttk.Button(side, text="SAVE", style="Big.TButton",
                   command=self.do_save).pack(fill="x", pady=4)
        ttk.Separator(side).pack(fill="x", pady=6)
        ttk.Button(side, text="⚡  MAX ALL (God Mode)", style="God.TButton",
                   command=self.god_mode).pack(fill="x")

    def _draw_avatar(self, profile):
        self.avatar.delete("all")
        img_path = profile.get("avatar") if profile else None
        if img_path:
            try:
                self._avatar_img = tk.PhotoImage(file=img_path)
                self.avatar.create_image(32, 32, image=self._avatar_img)
                return
            except Exception:
                pass
        name = (profile.get("name") if profile else "?") or "?"
        color = _AVATAR_COLORS[sum(map(ord, name)) % len(_AVATAR_COLORS)]
        self.avatar.create_oval(4, 4, 60, 60, fill=color, outline="")
        self.avatar.create_text(32, 32, text=name[:1].upper(),
                                fill="white", font=("Segoe UI", 26, "bold"))

    # ================================================================
    # Main notebook
    # ================================================================
    def _build_main(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self._build_profile_tab()
        self._build_company_tab()
        self._build_garages_tab()
        self._build_trucks_tab()
        self._build_explorer_tab()
        self._build_text_tab()

    def _num_row(self, parent, label, var, steps, maxval, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=var, width=18).grid(
            row=row, column=1, sticky="w", padx=8)
        col = 2
        for step in steps:
            ttk.Button(parent, text="+%s" % _short(step), width=7,
                       command=lambda s=step, v=var: self._bump(v, s)).grid(
                row=row, column=col, padx=2)
            col += 1
        ttk.Button(parent, text="MAX", width=6,
                   command=lambda v=var, m=maxval: v.set(str(m))).grid(
            row=row, column=col, padx=(6, 0))

    def _build_profile_tab(self):
        tab = ttk.Frame(self.nb, padding=16)
        self.nb.add(tab, text="\U0001F464  Profile")

        xpf = ttk.LabelFrame(tab, text="Experience", padding=12)
        xpf.pack(fill="x")
        self.var_xp = tk.StringVar()
        self._num_row(xpf, "XP (experience_points):", self.var_xp,
                      (10000, 100000), XP_MAX, 0)

        skf = ttk.LabelFrame(tab, text="Skills  (click the boxes)", padding=12)
        skf.pack(fill="x", pady=14)
        for r, (icon, label, key) in enumerate(SKILLS):
            ttk.Label(skf, text="%s  %s" % (icon, label), width=26).grid(
                row=r, column=0, sticky="w", pady=5)
            bar = SkillBar(skf, SKILL_MAX[key])
            bar.grid(row=r, column=1, sticky="w")
            self.skill_bars[key] = bar
        ttk.Button(skf, text="MAX all skills",
                   command=self._max_skills).grid(
            row=len(SKILLS), column=0, sticky="w", pady=(10, 0))

    def _build_company_tab(self):
        tab = ttk.Frame(self.nb, padding=16)
        self.nb.add(tab, text="\U0001F3E2  Company")
        f = ttk.LabelFrame(tab, text="Bank / Company", padding=12)
        f.pack(fill="x")
        self.var_money = tk.StringVar()
        self._num_row(f, "Money (money_account):", self.var_money,
                      (100000, 1000000), MONEY_MAX, 0)

        ttk.Label(f, text="HQ city:").grid(row=1, column=0, sticky="w", pady=6)
        self.var_hq = tk.StringVar()
        self.ent_hq = ttk.Entry(f, textvariable=self.var_hq, width=24)
        self.ent_hq.grid(row=1, column=1, sticky="w", padx=8)

        ttk.Label(f, text="Company name:").grid(row=2, column=0, sticky="w",
                                               pady=6)
        self.var_company = tk.StringVar()
        self.ent_company = ttk.Entry(f, textvariable=self.var_company, width=30)
        self.ent_company.grid(row=2, column=1, columnspan=3, sticky="w", padx=8)
        self.lbl_company_note = ttk.Label(f, foreground="#999", text="")
        self.lbl_company_note.grid(row=3, column=0, columnspan=5, sticky="w")

    def _build_garages_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="\U0001F3E0  Garages")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Own ALL garages (max size)",
                   command=self._own_all_garages).pack(side="left")
        self.lbl_gar = ttk.Label(bar, text="")
        self.lbl_gar.pack(side="left", padx=10)
        self.tree_gar = ttk.Treeview(tab, columns=("name", "status"),
                                     show="headings", selectmode="browse")
        self.tree_gar.heading("name", text="Garage")
        self.tree_gar.heading("status", text="status (0=none)")
        self.tree_gar.column("name", width=280)
        self.tree_gar.column("status", width=120)
        sb = ttk.Scrollbar(tab, orient="vertical", command=self.tree_gar.yview)
        self.tree_gar.configure(yscrollcommand=sb.set)
        self.tree_gar.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree_gar.bind("<Double-1>",
                           lambda e: self._edit_tree_value(self.tree_gar,
                                                           "status", e,
                                                           self._gar_units))
        self._gar_units = []

    def _build_trucks_tab(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="\U0001F69B  Trucks")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Repair ALL",
                   command=lambda: self._trucks_action("repair")).pack(side="left")
        ttk.Button(bar, text="Refuel ALL",
                   command=lambda: self._trucks_action("refuel")).pack(
            side="left", padx=4)
        ttk.Button(bar, text="Repair + Refuel ALL",
                   command=lambda: self._trucks_action("both")).pack(side="left")
        self.lbl_truck = ttk.Label(bar, text="")
        self.lbl_truck.pack(side="left", padx=10)
        self.tree_truck = ttk.Treeview(
            tab, columns=("name", "fuel", "wear"), show="headings")
        for c, t, w in (("name", "Vehicle", 240), ("fuel", "Fuel", 80),
                        ("wear", "Wear fields > 0", 120)):
            self.tree_truck.heading(c, text=t)
            self.tree_truck.column(c, width=w)
        sb = ttk.Scrollbar(tab, orient="vertical",
                           command=self.tree_truck.yview)
        self.tree_truck.configure(yscrollcommand=sb.set)
        self.tree_truck.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _build_explorer_tab(self):
        tab = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab, text="\U0001F5C2  Explorer (all data)")
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 4))
        ttk.Label(top, text="Filter:").pack(side="left")
        self.var_filter = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.var_filter, width=28)
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda _e: self._populate_units())
        self.lbl_count = ttk.Label(top, text="")
        self.lbl_count.pack(side="left", padx=8)

        panes = ttk.Panedwindow(tab, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left = ttk.Frame(panes)
        self.tree_units = ttk.Treeview(left, columns=("type", "name"),
                                       show="headings", selectmode="browse")
        self.tree_units.heading("type", text="Unit type")
        self.tree_units.heading("name", text="Name")
        self.tree_units.column("type", width=150)
        self.tree_units.column("name", width=170)
        sb1 = ttk.Scrollbar(left, orient="vertical",
                            command=self.tree_units.yview)
        self.tree_units.configure(yscrollcommand=sb1.set)
        self.tree_units.pack(side="left", fill="both", expand=True)
        sb1.pack(side="right", fill="y")
        self.tree_units.bind("<<TreeviewSelect>>", self._on_unit_select)
        panes.add(left, weight=1)
        right = ttk.Frame(panes)
        self.tree_fields = ttk.Treeview(right, columns=("field", "value"),
                                        show="headings", selectmode="browse")
        self.tree_fields.heading("field", text="Field")
        self.tree_fields.heading("value", text="Value")
        self.tree_fields.column("field", width=200)
        self.tree_fields.column("value", width=260)
        sb2 = ttk.Scrollbar(right, orient="vertical",
                            command=self.tree_fields.yview)
        self.tree_fields.configure(yscrollcommand=sb2.set)
        self.tree_fields.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.tree_fields.bind("<Double-1>", self._edit_field)
        panes.add(right, weight=2)
        self._cur_unit = None

    def _build_text_tab(self):
        tab = ttk.Frame(self.nb, padding=4)
        self.nb.add(tab, text="\U0001F4DD  Text (SiiN)")
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Refresh from data",
                   command=self._text_from_doc).pack(side="left", pady=2)
        ttk.Button(bar, text="Parse text into data",
                   command=self._text_into_doc).pack(side="left", padx=4)
        self.txt = tk.Text(tab, wrap="none", undo=True, font=("Consolas", 10))
        ys = ttk.Scrollbar(tab, orient="vertical", command=self.txt.yview)
        xs = ttk.Scrollbar(tab, orient="horizontal", command=self.txt.xview)
        self.txt.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.txt.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")

    def _build_statusbar(self):
        bar = ttk.Frame(self, padding=(10, 4))
        bar.pack(side="bottom", fill="x")
        self.status = tk.StringVar(value="No file open.")
        ttk.Label(bar, textvariable=self.status).pack(side="left")

    # ================================================================
    # Profiles / saves
    # ================================================================
    def refresh_profiles(self):
        try:
            self.profiles = find_profiles()
        except Exception:
            self.profiles = []
        game = self.game_filter.get()
        self._filtered = [p for p in self.profiles if p["game"] == game]
        labels = ["%s  [%s]" % (p["name"], p["profile"][:8])
                  for p in self._filtered]
        self.cb_profile["values"] = labels
        if labels:
            self.cb_profile.current(0)
            self._on_profile_change()
        else:
            self.cb_profile.set("(no profiles found)")
            self.cb_save.set("")
            self.cb_save["values"] = []
            self._draw_avatar(None)
            self.lbl_pname.configure(text="—")

    def _on_profile_change(self, _e=None):
        idx = self.cb_profile.current()
        if not (0 <= idx < len(self._filtered)):
            return
        prof = self._filtered[idx]
        self._draw_avatar(prof)
        self.lbl_pname.configure(text=prof["name"] or "—")
        saves = prof["saves"]
        self.cb_save["values"] = [s["label"] for s in saves]
        if saves:
            self.cb_save.current(0)

    def _current_save_path(self):
        pi = self.cb_profile.current()
        si = self.cb_save.current()
        if 0 <= pi < len(self._filtered):
            saves = self._filtered[pi]["saves"]
            if 0 <= si < len(saves):
                return saves[si]["path"]
        return None

    def _open_folder(self):
        path = self._current_save_path()
        if path:
            try:
                os.startfile(os.path.dirname(path))
            except Exception:
                pass

    def _add_custom_folder(self):
        folder = filedialog.askdirectory(
            title="Pick your game folder or a 'profiles' folder")
        if folder:
            add_custom_dir(folder)
            self.refresh_profiles()
            messagebox.showinfo("Folder added",
                                "Saved:\n%s\n\nProfiles reloaded." % folder)

    # ================================================================
    # Load
    # ================================================================
    def open_dialog(self):
        path = filedialog.askopenfilename(
            title="Open game.sii",
            filetypes=[("SII save", "*.sii"), ("All files", "*.*")])
        if path:
            self._load_path(path)

    def do_load(self):
        path = self._current_save_path()
        if not path:
            messagebox.showwarning("No save selected",
                                   "Pick a profile and save on the right, "
                                   "or use 'Open file manually...'.")
            return
        self._load_path(path)

    def _load_path(self, path):
        try:
            self.save = SaveFile(path)
        except Exception as exc:
            messagebox.showerror("Open error",
                                 "Could not decode the file:\n%s" % exc)
            return
        self._refresh_all_tabs()
        self.status.set("Loaded: %s  |  format: %s"
                        % (self.save.filename, self.save.source_format))
        if not self.save.is_game_save():
            messagebox.showwarning(
                "Not a game save",
                "This file has no 'economy'/'bank' unit, so money, XP and "
                "skills are NOT here.\n\nThey live in each save slot's "
                "'game.sii', not in 'profile.sii'.")

    def _refresh_all_tabs(self):
        s = self.save
        self.var_xp.set(s.get_field("experience_points", "economy") or "")
        for key, bar in self.skill_bars.items():
            bar.set(s.get_field(key, "economy") or 0)
        self.var_money.set(s.get_field("money_account", "bank") or "")
        self.var_hq.set(s.get_field("hq_city", "player") or "")
        cname = s.get_field("company_name")
        self.var_company.set(cname or "")
        self.ent_company.configure(state="normal" if cname is not None
                                   else "disabled")
        self.lbl_company_note.configure(
            text="" if cname is not None
            else "(no 'company_name' field in this save — edit via Explorer)")
        self._refresh_garages()
        self._refresh_trucks()
        self._populate_units()
        self.tree_fields.delete(*self.tree_fields.get_children())
        self._text_from_doc()
        self._refresh_summary()

    def _refresh_summary(self):
        s = self.save
        owned = sum(1 for u in s.doc.units_of("garage")
                    if (u.get("status") or "0") != "0")
        txt = ("Money: %s\nXP: %s\nTrucks: %d\nGarages owned: %d / %d\n"
               "Units: %d" % (
                   s.get_field("money_account", "bank") or "?",
                   s.get_field("experience_points", "economy") or "?",
                   len(s.vehicles()),
                   owned, len(s.doc.units_of("garage")),
                   len(s.doc.units)))
        self.lbl_summary.configure(text=txt)

    # ================================================================
    # Garages / trucks tabs
    # ================================================================
    def _refresh_garages(self):
        self.tree_gar.delete(*self.tree_gar.get_children())
        self._gar_units = self.save.doc.units_of("garage")
        for i, u in enumerate(self._gar_units):
            self.tree_gar.insert("", "end", iid=str(i),
                                 values=(u.name, u.get("status")))
        self.lbl_gar.configure(text="%d garages" % len(self._gar_units))

    def _own_all_garages(self):
        if not self.save:
            return
        n, status = self.save.own_all_garages()
        self._refresh_garages()
        self._refresh_summary()
        self.status.set("Set %d garages to status=%s (remember to SAVE)."
                        % (n, status))

    def _refresh_trucks(self):
        self.tree_truck.delete(*self.tree_truck.get_children())
        for i, u in enumerate(self.save.vehicles()):
            wear = sum(1 for f in u.fields
                       if f.key and "wear" in f.key and f.value not in ("0",))
            self.tree_truck.insert("", "end", iid=str(i),
                                   values=(u.name, u.get("fuel_relative"), wear))

    def _trucks_action(self, what):
        if not self.save:
            return
        msg = []
        if what in ("repair", "both"):
            msg.append("repaired %d wear fields" % self.save.repair_all())
        if what in ("refuel", "both"):
            msg.append("refueled %d trucks" % self.save.refuel_all())
        self._refresh_trucks()
        self._refresh_summary()
        self.status.set("Trucks: %s (remember to SAVE)." % ", ".join(msg))

    # ================================================================
    # Profile actions
    # ================================================================
    def _bump(self, var, step):
        try:
            cur = int(var.get() or 0)
        except ValueError:
            cur = 0
        var.set(str(cur + step))

    def _max_skills(self):
        for key, bar in self.skill_bars.items():
            bar.set(SKILL_MAX[key])

    def god_mode(self):
        if not self.save:
            messagebox.showwarning("Nothing open", "Load a save first.")
            return
        if not messagebox.askyesno(
                "MAX ALL (God Mode)",
                "Set money & XP to max, max all skills, repair & refuel every "
                "truck and own every garage?\n\nApplied to the loaded save; "
                "click SAVE afterwards to write it."):
            return
        r = self.save.god_mode()
        self._refresh_all_tabs()
        self.status.set("God Mode applied: money/xp/skills maxed, %d wear "
                        "fields fixed, %d trucks refueled, %d garages owned. "
                        "Click SAVE." % (r["repaired_fields"], r["refueled"],
                                         r["garages"]))

    # ================================================================
    # Explorer
    # ================================================================
    def _populate_units(self):
        self.tree_units.delete(*self.tree_units.get_children())
        if not self.save:
            return
        flt = self.var_filter.get().strip().lower()
        shown = 0
        for idx, u in enumerate(self.save.doc.units):
            if flt and flt not in u.type.lower() and flt not in u.name.lower():
                continue
            self.tree_units.insert("", "end", iid=str(idx),
                                   values=(u.type, u.name))
            shown += 1
            if shown >= 4000:
                break
        self.lbl_count.configure(
            text="%d / %d units" % (shown, len(self.save.doc.units)))

    def _on_unit_select(self, _e):
        sel = self.tree_units.selection()
        if not sel:
            return
        self._cur_unit = self.save.doc.units[int(sel[0])]
        self.tree_fields.delete(*self.tree_fields.get_children())
        for fi, f in enumerate(self._cur_unit.fields):
            if f.key is None:
                continue
            self.tree_fields.insert("", "end", iid=str(fi),
                                    values=(f.name, f.value))

    def _edit_field(self, _e):
        sel = self.tree_fields.selection()
        if not sel or not self._cur_unit:
            return
        fi = int(sel[0])
        field = self._cur_unit.fields[fi]
        self._inline_edit(self.tree_fields, sel[0], "value", field.value,
                          lambda v: setattr(field, "value", v))

    def _edit_tree_value(self, tree, col, event, units):
        sel = tree.selection()
        if not sel:
            return
        u = units[int(sel[0])]
        self._inline_edit(tree, sel[0], col, u.get("status"),
                          lambda v: (u.set("status", v),
                                     self._refresh_summary()))

    def _inline_edit(self, tree, iid, col, initial, commit_fn):
        bbox = tree.bbox(iid, column=col)
        if not bbox:
            return
        x, y, w, h = bbox
        var = tk.StringVar(value=initial or "")
        ent = tk.Entry(tree, textvariable=var)
        ent.place(x=x, y=y, width=w, height=h)
        ent.focus_set()
        ent.select_range(0, "end")

        def commit(_evt=None):
            commit_fn(var.get())
            tree.set(iid, col, var.get())
            ent.destroy()

        ent.bind("<Return>", commit)
        ent.bind("<FocusOut>", commit)
        ent.bind("<Escape>", lambda _x: ent.destroy())

    # ================================================================
    # Text
    # ================================================================
    def _text_from_doc(self):
        if not self.save:
            return
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", self.save.doc.render())

    def _text_into_doc(self):
        if not self.save:
            return
        self.save.reparse_text(self.txt.get("1.0", "end-1c"))
        self._refresh_all_tabs()
        self.status.set("Parsed edited text back into the data model.")

    # ================================================================
    # Save
    # ================================================================
    def _flush_ui_to_doc(self):
        s = self.save
        applied, missing = [], []

        def apply(key, value, unit):
            if value is None or str(value).strip() == "":
                return
            (applied if s.set_field(key, str(value).strip(), unit)
             else missing).append(key)

        apply("experience_points", self.var_xp.get(), "economy")
        apply("money_account", self.var_money.get(), "bank")
        apply("hq_city", self.var_hq.get(), "player")
        if self.ent_company.cget("state") != "disabled":
            apply("company_name", self.var_company.get(), None)
        for _icon, _label, key in SKILLS:
            apply(key, self.skill_bars[key].get(), "economy")
        return applied, missing

    def do_save(self):
        if not self.save:
            messagebox.showwarning("Nothing open", "Load a save first.")
            return
        applied, missing = self._flush_ui_to_doc()
        try:
            bak = self.save.save(make_backup=self.backup_var.get())
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))
            return
        self._text_from_doc()
        self._refresh_summary()
        msg = "Saved: %s" % self.save.filename
        if missing:
            msg += ("\n\nNOT found (skipped): %s\nYou may have opened the "
                    "wrong file (profile.sii vs game.sii)." % ", ".join(missing))
        if bak:
            msg += "\n\nBackup: %s" % os.path.basename(bak)
        msg += ("\n\nReminder: set  uset g_save_format \"2\"  in config.cfg "
                "so the game keeps text saves.")
        messagebox.showinfo("Done", msg)
        self.status.set("Saved: %s" % self.save.filename)


def _short(n):
    if n >= 1_000_000:
        return "%dM" % (n // 1_000_000)
    if n >= 1_000:
        return "%dk" % (n // 1_000)
    return str(n)


def main():
    app = EditorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
