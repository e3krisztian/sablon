from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from . import DocCompiler


unicode = u''.__class__


class HTML(unicode):
    is_html_safe = True

HTML_ESCAPE_MAP = dict(
    (ord(dangerous), safe)
    for dangerous, safe in (
        (u'&', u'&amp;'),
        (u'"', u'&quot;'),
        (u"'", u'&apos;'),
        (u'>', u'&gt;'),
        (u'<', u'&lt;')))


def wrap(obj):
    try:
        if obj.is_html_safe and isinstance(obj, unicode):
            return obj
    except AttributeError:
        pass
    return HTML(unicode(obj).translate(HTML_ESCAPE_MAP))


class HtmlDocCompiler(DocCompiler):
    DEFINE_WRAPS = 'from sablon.html import HTML as __html, wrap as __html_safe'
    WRAP_EXPR = '__html_safe'
    WRAP_RESULT = '__html'


def html_sablon(fun):
    '''
        Create a function that return a string defined by the doc-string.

        The returned function will have the same signature as the input.
    '''
    return HtmlDocCompiler().compile(fun)
