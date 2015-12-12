from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from collections import namedtuple
import inspect
import re

try:
    inspect.signature
except AttributeError:
    def signature(func):
        return inspect.formatargspec(*inspect.getargspec(func))
else:
    def signature(func):
        return str(inspect.signature(func))

RE_TOKENIZE = re.compile(
    '''
    # (name           value   ) postcond | # human-desc
    #  ----           -----     --------     ----------
    (?P<code>         [{]     ) (?![{:]) | # '{' except in '{{' and '{:'
    (?P<xblock_code>  [{]:    )          | # '{:' ends block and starts new code
    (?P<xcode>        [}]     ) (?![}])  | # '}' except in '}}'
    (?P<xcode_block>  :[}]    )          | # ':}' ends current code and starts a new block
    (?P<text_colon>   :       ) (?![}])  | # ':' except in ':}'
    (?P<text_brace>   [{]     ) [{]      | # '{{' but yield only a '{'
    (?P<text_xbrace>  [}]     ) [}]      | # '}}' but yield only a '}'
    (?P<text>         [^{:}]+ )            # anything else
    ''', re.VERBOSE | re.UNICODE).finditer

TEXT = 'text'
COMMENT = 'comment'

Token = namedtuple('Token', 'type value')

def tokenize(line):
    for match in RE_TOKENIZE(line):
        tokens = [
            Token(type, value) for type, value in match.groupdict().items()
            if value is not None]
        assert len(tokens) == 1, tokens
        token = tokens[0]
        if token.type.startswith('text'):
            yield Token(TEXT, token.value)
        else:
            yield token


class State:
    def __init__(self, compiler):
        self.compiler = compiler
        self.fragments = []

    def process(self, token):
        getattr(self, 'process_' + token.type)(token.value)

    def flush(self):
        pass


class StateText(State):
    def process_comment(self, value):
        self.fragments.append(Token(COMMENT, value))
    def process_newline(self, value):
        self.process_text(value)
    def process_text(self, value):
        self.fragments.append(Token(TEXT, value))
    def process_code(self, value):
        self.compiler.enter(StateCode(self.compiler))
    def process_xcode(self, value):
        raise SyntaxError
    def process_xblock_code(self, value):
        self.compiler.enter(StateCode(self.compiler))
        self.compiler.dedent()
    def process_xcode_block(self, value):
        raise SyntaxError

    def flush(self):
        multiline_code = sum(1 for t in self.fragments if t.type == TEXT) > 1
        if multiline_code:
            self.compiler.emit('__text(')
            self.compiler.indent()
            self._flush('{} +')
            self.compiler.emit('"")')
            self.compiler.dedent()
        else:
            self._flush('__text({})')

    def _flush(self, template):
        for t in self.fragments:
            if t.type == TEXT:
                self.compiler.emit(template.format(repr(t.value)))
            else:
                assert t.type == COMMENT
                self.compiler.emit('# ' + t.value.strip())
        self.fragments[:] = []


class StateCode(State):
    expression = True
    def process_comment(self, value):
        self.compiler.emit('# ' + value.strip())
    def process_newline(self, value):
        pass
    def process_text(self, value):
        self.fragments.append(value.strip())
    def process_code(self, value):
        raise SyntaxError
    def process_xcode(self, value):
        self.compiler.enter(StateText(self.compiler))
    def process_xblock_code(self, value):
        raise SyntaxError
    def process_xcode_block(self, value):
        self.expression = False
        self.compiler.enter(StateText(self.compiler))

    def flush(self):
        code = ' '.join(self.fragments)
        if self.expression:
            if code:
                self.compiler.emit('__expr({})'.format(code))
        else:
            assert code
            self.compiler.emit(code + ':')
            self.compiler.indent()
            # ugly in output, but prevents invalid empty blocks
            # and costs nothing when compiled
            # FIXME: protect with test
            self.compiler.emit('pass')
        self.fragments[:] = []
        self.expression = True


class Compiler:
    def __init__(self):
        self.result = []
        self.state = StateText(self)
        self.indentation = 1
        self.lineno = 0

    def enter(self, state):
        self.state.flush()
        self.state = state

    def process(self, line):
        self.lineno += 1
        line = line.strip()
        if line.startswith('# ') or line == '#':
            self.state.process_newline('\n')
            self.process_line(line[2:])
        elif line.startswith('= ') or line == '=':
            self.process_line(line[2:])
        elif line and line[:1] in '#=':
            raise SyntaxError(
                'Invalid template line {} - missing space after {}?'
                .format(self.lineno, line[0])
                + '\n' + line)
        else:
            self.state.process_comment(line)

    def process_line(self, line):
        tokens = list(tokenize(line))
        if not all(t.type == TEXT for t in tokens):
            self.state.process_comment(line)
        for t in tokens:
            self.state.process(t)

    def indent(self):
        self.indentation += 1
    def dedent(self):
        assert self.indentation > 1
        self.indentation -= 1
    def emit(self, line):
        self.result.append(' ' * 4 * self.indentation + line)

    def get_source(self):
        self.state.flush()
        return '\n'.join(self.result)


DEFUN = '''\
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
def {}{}:
    __fragments = []
    __text = __fragments.append
    __unicode = u''.__class__
    def __expr(__value):
       # ignore None to be able to define & use local functions
       if __value is not None:
           __text(__unicode(__value))
    # - - - - - - - - - - - - - -
'''
ENDFUN = '''
    # - - - - - - - - - - - - - -
    return u''.join(__fragments)
'''


def _compile_doc(f):
    c = Compiler()
    for line in f.__doc__.splitlines():
        c.process(line)
    source = (
        DEFUN.format(f.__name__, str(signature(f))) +
        c.get_source() +
        ENDFUN)
    return source


def form(fun):
    '''
        Create a function that return a string defined by the doc-string.

        The returned function will have the same signature as the input.
    '''
    source = _compile_doc(fun)
    env = {}
    exec(source, fun.__globals__, env)
    form_fun = env[fun.__name__]
    form_fun.source = source
    form_fun.__doc__ = fun.__doc__
    form_fun.__module__ = '{}/{}'.format(fun.__module__, fun.__name__)
    return form_fun
