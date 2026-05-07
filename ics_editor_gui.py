import os
import tkinter as tk
from tkinter import filedialog, messagebox
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
    def __init__(self):
        super().__init__()
        self.title("ICS Termin-Editor (SUMMARY)")

        self.geometry("820x600")
        self.minsize(820, 600)

        self.file_path: Optional[str] = None
        self.raw_text: Optional[str] = None
        self.unfolded: List[str] = []
        self.events: List[EventBlock] = []

        self.summary_counts: Counter = Counter()

        # Where the file dialog should start (Docker: /data)
        self.ics_dir = os.environ.get("ICS_DIR", "/data")

        # Top controls
        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        self.btn_open = tk.Button(top, text="ICS öffnen", command=self.open_file)
        self.btn_open.pack(side="left")

        self.lbl_file = tk.Label(top, text="Keine Datei geladen", anchor="w")
        self.lbl_file.pack(side="left", padx=10, fill="x", expand=True)

        # Filter row
        filt = tk.Frame(self)
        filt.pack(fill="x", padx=10)

        tk.Label(filt, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self.render_list())
        self.ent_filter = tk.Entry(filt, textvariable=self.filter_var)
        self.ent_filter.pack(side="left", fill="x", expand=True, padx=6)

        # Scrollable list
        self.canvas = tk.Canvas(self, borderwidth=0)
        self.frame_list = tk.Frame(self.canvas)
        self.vsb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.canvas_frame = self.canvas.create_window((0, 0), window=self.frame_list, anchor="nw")

        self.frame_list.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # Bottom actions
        bottom = tk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=10)

        self.btn_select_all = tk.Button(bottom, text="Alle markieren", command=lambda: self.set_all_checks(True))
        self.btn_select_none = tk.Button(bottom, text="Keine markieren", command=lambda: self.set_all_checks(False))
        self.btn_select_all.pack(side="left")
        self.btn_select_none.pack(side="left", padx=6)

        self.btn_apply = tk.Button(bottom, text="Anwenden & Speichern unter…", command=self.apply_and_save, state="disabled")
        self.btn_apply.pack(side="right")

        # internal list state
        self.rows: List[Dict] = []

    def on_frame_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def open_file(self):
        path = filedialog.askopenfilename(
            title="ICS auswählen",
            initialdir=self.ics_dir,
            filetypes=[("iCalendar", "*.ics *.ical"), ("Alle Dateien", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except Exception as e:
            messagebox.showerror("Fehler", f"Kann Datei ned lese:\n{e}")
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

        # Header
        hdr = tk.Frame(self.frame_list)
        hdr.pack(fill="x", pady=(0, 6))
        tk.Label(hdr, text="✓", width=3).pack(side="left")
        tk.Label(hdr, text="Termin (SUMMARY)", anchor="w").pack(side="left", fill="x", expand=True)
        tk.Label(hdr, text="Anz.", width=6).pack(side="left")
        tk.Label(hdr, text="Aktion", width=14).pack(side="left")
        tk.Label(hdr, text="Neuer Name (wenn Umbenennen)", anchor="w").pack(side="left", fill="x", expand=True)

        for summary in sorted(self.summary_counts.keys(), key=lambda s: s.lower()):
            count = self.summary_counts[summary]
            if filt and filt not in summary.lower():
                continue

            row = tk.Frame(self.frame_list)
            row.pack(fill="x", pady=2)

            var_checked = tk.BooleanVar(value=False)
            tk.Checkbutton(row, variable=var_checked).pack(side="left", padx=(0, 6))

            tk.Label(row, text=summary, anchor="w").pack(side="left", fill="x", expand=True)

            tk.Label(row, text=str(count), width=6).pack(side="left")

            var_action = tk.StringVar(value="keep")  # keep | delete | rename
            opt = tk.OptionMenu(row, var_action, "keep", "delete", "rename")
            opt.configure(width=10)
            opt.pack(side="left", padx=6)

            rename_var = tk.StringVar(value="")
            ent = tk.Entry(row, textvariable=rename_var)
            ent.pack(side="left", fill="x", expand=True)

            def on_action_change(*_args, v=var_action, e=ent):
                e.configure(state=("normal" if v.get() == "rename" else "disabled"))

            var_action.trace_add("write", on_action_change)
            on_action_change()

            self.rows.append({
                "summary": summary,
                "checked": var_checked,
                "action": var_action,
                "rename": rename_var
            })

        if not self.rows:
            tk.Label(self.frame_list, text="Nix g'funda (Filter zu streng?)").pack(anchor="w", pady=10)

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
            if action == "delete":
                delete_summaries.add(summary)
            elif action == "rename":
                new_name = r["rename"].get().strip()
                if not new_name:
                    messagebox.showerror("Fehler", f"Bei '{summary}' isch 'Umbenennen' ausgewählt, aber neuer Name isch leer.")
                    return
                rename_map[summary] = new_name

        if not selected_any:
            messagebox.showinfo("Info", "Du hosch nix markiert. Dann passiert au nix.")
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
            messagebox.showerror("Fehler", f"Konnte ned speichern:\n{e}")
            return

        messagebox.showinfo("Fertig", "G'speichert. Du kasch die neue .ics jetzt importiere.")


if __name__ == "__main__":
    app = ICSGui()
    app.mainloop()
