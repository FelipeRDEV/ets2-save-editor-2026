"""Graphical interface (Tkinter) for the ETS2/ATS save editor."""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .save import SaveFile, find_profiles, QUICK_FIELDS


class EditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ETS2 / ATS Save Editor 2026")
        self.geometry("900x640")
        self.minsize(720, 520)

        self.save = None           # current SaveFile
        self.quick_vars = {}       # key -> StringVar

        self._build_topbar()
        self._build_notebook()
        self._build_statusbar()
        self._populate_profiles()

    # -- UI construction --------------------------------------------------
    def _build_topbar(self):
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill="x")

        ttk.Button(bar, text="Open file...",
                   command=self.open_dialog).pack(side="left")

        ttk.Label(bar, text="  Detected profiles:").pack(side="left")
        self.profile_cb = ttk.Combobox(bar, state="readonly", width=45)
        self.profile_cb.pack(side="left", padx=4)
        self.profile_cb.bind("<<ComboboxSelected>>", self._on_profile_pick)

        ttk.Button(bar, text="Reload profiles",
                   command=self._populate_profiles).pack(side="left")

    def _build_notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=4)

        # Tab 1: quick edit
        self.tab_quick = ttk.Frame(self.nb, padding=12)
        self.nb.add(self.tab_quick, text="Quick edit")
        for row, (key, label, _kind) in enumerate(QUICK_FIELDS):
            ttk.Label(self.tab_quick, text=label + ":").grid(
                row=row, column=0, sticky="w", pady=4, padx=(0, 10))
            var = tk.StringVar()
            self.quick_vars[key] = var
            ttk.Entry(self.tab_quick, textvariable=var, width=28).grid(
                row=row, column=1, sticky="w", pady=4)
        ttk.Label(
            self.tab_quick,
            text=("Tip: empty / not-found fields are ignored.\n"
                  "'money_account' lives in the bank unit; skills and XP "
                  "in the economy unit."),
            foreground="#666",
        ).grid(row=len(QUICK_FIELDS), column=0, columnspan=2,
               sticky="w", pady=(16, 0))

        # Tab 2: raw text
        self.tab_raw = ttk.Frame(self.nb, padding=4)
        self.nb.add(self.tab_raw, text="Text (SiiN)")
        self.txt = tk.Text(self.tab_raw, wrap="none", undo=True,
                           font=("Consolas", 10))
        yscroll = ttk.Scrollbar(self.tab_raw, orient="vertical",
                                command=self.txt.yview)
        xscroll = ttk.Scrollbar(self.tab_raw, orient="horizontal",
                                command=self.txt.xview)
        self.txt.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.txt.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.tab_raw.rowconfigure(0, weight=1)
        self.tab_raw.columnconfigure(0, weight=1)

    def _build_statusbar(self):
        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill="x")
        self.status = tk.StringVar(value="No file open.")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")

        self.backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bottom, text="Make backup",
                        variable=self.backup_var).pack(side="right", padx=4)
        ttk.Button(bottom, text="Save",
                   command=self.do_save).pack(side="right")
        ttk.Button(bottom, text="Apply fields to text",
                   command=self._apply_quick_to_text).pack(side="right", padx=4)

    # -- profiles ---------------------------------------------------------
    def _populate_profiles(self):
        self.profiles_flat = []
        try:
            profiles = find_profiles()
        except Exception:
            profiles = []
        labels = []
        for p in profiles:
            for s in p["saves"]:
                self.profiles_flat.append(s["path"])
                labels.append("[%s] %s / %s" % (
                    p["game"].split()[0], p["name"], s["slot"]))
        self.profile_cb["values"] = labels
        if not labels:
            self.profile_cb.set("(no profiles found)")

    def _on_profile_pick(self, _event):
        idx = self.profile_cb.current()
        if 0 <= idx < len(self.profiles_flat):
            self.load_file(self.profiles_flat[idx])

    # -- open / load ------------------------------------------------------
    def open_dialog(self):
        path = filedialog.askopenfilename(
            title="Open game.sii",
            filetypes=[("SII save", "*.sii"), ("All files", "*.*")])
        if path:
            self.load_file(path)

    def load_file(self, path):
        try:
            self.save = SaveFile(path)
        except Exception as exc:
            messagebox.showerror("Open error",
                                 "Could not decode the file:\n%s" % exc)
            return
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", self.save.text)
        for key, var in self.quick_vars.items():
            val = self.save.get_field(key)
            var.set(val if val is not None else "")
        self.status.set("Open: %s  |  original format: %s"
                        % (os.path.basename(path), self.save.source_format))

    # -- apply / save -----------------------------------------------------
    def _apply_quick_to_text(self):
        """Apply the quick fields to the in-memory text and refresh the tab."""
        if not self.save:
            return
        # sync from the text tab (in case the user edited it directly)
        self.save.text = self.txt.get("1.0", "end-1c")
        values = {k: v.get() for k, v in self.quick_vars.items()}
        applied = self.save.apply_quick_fields(values)
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", self.save.text)
        self.status.set("Fields applied to text: %s"
                        % (", ".join(applied) if applied else "none"))

    def do_save(self):
        if not self.save:
            messagebox.showwarning("Nothing open", "Open a save first.")
            return
        # make sure quick fields are applied and take the text from the tab
        self._apply_quick_to_text()
        self.save.text = self.txt.get("1.0", "end-1c")
        try:
            bak = self.save.save(make_backup=self.backup_var.get())
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))
            return
        msg = "Saved successfully."
        if bak:
            msg += "\nBackup: %s" % os.path.basename(bak)
        msg += ("\n\nReminder: for the game to accept text saves, set\n"
                "g_save_format 2 in config.cfg (otherwise it rewrites on save).")
        messagebox.showinfo("Done", msg)
        self.status.set("Saved: %s" % os.path.basename(self.save.path))


def main():
    app = EditorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
