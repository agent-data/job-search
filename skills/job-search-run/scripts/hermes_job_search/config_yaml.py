"""config_yaml.py — stdlib-only handling of the workspace config.yaml.

The runtime ships no YAML library, so this is deliberately scoped to the documented config schema
(templates/config.example.yaml): top-level scalars, one level of nested maps, and a `queries:` list
of single-line flow-maps. Two operations:

  * load-config  — a LOUD reader: it errors on anything it cannot classify rather than silently
    dropping it, then enforces E-NO-CONFIG / E-CONFIG-VERSION.
  * update-config — SURGICAL line edits on a closed allow-list of keys; it never parses-and-reemits
    (which would destroy comments/structure), so unrelated lines stay byte-identical.

Judgment never lives here; and the allow-list structurally cannot write a score/weight field.
"""
from errors import JobSearchError

SUPPORTED_CONFIG_MAJOR = 1

# Closed allow-list of settable scalar keys (dotted). Anything else — including any score/weight
# key — is rejected loudly.
ALLOWED_SET_KEYS = {
    "workspace.preferences_path",
    "search.freshness",
    "search.detail_model",
    "search.parallel_detail_reads",
    "schedule.frequency",
    "schedule.time",
    "schedule.timezone",
    "notify.desktop_notify_on_block",
}


# ---------- scalar coercion + comment stripping ----------

def _coerce_scalar(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s in ("null", "~", ""):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _strip_inline_comment(line):
    """Drop a YAML inline comment (whitespace-preceded #) outside quotes; leave # inside quotes."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in (" ", "\t")):
            return line[:i].rstrip()
    return line


def _split_top_commas(s):
    """Split on commas that are at brace depth 0 and outside quotes (so a comma inside a quoted
    value like \"AI, ML engineer\" does not split the flow-map)."""
    parts, buf, quote, depth = [], [], None, 0
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch == "{":
            depth += 1
            buf.append(ch)
        elif ch == "}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def _parse_flow_map(s):
    s = s.strip()
    if s.startswith("{"):
        s = s[1:]
    if s.endswith("}"):
        s = s[:-1]
    out = {}
    for part in _split_top_commas(s):
        part = part.strip()
        if not part:
            continue
        key, sep, val = part.partition(":")
        if not sep:
            raise JobSearchError("config_parse_error", "malformed flow-map entry: {!r}".format(part))
        out[key.strip()] = _coerce_scalar(val.strip())
    return out


# ---------- load ----------

def parse_config(text):
    """Parse the documented config schema into a dict. Loud: raise on any unclassifiable line."""
    result = {}
    parent = None  # current top-level key whose indented children we are reading
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        if indent == 0:
            key, sep, val = body.partition(":")
            if not sep:
                raise JobSearchError("config_parse_error", "line {}: expected 'key:' ({!r})".format(lineno, raw.strip()))
            key, val = key.strip(), val.strip()
            if val == "":
                parent = key
                result.setdefault(key, None)  # container decided by first child
            else:
                result[key] = _coerce_scalar(val)
                parent = None
        else:
            if parent is None:
                raise JobSearchError("config_parse_error", "line {}: unexpected indent ({!r})".format(lineno, raw.strip()))
            if body.startswith("- "):
                if result.get(parent) is None:
                    result[parent] = []
                item = body[2:].strip()
                result[parent].append(_parse_flow_map(item) if item.startswith("{") else _coerce_scalar(item))
            else:
                if result.get(parent) is None:
                    result[parent] = {}
                key, sep, val = body.partition(":")
                if not sep:
                    raise JobSearchError("config_parse_error", "line {}: expected 'key: value' ({!r})".format(lineno, raw.strip()))
                result[parent][key.strip()] = _coerce_scalar(val.strip())
    return result


def load_config(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        raise JobSearchError("E-NO-CONFIG", "No config.yaml found at {}.".format(path))
    cfg = parse_config(text)
    ver = cfg.get("version")
    if isinstance(ver, int) and ver > SUPPORTED_CONFIG_MAJOR:
        raise JobSearchError("E-CONFIG-VERSION",
                             "config.yaml version {} is newer than supported ({}).".format(ver, SUPPORTED_CONFIG_MAJOR))
    return cfg


# ---------- surgical update ----------

def _format_value(v):
    if v in ("true", "false"):
        return v
    if v.lstrip("-").isdigit():
        return v
    return '"{}"'.format(v)


def _split_after_colon(after):
    """after = text following the first ':' (no trailing newline). Return (lead_ws, value, suffix)
    so the value token can be replaced while suffix (spacing + inline comment) is preserved."""
    i = 0
    while i < len(after) and after[i] == " ":
        i += 1
    lead, rest = after[:i], after[i:]
    if rest[:1] in ('"', "'"):
        q = rest[0]
        j = rest.find(q, 1)
        if j == -1:
            return lead, rest, ""
        return lead, rest[:j + 1], rest[j + 1:]
    end = 0
    while end < len(rest) and rest[end] != " ":
        end += 1
    return lead, rest[:end], rest[end:]


def _replace_value_line(line, new_value):
    nl = "\n" if line.endswith("\n") else ""
    core = line[:-1] if nl else line
    ci = core.index(":")
    head, after = core[:ci + 1], core[ci + 1:]
    lead, _old, suffix = _split_after_colon(after)
    return head + lead + _format_value(new_value) + suffix + nl


def set_scalar(text, dotted_key, value):
    if dotted_key not in ALLOWED_SET_KEYS:
        raise JobSearchError("config_key_not_allowed", "{} is not a settable config key".format(dotted_key))
    top, _, leaf = dotted_key.partition(".")
    lines = text.splitlines(keepends=True)
    in_block = False
    for i, line in enumerate(lines):
        core = line.rstrip("\n")
        indent = len(core) - len(core.lstrip(" "))
        body = core.strip()
        if indent == 0 and body.startswith(top + ":"):
            in_block = True
            continue
        if in_block:
            if indent == 0 and body and not body.startswith("#"):
                break  # left the block without finding the leaf
            if indent > 0 and body.split(":", 1)[0].strip() == leaf:
                lines[i] = _replace_value_line(line, value)
                return "".join(lines)
    raise JobSearchError("config_key_not_found", "{} not found in config.yaml".format(dotted_key))


def add_query(text, query):
    lines = text.splitlines(keepends=True)
    q_start = None
    for i, line in enumerate(lines):
        core = line.rstrip("\n")
        if (len(core) - len(core.lstrip(" "))) == 0 and core.strip().startswith("queries:"):
            q_start = i
            break
    if q_start is None:
        raise JobSearchError("config_no_queries", "no queries: block in config.yaml")
    last, item_indent = None, "  "
    for j in range(q_start + 1, len(lines)):
        core = lines[j].rstrip("\n")
        indent = len(core) - len(core.lstrip(" "))
        body = core.strip()
        if not body or body.startswith("#"):
            continue
        if indent == 0:
            break
        if body.startswith("- "):
            last = j
            item_indent = " " * indent
    new_line = '{}- {{ id: "{}", keywords: "{}", location: "{}", limit: {}, enabled: {} }}\n'.format(
        item_indent, query["id"], query["keywords"], query.get("location", ""),
        int(query.get("limit", 25)), "true" if query.get("enabled", True) else "false")
    insert_at = (last + 1) if last is not None else (q_start + 1)
    if insert_at > 0 and not lines[insert_at - 1].endswith("\n"):
        lines[insert_at - 1] += "\n"
    lines.insert(insert_at, new_line)
    return "".join(lines)
