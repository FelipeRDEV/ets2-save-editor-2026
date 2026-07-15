"""Graphical interface (Tkinter) for the ETS2/ATS save editor.

Layout inspired by TS-SE Tool: a right-hand "Profiles & Saves" panel with big
Load/Save buttons and a tabbed editor (Profile, Company, Explorer, Text).
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .save import SaveFile, find_profiles, add_custom_dir


# Skill display name -> economy field key, with a max number of point boxes.
SKILLS = [
    ("ADR (dangerous goods)", "adr", 6),
    ("Long Distance", "long_dist", 6),
    ("High Value Cargo", "heavy", 6),
    ("Fragile Cargo", "fragile", 6),
    ("Just-In-Time Delivery", "urgent", 6),
    ("Ecodriving", "mechanical", 6),
]


class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ETS2 / ATS Save Editor 2026")
        self.geometry("1000x680")
        self.minsize(900, 620)

        self.save = None
        self.profiles = []
        self.game_filter = tk.StringVar(value="Euro Truck Simulator 2")
        self.backup_var = tk.BooleanVar(value=True)
        self.skill_vars = {}     # key -> IntVar
        self.skill_boxes = {}    # key -> [buttons]

        self._build_sidebar()
        self._build_main()
        self._build_statusbar()
        self.refresh_profiles()

    # ================================================================
    # Sidebar: game toggle + profiles/saves + Load/Save
    # ================================================================
    def _build_sidebar(self):
        side = ttk.Frame(self, padding=8, width=280)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)

        game = ttk.Frame(side)
        game.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(game, text="ETS 2", value="Euro Truck Simulator 2",
                        variable=self.game_filter, command=self.refresh_profiles,
                        width=12).pack(side="left", expand=True, fill="x")
        ttk.Radiobutton(game, text="ATS", value="American Truck Simulator",
                        variable=self.game_filter, command=self.refresh_profiles,
                        width=12).pack(side="left", expand=True, fill="x")

        ttk.Button(side, text="Add Custom Folder...",
                   command=self._add_custom_folder).pack(fill="x", pady=(0, 8))

        grp = ttk.LabelFrame(side, text="Profiles && Saves", padding=8)
        grp.pack(fill="both", expand=True)

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
                   command=self.open_dialog).pack(fill="x", pady=(2, 8))

        ttk.Checkbutton(grp, text="Make backup before saving",
                        variable=self.backup_var).pack(anchor="w", pady=2)

        big = ttk.Style()
        big.configure("Big.TButton", font=("Segoe UI", 12, "bold"), padding=12)
        ttk.Button(grp, text="LOAD", style="Big.TButton",
                   command=self.do_load).pack(fill="x", pady=(8, 4))
        ttk.Button(grp, text="SAVE", style="Big.TButton",
                   command=self.do_save).pack(fill="x", pady=4)

    # ================================================================
    # Main area: notebook
    # ================================================================
    def _build_main(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self._build_profile_tab()
        self._build_company_tab()
        self._build_explorer_tab()
        self._build_text_tab()

    def _build_profile_tab(self):
        tab = ttk.Frame(self.nb, padding=14)
        self.nb.add(tab, text="Profile")

        xpf = ttk.LabelFrame(tab, text="Experience", padding=10)
        xpf.pack(fill="x")
        ttk.Label(xpf, text="XP (experience_points):").grid(row=0, column=0,
                                                            sticky="w")
        self.var_xp = tk.StringVar()
        ttk.Entry(xpf, textvariable=self.var_xp, width=16).grid(
            row=0, column=1, sticky="w", padx=8)
        for i, step in enumerate((1000, 10000, 100000)):
            ttk.Button(xpf, text="+%d" % step, width=9,
                       command=lambda s=step: self._bump_xp(s)).grid(
                row=0, column=2 + i, padx=2)
        ttk.Button(xpf, text="0", width=4,
                   command=lambda: self.var_xp.set("0")).grid(row=0, column=5, padx=2)

        skf = ttk.LabelFrame(tab, text="Skills (click a box to set the level)",
                             padding=10)
        skf.pack(fill="x", pady=12)
        for r, (label, key, maxpts) in enumerate(SKILLS):
            ttk.Label(skf, text=label, width=22).grid(row=r, column=0,
                                                      sticky="w", pady=3)
            var = tk.IntVar(value=0)
            self.skill_vars[key] = var
            boxes = []
            for p in range(1, maxpts + 1):
                b = tk.Button(skf, text=str(p), width=3, relief="raised",
                              command=lambda k=key, n=p: self._set_skill(k, n))
                b.grid(row=r, column=p, padx=1)
                boxes.append(b)
            self.skill_boxes[key] = boxes
            lbl = ttk.Label(skf, textvariable=var, width=3)
            lbl.grid(row=r, column=maxpts + 2, padx=(8, 0))

        ttk.Label(tab, foreground="#666",
                  text=("Skills map to the economy unit fields: adr, long_dist, "
                        "heavy, fragile, urgent, mechanical.")).pack(anchor="w")

    def _build_company_tab(self):
        tab = ttk.Frame(self.nb, padding=14)
        self.nb.add(tab, text="Company")

        f = ttk.LabelFrame(tab, text="Bank / Company", padding=10)
        f.pack(fill="x")
        ttk.Label(f, text="Money (money_account):").grid(row=0, column=0,
                                                        sticky="w", pady=4)
        self.var_money = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_money, width=20).grid(
            row=0, column=1, sticky="w", padx=8)
        for i, step in enumerate((100000, 1000000, 10000000)):
            ttk.Button(f, text="+%s" % _short(step), width=8,
                       command=lambda s=step: self._bump_money(s)).grid(
                row=0, column=2 + i, padx=2)

        ttk.Label(f, text="Company name:").grid(row=1, column=0, sticky="w",
                                               pady=4)
        self.var_company = tk.StringVar()
        self.ent_company = ttk.Entry(f, textvariable=self.var_company, width=30)
        self.ent_company.grid(row=1, column=1, columnspan=3, sticky="w", padx=8)
        self.lbl_company_note = ttk.Label(f, foreground="#666", text="")
        self.lbl_company_note.grid(row=2, column=0, columnspan=5, sticky="w")

        gf = ttk.LabelFrame(tab, text="Garages (from the save)", padding=6)
        gf.pack(fill="both", expand=True, pady=12)
        self.garage_list = tk.Listbox(gf)
        self.garage_list.pack(fill="both", expand=True)
        ttk.Label(tab, foreground="#666",
                  text=("Detailed garage/city/truck editing: use the Explorer "
                        "tab — every unit and field is editable there.")).pack(
            anchor="w")

    def _build_explorer_tab(self):
        tab = ttk.Frame(self.nb, padding=6)
        self.nb.add(tab, text="Explorer (all data)")

        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 4))
        ttk.Label(top, text="Filter units:").pack(side="left")
        self.var_filter = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.var_filter, width=30)
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
        self.tree_units.column("type", width=140)
        self.tree_units.column("name", width=180)
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
        self.nb.add(tab, text="Text (SiiN)")
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Refresh from data",
                   command=self._text_from_doc).pack(side="left", pady=2)
        ttk.Button(bar, text="Parse text into data",
                   command=self._text_into_doc).pack(side="left", padx=4)
        ttk.Label(bar, foreground="#666",
                  text="Power users: edit raw SiiN, then 'Parse text into data'."
                  ).pack(side="left", padx=8)
        self.txt = tk.Text(tab, wrap="none", undo=True, font=("Consolas", 10))
        ys = ttk.Scrollbar(tab, orient="vertical", command=self.txt.yview)
        xs = ttk.Scrollbar(tab, orient="horizontal", command=self.txt.xview)
        self.txt.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.txt.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")

    def _build_statusbar(self):
        bar = ttk.Frame(self, padding=(8, 4))
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

    def _on_profile_change(self, _e=None):
        idx = self.cb_profile.current()
        if not (0 <= idx < len(self._filtered)):
            return
        saves = self._filtered[idx]["saves"]
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
            os.startfile(os.path.dirname(path))  # noqa: S606 (Windows)

    def _add_custom_folder(self):
        folder = filedialog.askdirectory(
            title="Pick your game folder or a 'profiles' folder")
        if folder:
            add_custom_dir(folder)
            self.refresh_profiles()
            messagebox.showinfo("Folder added",
                                "Added and saved:\n%s\n\nProfiles reloaded."
                                % folder)

    # ================================================================
    # Load / populate
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
                                   "Pick a profile and a save on the right, "
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
                "skills are NOT here.\n\nMoney/XP live in the save's "
                "'game.sii' (inside each save slot), not in 'profile.sii'.\n\n"
                "You can still edit whatever it contains in the Explorer tab.")

    def _refresh_all_tabs(self):
        s = self.save
        # Profile
        self.var_xp.set(s.get_field("experience_points", "economy") or "")
        for key, var in self.skill_vars.items():
            val = s.get_field(key, "economy")
            try:
                var.set(int(val))
            except (TypeError, ValueError):
                var.set(0)
            self._paint_skill(key)
        # Company
        self.var_money.set(s.get_field("money_account", "bank") or "")
        cname = s.get_field("company_name") or s.get_field("name", "user")
        self.var_company.set(cname or "")
        self.ent_company.configure(state="normal" if cname is not None
                                   else "disabled")
        self.lbl_company_note.configure(
            text="" if cname is not None
            else "(no company/name field found in this file)")
        self.garage_list.delete(0, "end")
        for g in s.doc.units_of("garage"):
            status = g.get("status")
            self.garage_list.insert("end", "%s   status=%s" % (g.name, status))
        # Explorer + Text
        self._populate_units()
        self.tree_fields.delete(*self.tree_fields.get_children())
        self._text_from_doc()

    # ================================================================
    # Profile tab actions
    # ================================================================
    def _bump_xp(self, step):
        try:
            cur = int(self.var_xp.get() or 0)
        except ValueError:
            cur = 0
        self.var_xp.set(str(cur + step))

    def _set_skill(self, key, n):
        var = self.skill_vars[key]
        var.set(n if var.get() != n else n - 1)
        self._paint_skill(key)

    def _paint_skill(self, key):
        val = self.skill_vars[key].get()
        for i, b in enumerate(self.skill_boxes[key], start=1):
            b.configure(bg="#e0a020" if i <= val else "SystemButtonFace",
                        activebackground="#f0b840" if i <= val else "SystemButtonFace")

    def _bump_money(self, step):
        try:
            cur = int(self.var_money.get() or 0)
        except ValueError:
            cur = 0
        self.var_money.set(str(cur + step))

    # ================================================================
    # Explorer tab
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
        x, y, w, h = self.tree_fields.bbox(sel[0], column="value")
        var = tk.StringVar(value=field.value)
        ent = tk.Entry(self.tree_fields, textvariable=var)
        ent.place(x=x, y=y, width=w, height=h)
        ent.focus_set()
        ent.select_range(0, "end")

        def commit(_evt=None):
            field.value = var.get()
            self.tree_fields.set(sel[0], "value", field.value)
            ent.destroy()

        ent.bind("<Return>", commit)
        ent.bind("<FocusOut>", commit)
        ent.bind("<Escape>", lambda _x: ent.destroy())

    # ================================================================
    # Text tab
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
        """Write the friendly-tab widgets back into the document model."""
        s = self.save
        applied, missing = [], []

        def apply(key, value, unit):
            if value is None or str(value).strip() == "":
                return
            if s.set_field(key, str(value).strip(), unit):
                applied.append(key)
            else:
                missing.append(key)

        apply("experience_points", self.var_xp.get(), "economy")
        apply("money_account", self.var_money.get(), "bank")
        if self.ent_company.cget("state") != "disabled":
            # company name may be quoted
            name = self.var_company.get().strip()
            if name and not name.startswith('"'):
                name = '"%s"' % name if " " in name else name
            apply("company_name", name, None)
        for _label, key, _mx in SKILLS:
            apply(key, self.skill_vars[key].get(), "economy")
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
        msg = "Saved: %s\n\nFields written: %s" % (
            self.save.filename, ", ".join(applied) if applied else "(none)")
        if missing:
            msg += ("\n\nNOT found in this file (skipped): %s\n"
                    "These fields don't exist here — you may have opened the "
                    "wrong file (e.g. profile.sii instead of game.sii)."
                    % ", ".join(missing))
        if bak:
            msg += "\n\nBackup: %s" % os.path.basename(bak)
        msg += ("\n\nReminder: set  uset g_save_format \"2\"  in config.cfg so "
                "the game keeps text saves.")
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
