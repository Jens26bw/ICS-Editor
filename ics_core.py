from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


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
    Simple line folding at character length.
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
    if not line.startswith("SUMMARY"):
        return None
    if ":" not in line:
        return ""
    return line.split(":", 1)[1]


def set_summary_value(line: str, new_value: str) -> str:
    if ":" not in line:
        return "SUMMARY:" + new_value
    left, _ = line.split(":", 1)
    return f"{left}:{new_value}"


@dataclass
class EventBlock:
    start_idx: int
    end_idx: int
    lines: List[str]
    summary_line_idx: Optional[int]
    summary_value: str


def parse_events(unfolded_lines: List[str]) -> Tuple[List[EventBlock], List[str]]:
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
