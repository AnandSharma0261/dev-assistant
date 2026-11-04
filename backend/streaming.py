# ============================================================
#  Helpers to turn a model's growing output into small SSE deltas.
# ============================================================

import re

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", '"': '"', "\\": "\\", "/": "/"}


def partial_json_string(text, key):
    """
    Decoded value of string field `key` from a JSON object that is still being
    streamed (so it may end mid-string or mid-escape). Returns None until the
    field has started. The returned prefix only ever grows as text is added.
    """
    m = re.search(r'"%s"\s*:\s*"' % re.escape(key), text)
    if not m:
        return None
    raw, out, i = text[m.end():], [], 0
    while i < len(raw):
        c = raw[i]
        if c == '"':
            break                          # end of the string value
        if c != "\\":
            out.append(c)
            i += 1
            continue
        if i + 1 >= len(raw):
            break                          # escape cut off: wait for more text
        n = raw[i + 1]
        if n != "u":
            out.append(_ESCAPES.get(n, n))
            i += 2
            continue
        if i + 6 > len(raw):
            break
        try:
            code = int(raw[i + 2:i + 6], 16)
        except ValueError:
            break
        if 0xD800 <= code < 0xDC00:        # surrogate pair: needs the second half
            if i + 12 > len(raw):
                break
            try:
                low = int(raw[i + 8:i + 12], 16)
            except ValueError:
                break
            out.append(chr(0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)))
            i += 12
            continue
        out.append(chr(code))
        i += 6
    return "".join(out)


class DeltaEmitter:
    """
    Use as gemini_helper's on_text callback. Turns "full text so far" into
    {"append": "..."} deltas (so the stream stays small) and {"reset": true}
    when a retry starts over. `extract` optionally maps the raw text to what
    should be shown (e.g. just the code field of a JSON answer).
    """

    def __init__(self, send, extract=None):
        self.send = send
        self.extract = extract
        self.sent = ""

    def __call__(self, full_text):
        text = self.extract(full_text) if (self.extract and full_text) else full_text
        if text is None:
            return
        if not text.startswith(self.sent):   # retry (""), or output changed
            self.sent = ""
            self.send({"reset": True})
        delta = text[len(self.sent):]
        if delta:
            self.sent = text
            self.send({"append": delta})
