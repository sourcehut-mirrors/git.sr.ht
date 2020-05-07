from pygments.formatter import Formatter
from pygments.token import Token, STANDARD_TYPES
from srht.markdown import markdown
from urllib.parse import urlparse

_escape_html_table = {
    ord('&'): u'&amp;',
    ord('<'): u'&lt;',
    ord('>'): u'&gt;',
    ord('"'): u'&quot;',
    ord("'"): u'&#39;',
}

def escape_html(text, table=_escape_html_table):
    return text.translate(table)

def _get_ttype_class(ttype):
    fname = STANDARD_TYPES.get(ttype)
    if fname:
        return fname
    aname = ''
    while fname is None:
        aname = '-' + ttype[-1] + aname
        ttype = ttype.parent
        fname = STANDARD_TYPES.get(ttype)
    return fname + aname

# Fork of the pygments HtmlFormatter (BSD licensed)
# The main difference is that it relies on AnnotatedFormatter to escape the
# HTML tags in the source. Other features we don't use are removed to keep it
# slim.
class _BaseFormatter(Formatter):
    def __init__(self):
        super().__init__()
        self._create_stylesheet()

    def get_style_defs(self, arg=None):
        """
        Return CSS style definitions for the classes produced by the current
        highlighting style. ``arg`` can be a string or list of selectors to
        insert before the token type classes.
        """
        if arg is None:
            arg = ".highlight"
        if isinstance(arg, str):
            args = [arg]
        else:
            args = list(arg)

        def prefix(cls):
            if cls:
                cls = '.' + cls
            tmp = []
            for arg in args:
                tmp.append((arg and arg + ' ' or '') + cls)
            return ', '.join(tmp)

        styles = [(level, ttype, cls, style)
                  for cls, (style, ttype, level) in self.class2style.items()
                  if cls and style]
        styles.sort()
        lines = ['%s { %s } /* %s */' % (prefix(cls), style, repr(ttype)[6:])
                 for (level, ttype, cls, style) in styles]
        return '\n'.join(lines)

    def _get_css_class(self, ttype):
        """Return the css class of this token type prefixed with
        the classprefix option."""
        ttypeclass = _get_ttype_class(ttype)
        if ttypeclass:
            return ttypeclass
        return ''

    def _get_css_classes(self, ttype):
        """Return the css classes of this token type prefixed with
        the classprefix option."""
        cls = self._get_css_class(ttype)
        while ttype not in STANDARD_TYPES:
            ttype = ttype.parent
            cls = self._get_css_class(ttype) + ' ' + cls
        return cls

    def _create_stylesheet(self):
        t2c = self.ttype2class = {Token: ''}
        c2s = self.class2style = {}
        for ttype, ndef in self.style:
            name = self._get_css_class(ttype)
            style = ''
            if ndef['color']:
                style += 'color: #%s; ' % ndef['color']
            if ndef['bold']:
                style += 'font-weight: bold; '
            if ndef['italic']:
                style += 'font-style: italic; '
            if ndef['underline']:
                style += 'text-decoration: underline; '
            if ndef['bgcolor']:
                style += 'background-color: #%s; ' % ndef['bgcolor']
            if ndef['border']:
                style += 'border: 1px solid #%s; ' % ndef['border']
            if style:
                t2c[ttype] = name
                # save len(ttype) to enable ordering the styles by
                # hierarchy (necessary for CSS cascading rules!)
                c2s[name] = (style[:-2], ttype, len(ttype))

    def _format_lines(self, tokensource):
        lsep = "\n"
        # for <span style=""> lookup only
        getcls = self.ttype2class.get
        c2s = self.class2style

        lspan = ''
        line = []
        for ttype, value in tokensource:
            cls = self._get_css_classes(ttype)
            cspan = cls and '<span class="%s">' % cls or ''

            parts = value.split('\n')

            # for all but the last line
            for part in parts[:-1]:
                if line:
                    if lspan != cspan:
                        line.extend(((lspan and '</span>'), cspan, part,
                                     (cspan and '</span>'), lsep))
                    else:  # both are the same
                        line.extend((part, (lspan and '</span>'), lsep))
                    yield 1, ''.join(line)
                    line = []
                elif part:
                    yield 1, ''.join((cspan, part, (cspan and '</span>'), lsep))
                else:
                    yield 1, lsep
            # for the last line
            if line and parts[-1]:
                if lspan != cspan:
                    line.extend(((lspan and '</span>'), cspan, parts[-1]))
                    lspan = cspan
                else:
                    line.append(parts[-1])
            elif parts[-1]:
                line = [cspan, parts[-1]]
                lspan = cspan
            # else we neither have to open a new span nor set lspan

        if line:
            line.extend(((lspan and '</span>'), lsep))
            yield 1, ''.join(line)

    def _wrap_div(self, inner):
        yield 0, f"<div class='highlight'>"
        for tup in inner:
            yield tup
        yield 0, '</div>\n'

    def _wrap_pre(self, inner):
        yield 0, '<pre><span></span>'
        for tup in inner:
            yield tup
        yield 0, '</pre>'

    def wrap(self, source, outfile):
        """
        Wrap the ``source``, which is a generator yielding
        individual lines, in custom generators. See docstring
        for `format`. Can be overridden.
        """
        return self._wrap_div(self._wrap_pre(source))

    def format_unencoded(self, tokensource, outfile):
        source = self._format_lines(tokensource)
        source = self.wrap(source, outfile)
        for t, piece in source:
            outfile.write(piece)

def validate_annotation(valid, anno):
    valid.expect("type" in anno, "'type' is required")
    if not valid.ok:
        return
    valid.expect(anno["type"] in ["link", "markdown"],
            f"'{anno['type']} is not a valid annotation type'")
    if anno["type"] == "link":
        for field in ["lineno", "colno", "len"]:
            valid.expect(field in anno, "f'{field}' is required")
            valid.expect(field not in anno or isinstance(anno[field], int),
                    "f'{field}' must be an integer")
        valid.expect("to" in anno, "'to' is required")
        valid.expect("title" not in anno or isinstance(anno["title"], str),
                "'title' must be a string")
        valid.expect("color" not in anno or isinstance(anno["color"], str),
                "'color' must be a string")
        if "color" in anno and anno["color"] != "transparent":
            valid.expect("color" not in anno or len(anno["color"]) == 7,
                    "'color' must be a 7 digit string or 'transparent'")
            valid.expect("color" not in anno or not any(
                c for c in anno["color"].lower() if c not in "#0123456789abcdef"),
                    "'color' must be in hexadecimal or 'transparent'")
    elif anno["type"] == "markdown":
        for field in ["lineno"]:
            valid.expect(field in anno, "f'{field}' is required")
            valid.expect(field not in anno or isinstance(anno[field], int),
                    "f'{field}' must be an integer")
        for field in ["title", "content"]:
            valid.expect(field in anno, "f'{field}' is required")
            valid.expect(field not in anno or isinstance(anno[field], str),
                    "f'{field}' must be a string")

class AnnotatedFormatter(_BaseFormatter):
    def __init__(self, get_annos, link_prefix):
        super().__init__()
        self.get_annos = get_annos
        self.link_prefix = link_prefix

    @property
    def annos(self):
        if hasattr(self, "_annos"):
            return self._annos
        self._annos = dict()
        for anno in (self.get_annos() or list()):
            lineno = int(anno["lineno"])
            self._annos.setdefault(lineno, list())
            self._annos[lineno].append(anno)
            self._annos[lineno] = sorted(self._annos[lineno],
                    key=lambda anno: anno.get("from", -1))
        return self._annos

    def _annotate_token(self, token, colno, annos):
        # TODO: Extend this to support >1 anno per token
        for anno in annos:
            if anno["type"] == "link":
                start = anno["colno"] - 1
                end = anno["colno"] + anno["len"] - 1
                target = anno["to"]
                title = anno.get("title", "")
                color = anno.get("color", None)
                url = urlparse(target)
                if url.scheme == "":
                    target = self.link_prefix + "/" + target
                if start <= colno < end:
                    if color is not None:
                        return (f"<a class='annotation' title='{escape_html(title)}' " +
                            f"href='{escape_html(target)}' " +
                            f"rel='nofollow noopener' " +
                            f"style='background-color: {color}' " +
                            f">{escape_html(token)}</a>""")
                    else:
                        return (f"<a class='annotation' title='{escape_html(title)}' " +
                            f"href='{escape_html(target)}' " +
                            f"rel='nofollow noopener' " +
                            f">{escape_html(token)}</a>""")
            elif anno["type"] == "markdown":
                if "\n" not in token:
                    continue
                title = anno["title"]
                content = anno["content"]
                content = markdown(content, baselevel=6,
                        link_prefix=self.link_prefix)
                annotation = f"<details><summary>{escape_html(title)}</summary>{content}</details>\n"
                token = escape_html(token).replace("\n", annotation, 1)
                return token
            # Other types?
        return escape_html(token)

    def _wrap_source(self, source):
        lineno = 0
        colno = 0
        for ttype, token in source:
            parts = token.splitlines(True)
            _lineno = lineno
            for part in parts:
                annos = self.annos.get(_lineno + 1, [])
                if any(annos):
                    yield ttype, self._annotate_token(part, colno, annos)
                else:
                    yield ttype, escape_html(part)
                _lineno += 1
            if "\n" in token:
                lineno += sum(1 if c == "\n" else 0 for c in token)
                colno = len(token[token.rindex("\n")+1:])
            else:
                colno += len(token)

    def _format_lines(self, source):
        yield from super()._format_lines(self._wrap_source(source))
