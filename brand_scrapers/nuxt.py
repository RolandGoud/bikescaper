"""Read the state a Nuxt page embeds. Nuxt 2 as `window.__NUXT__=(function(a,b,...){...;return {...}}(x,y,...))`.

The state is minified JavaScript, not JSON: strings used more than once are passed in as the
function's arguments, and shared objects are filled by statements (`cY.code=eQ;`) before the
return. This reads that small subset of JavaScript (literals, objects, arrays, `Array(n)`,
`void 0` and member assignments) without running any of it.
"""
import json
import re

_TOKEN = re.compile(r'\s*(?:("(?:[^"\\]|\\.)*")|(\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+)|([A-Za-z_$][\w$]*)|(.))', re.S)
_WORDS = {"true": True, "false": False, "null": None, "undefined": None}


class _Parser:
    def __init__(self, text):
        self.tokens = [(m.group(1), m.group(2), m.group(3), m.group(4))
                       for m in _TOKEN.finditer(text) if any(m.groups())]
        self.i = 0
        self.names = {}

    def peek(self, offset=0):
        i = self.i + offset
        return self.tokens[i] if i < len(self.tokens) else (None, None, None, None)

    def take(self, punct=None):
        tok = self.peek()
        if punct is not None and tok[3] != punct:
            raise ValueError(f"expected {punct!r} at token {self.i}, got {tok}")
        self.i += 1
        return tok

    def is_punct(self, punct):
        return self.peek()[3] == punct

    def value(self):
        string, number, name, punct = self.take()
        if string is not None:
            return json.loads(string)
        if number is not None:
            return float(number) if re.search(r"[.eE]", number) else int(number)
        if name is not None:
            if name == "void":
                self.value()
                return None
            if name == "Array" and self.is_punct("("):
                self.take("(")
                n = self.value()
                self.take(")")
                return [None] * int(n)
            if name in self.names:
                return self.names[name]
            if name in _WORDS:
                return _WORDS[name]
            raise ValueError(f"unknown name {name!r}")
        if punct == "{":
            obj = {}
            while not self.is_punct("}"):
                key_string, key_number, key_name, _ = self.take()
                key = json.loads(key_string) if key_string is not None else (key_name or key_number)
                self.take(":")
                obj[key] = self.value()
                if self.is_punct(","):
                    self.take(",")
            self.take("}")
            return obj
        if punct == "[":
            items = []
            while not self.is_punct("]"):
                items.append(self.value())
                if self.is_punct(","):
                    self.take(",")
            self.take("]")
            return items
        raise ValueError(f"unexpected token {punct!r} at {self.i}")

    def target(self):
        """`a.b.c` or `a[0]` before an `=`: the container and the key to set."""
        container = self.names[self.take()[2]]
        while True:
            if self.is_punct("."):
                self.take(".")
                key = self.take()[2]
            else:
                self.take("[")
                key = self.value()
                self.take("]")
            if self.is_punct("="):
                return container, key
            container = container[key]

    def state(self):
        self.take("(")
        if self.take()[2] != "function":
            raise ValueError("not a Nuxt state function")
        self.take("(")
        params = []
        while not self.is_punct(")"):
            params.append(self.take()[2])
            if self.is_punct(","):
                self.take(",")
        self.take(")")
        self.take("{")
        body_start = self.i
        depth = 1
        while depth:  # skip the body: the arguments come after it
            punct = self.take()[3]
            depth += {"{": 1, "}": -1}.get(punct, 0)
        self.take("(")
        args = []
        while not self.is_punct(")"):
            args.append(self.value())
            if self.is_punct(","):
                self.take(",")
        self.names = dict(zip(params, args + [None] * (len(params) - len(args))))
        self.i = body_start
        while True:
            if self.peek()[2] == "return":
                self.take()
                return self.value()
            container, key = self.target()
            self.take("=")
            container[key] = self.value()
            self.take(";")


def nuxt_state(page):
    """The page's __NUXT__ state as Python data, or None when there is none or it can't be read."""
    start = (page or "").find("window.__NUXT__=")
    if start < 0:
        return None
    end = page.find("</script>", start)
    try:
        return _Parser(page[start + len("window.__NUXT__="):end]).state()
    except (ValueError, KeyError, IndexError, TypeError):
        return None


# Nuxt 3 writes its state as JSON instead (`<script id="__NUXT_DATA__">`), flattened by devalue: one
# array whose numbers point at other entries, with ["Reactive", i] and the like wrapping values.
_WRAPPERS = {"Reactive", "ShallowReactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef", "NuxtError", "Island"}


def _undevalue(table):
    seen = {}

    def value(i):
        if not isinstance(i, int) or isinstance(i, bool):
            return i
        if i < 0:  # devalue's undefined, NaN and infinities
            return None
        if i in seen:
            return seen[i]
        raw = table[i]
        if isinstance(raw, list):
            if raw and isinstance(raw[0], str) and raw[0] in _WRAPPERS:
                seen[i] = value(raw[1]) if len(raw) > 1 else None
                return seen[i]
            if raw and raw[0] == "Date":
                seen[i] = raw[1]
                return seen[i]
            if raw and raw[0] == "Set":
                seen[i] = out = []
                out.extend(value(x) for x in raw[1:])
                return out
            if raw and raw[0] == "Map":
                seen[i] = out = {}
                for k in range(1, len(raw) - 1, 2):
                    out[str(value(raw[k]))] = value(raw[k + 1])
                return out
            seen[i] = out = []
            out.extend(value(x) for x in raw)
            return out
        if isinstance(raw, dict):
            seen[i] = out = {}
            for k, x in raw.items():
                out[k] = value(x)
            return out
        seen[i] = raw
        return raw

    return value(0)


def nuxt_data(page):
    """A Nuxt 3 page's __NUXT_DATA__ as Python data, or None."""
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', page or "", re.S)
    if not m:
        return None
    try:
        table = json.loads(m.group(1))
        return _undevalue(table) if isinstance(table, list) and table else None
    except (ValueError, IndexError, TypeError, RecursionError):
        return None
