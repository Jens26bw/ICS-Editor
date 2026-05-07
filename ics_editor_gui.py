import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from dataclasses import dataclass
from collections import Counter
from typing import List, Dict, Tuple, Optional

# -----------------------------
# ICS parsing helpers (minimal, practical)
# -----------------------------

def unfold_ics_lines(raw: str) -> List[str]:
    """
    RFC 5545 line unfolding:
    Lines that start with space or tab are continuations of the previous line.
    """
    lines = raw.splitlines()
    unfolded = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded

def fold_ics_line(line: str, limit: int = 75) -> List[str]:
    """
    Simple line folding at character length (not octet-perfect, but works for typical UTF-8 use in practice).
    """
    if len(line) <= limit:
        return [line]
    out = [line[:limit]]
    rest = line[limit:]
    while rest:
        out.append(" " + rest[:limit - 1])
        rest = rest[limit - 1:]
    return out

def fold_ics_lines(lines: List[str]) -> str:
    folded = []
    for line in lines:
        folded.extend(fold_ics_line(line))
    return "\r\n".join(folded) + "\r\n"

def get_summary_value(line: str) -> Optional[str]:
    """
    Extract SUMMARY value from a property line like:
      SUMMARY:Restmüll
      SUMMARY;LANGUAGE=de:Restmüll
    Returns the value portion after the first ":" or None if not SUMMARY.
    """
    if not line.startswith("SUMMARY"):
        return None
    if ":" not in line:
        return ""
    return line.split(":", 1)[1]

def set_summary_value(line: str, new_value: str) -> str:
    """
    Replace the SUMMARY value, preserving params.
    """
    if ":" not in line:
        return "SUMMARY:" + new_value
    left, _ = line.split(":", 1)
    return f"{left}:{new_value}"

@dataclass
class EventBlock:
    start_idx: int
    end_idx: int  # inclusive
    lines: List[str]
    summary_line_idx: Optional[int]  # index within lines
    summary_value: str

def parse_events(unfolded_lines: List[str]) -> Tuple[List[EventBlock], List[str]]:
    """
    Parse VEVENT blocks from unfolded lines.
    Returns (events, all_lines) where events include indices into all_lines.
    """
    events: List[EventBlock] = []
    i = 0
    n = len(unfolded_lines)
    while i < n:
        if unfolded_lines[i].strip() == "BEGIN:VEVENT":
            start = i
            j = i
            summary_val = ""
            summary_line_idx = None
            block_lines = []
            while j < n and unfolded_lines[j].strip() != "END:VEVENT":
                block_lines.append(unfolded_lines[j])
                val = get_summary_value(unfolded_lines[j])
                if val is not None:
                    summary_val = val
                    summary_line_idx = len(block_lines) - 1
                j += 1

            if j < n and unfolded_lines[j].strip() == "END:VEVENT":
                block_lines.append(unfolded_lines[j])
                end = j
            else:
                end = n - 1

            events.append(EventBlock(
                start_idx=start,
                end_idx=end,
                lines=block_lines,
                summary_line_idx=summary_line_idx,
                summary_value=summary_val
            ))
            i = end + 1
        else:
            i += 1
    return events, unfolded_lines

def apply_changes_to_ics(unfolded_lines: List[str],
                         events: List[EventBlock],
                         delete_summaries: set,
                         rename_map: Dict[str, str]) -> List[str]:
    """
    Build new unfolded lines:
      - remove events whose summary is in delete_summaries
      - rename events whose summary matches a key in rename_map
    """
    modified_blocks: Dict[int, List[str]] = {}

    for ev in events:
        s = ev.summary_value
        if s in delete_summaries:
            continue

        if s in rename_map:
            new_lines = ev.lines[:]
            if ev.summary_line_idx is not None:
                new_lines[ev.summary_line_idx] = set_summary_value(
                    new_lines[ev.summary_line_idx], rename_map[s]
                )
            else:
                insert_at = 1 if len(new_lines) > 1 else 0
                new_lines.insert(insert_at, "SUMMARY:" + rename_map[s])
            modified_blocks[ev.start_idx] = new_lines

    out2 = []
    i = 0
    n = len(unfolded_lines)

    while i < n:
        if unfolded_lines[i].strip() == "BEGIN:VEVENT":
            ev = next((e for e in events if e.start_idx == i), None)
            if ev is None:
                out2.append(unfolded_lines[i])
                i += 1
                continue

            s = ev.summary_value
            if s in delete_summaries:
                i = ev.end_idx + 1
                continue

            if i in modified_blocks:
                out2.extend(modified_blocks[i])
                i = ev.end_idx + 1
                continue

            out2.extend(ev.lines)
            i = ev.end_idx + 1
        else:
            out2.append(unfolded_lines[i])
            i += 1

    return out2


# -----------------------------
# GUI
# -----------------------------

class ICSGui(tk.Tk):
    COLORS = {
        "bg": "#f4f6f8",
        "panel": "#ffffff",
        "header": "#eef2f6",
        "text": "#17202a",
        "muted": "#667085",
        "border": "#d0d7de",
        "primary": "#2563eb",
        "primary_active": "#1d4ed8",
    }

    ACTION_KEEP = "Behalten"
    ACTION_DELETE = "Löschen"
    ACTION_RENAME = "Umbenennen"

    def __init__(self):
        super().__init__()
        self.title("ICS Editor")

        self.geometry("1040x720")
        self.minsize(920, 620)
        self.configure(bg=self.COLORS["bg"])
        self.option_add("*Font", ("DejaVu Sans", 10))

        self.file_path: Optional[str] = None
        self.raw_text: Optional[str] = None
        self.unfolded: List[str] = []
        self.events: List[EventBlock] = []

        self.summary_counts: Counter = Counter()

        # Where the file dialog should start (Docker: /data)
        self.ics_dir = os.environ.get("ICS_DIR", "/data")

        self._build_styles()

        shell = ttk.Frame(self, style="App.TFrame", padding=18)
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell, style="App.TFrame")
        header.pack(fill="x", pady=(0, 14))

        title_box = ttk.Frame(header, style="App.TFrame")
        title_box.pack(side="left", fill="x", expand=True)

        ttk.Label(title_box, text="ICS Editor", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="Termine aus einer ICS-Datei prüfen, umbenennen oder entfernen.",
            style="Muted.TLabel"
        ).pack(anchor="w", pady=(2, 0))

        self.btn_open = ttk.Button(header, text="ICS-Datei öffnen", style="Primary.TButton", command=self.open_file)
        self.btn_open.pack(side="right", padx=(12, 0), ipady=4)

        toolbar = ttk.Frame(shell, style="Panel.TFrame", padding=14)
        toolbar.pack(fill="x", pady=(0, 12))

        file_box = ttk.Frame(toolbar, style="Panel.TFrame")
        file_box.pack(side="left", fill="x", expand=True)

        ttk.Label(file_box, text="Aktuelle Datei", style="Caption.TLabel").pack(anchor="w")
        self.lbl_file = ttk.Label(file_box, text="Keine Datei geladen", style="File.TLabel", anchor="w")
        self.lbl_file.pack(anchor="w", fill="x", pady=(3, 0))

        filter_box = ttk.Frame(toolbar, style="Panel.TFrame")
        filter_box.pack(side="right", fill="x", padx=(18, 0))

        ttk.Label(filter_box, text="Filter", style="Caption.TLabel").pack(anchor="w")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self.render_list())
        self.ent_filter = ttk.Entry(filter_box, textvariable=self.filter_var, width=30)
        self.ent_filter.pack(anchor="w", pady=(3, 0), ipady=3)

        list_panel = ttk.Frame(shell, style="Panel.TFrame")
        list_panel.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            list_panel,
            borderwidth=0,
            highlightthickness=0,
            background=self.COLORS["panel"]
        )
        self.frame_list = ttk.Frame(self.canvas, style="Panel.TFrame", padding=12)
        self.vsb = ttk.Scrollbar(list_panel, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas_frame = self.canvas.create_window((0, 0), window=self.frame_list, anchor="nw")

        self.frame_list.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        bottom = ttk.Frame(shell, style="App.TFrame")
        bottom.pack(fill="x", pady=(12, 0))

        self.btn_select_all = ttk.Button(bottom, text="Alle auswählen", command=lambda: self.set_all_checks(True))
        self.btn_select_none = ttk.Button(bottom, text="Auswahl aufheben", command=lambda: self.set_all_checks(False))
        self.btn_select_all.pack(side="left")
        self.btn_select_none.pack(side="left", padx=8)

        self.btn_apply = ttk.Button(
            bottom,
            text="Änderungen speichern unter...",
            style="Primary.TButton",
            command=self.apply_and_save,
            state="disabled"
        )
        self.btn_apply.pack(side="right", ipady=4)

        # internal list state
        self.rows: List[Dict] = []

    def _build_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background=self.COLORS["bg"])
        style.configure("Panel.TFrame", background=self.COLORS["panel"])
        style.configure("Row.TFrame", background=self.COLORS["panel"])
        style.configure("Header.TFrame", background=self.COLORS["header"])

        style.configure("TLabel", background=self.COLORS["panel"], foreground=self.COLORS["text"])
        style.configure("Title.TLabel", background=self.COLORS["bg"], foreground=self.COLORS["text"], font=("DejaVu Sans", 19, "bold"))
        style.configure("Muted.TLabel", background=self.COLORS["bg"], foreground=self.COLORS["muted"])
        style.configure("Caption.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["muted"], font=("DejaVu Sans", 9, "bold"))
        style.configure("File.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["text"])
        style.configure("Header.TLabel", background=self.COLORS["header"], foreground=self.COLORS["muted"], font=("DejaVu Sans", 9, "bold"))
        style.configure("Empty.TLabel", background=self.COLORS["panel"], foreground=self.COLORS["muted"], font=("DejaVu Sans", 11))

        style.configure("TButton", padding=(12, 7), background="#ffffff", foreground=self.COLORS["text"], bordercolor=self.COLORS["border"])
        style.map("TButton", background=[("active", "#eef2f6")])
        style.configure("Primary.TButton", background=self.COLORS["primary"], foreground="#ffffff", bordercolor=self.COLORS["primary"])
        style.map("Primary.TButton", background=[("active", self.COLORS["primary_active"]), ("disabled", "#9ca3af")])

        style.configure("TEntry", fieldbackground="#ffffff", bordercolor=self.COLORS["border"], lightcolor=self.COLORS["border"], darkcolor=self.COLORS["border"])
        style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff", arrowcolor=self.COLORS["text"], bordercolor=self.COLORS["border"])
        style.configure("TCheckbutton", background=self.COLORS["panel"], foreground=self.COLORS["text"])

    def on_frame_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def open_file(self):
        path = filedialog.askopenfilename(
            title="ICS-Datei auswählen",
            initialdir=self.ics_dir,
            filetypes=[("iCalendar", "*.ics *.ical"), ("Alle Dateien", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except Exception as e:
            messagebox.showerror("Fehler", f"Die Datei konnte nicht gelesen werden:\n{e}")
            return

        self.file_path = path
        self.raw_text = raw
        self.unfolded = unfold_ics_lines(raw)
        self.events, _ = parse_events(self.unfolded)

        counts = Counter()
        for ev in self.events:
            counts[ev.summary_value] += 1
        self.summary_counts = counts

        self.lbl_file.config(text=path)
        self.btn_apply.config(state="normal")

        self.render_list()

    def clear_list(self):
        for child in self.frame_list.winfo_children():
            child.destroy()
        self.rows.clear()

    def render_list(self):
        self.clear_list()

        if not self.file_path:
            return

        filt = self.filter_var.get().strip().lower()

        hdr = ttk.Frame(self.frame_list, style="Header.TFrame", padding=(10, 8))
        hdr.pack(fill="x", pady=(0, 8))
        ttk.Label(hdr, text="", width=4, style="Header.TLabel").pack(side="left")
        ttk.Label(hdr, text="Termin", anchor="w", style="Header.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Label(hdr, text="Anzahl", width=8, anchor="center", style="Header.TLabel").pack(side="left")
        ttk.Label(hdr, text="Aktion", width=16, anchor="w", style="Header.TLabel").pack(side="left", padx=(12, 0))
        ttk.Label(hdr, text="Neuer Name", anchor="w", style="Header.TLabel").pack(side="left", fill="x", expand=True, padx=(10, 0))

        for summary in sorted(self.summary_counts.keys(), key=lambda s: s.lower()):
            count = self.summary_counts[summary]
            if filt and filt not in summary.lower():
                continue

            row = ttk.Frame(self.frame_list, style="Row.TFrame", padding=(10, 6))
            row.pack(fill="x", pady=1)

            var_checked = tk.BooleanVar(value=False)
            ttk.Checkbutton(row, variable=var_checked).pack(side="left", padx=(0, 8))

            ttk.Label(row, text=summary or "(ohne Titel)", anchor="w").pack(side="left", fill="x", expand=True)

            ttk.Label(row, text=str(count), width=8, anchor="center").pack(side="left")

            var_action = tk.StringVar(value=self.ACTION_KEEP)
            opt = ttk.Combobox(
                row,
                textvariable=var_action,
                values=(self.ACTION_KEEP, self.ACTION_DELETE, self.ACTION_RENAME),
                width=14,
                state="readonly"
            )
            opt.pack(side="left", padx=(12, 0))

            rename_var = tk.StringVar(value="")
            ent = ttk.Entry(row, textvariable=rename_var)
            ent.pack(side="left", fill="x", expand=True, padx=(10, 0), ipady=2)

            def on_action_change(*_args, v=var_action, e=ent):
                e.configure(state=("normal" if v.get() == self.ACTION_RENAME else "disabled"))

            var_action.trace_add("write", on_action_change)
            on_action_change()

            self.rows.append({
                "summary": summary,
                "checked": var_checked,
                "action": var_action,
                "rename": rename_var
            })

        if not self.rows:
            ttk.Label(
                self.frame_list,
                text="Keine passenden Termine gefunden.",
                style="Empty.TLabel"
            ).pack(anchor="center", pady=36)

    def set_all_checks(self, value: bool):
        for r in self.rows:
            r["checked"].set(value)

    def apply_and_save(self):
        if not self.file_path or self.raw_text is None:
            return

        delete_summaries = set()
        rename_map = {}

        selected_any = False
        for r in self.rows:
            if not r["checked"].get():
                continue
            selected_any = True
            action = r["action"].get()
            summary = r["summary"]
            if action == self.ACTION_DELETE:
                delete_summaries.add(summary)
            elif action == self.ACTION_RENAME:
                new_name = r["rename"].get().strip()
                if not new_name:
                    messagebox.showerror("Fehler", f"Bei '{summary}' wurde 'Umbenennen' gewählt, aber kein neuer Name eingetragen.")
                    return
                rename_map[summary] = new_name

        if not selected_any:
            messagebox.showinfo("Info", "Es wurde kein Termin ausgewählt.")
            return

        new_unfolded = apply_changes_to_ics(self.unfolded, self.events, delete_summaries, rename_map)
        new_ics = fold_ics_lines(new_unfolded)

        out_path = filedialog.asksaveasfilename(
            title="Speichern unter",
            initialdir=self.ics_dir,
            defaultextension=".ics",
            filetypes=[("iCalendar", "*.ics"), ("Alle Dateien", "*.*")]
        )
        if not out_path:
            return

        try:
            with open(out_path, "w", encoding="utf-8", newline="") as f:
                f.write(new_ics)
        except Exception as e:
            messagebox.showerror("Fehler", f"Die Datei konnte nicht gespeichert werden:\n{e}")
            return

        messagebox.showinfo("Fertig", "Die neue ICS-Datei wurde gespeichert und kann jetzt importiert werden.")


if __name__ == "__main__":
    app = ICSGui()
    app.mainloop()
