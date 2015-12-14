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
            self.compiler.emit('__output(')
            self.compiler.indent()
            self._flush('{} +')
            self.compiler.emit('"")')
            self.compiler.dedent()
        else:
            self._flush('__output({})')

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
                self.compiler.emit('__output_value({})'.format(code))
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


class DocCompiler:

    # Override these string constants in subclasses to escape expression values
    # See html module for an example
    # These strings must not contain new lines!

    DEFINE_WRAPS = '__unicode = u"".__class__'
    WRAP_EXPR = '__unicode'
    WRAP_RESULT = ''

    # implementation
    #
    # generate function source from doc-string using a finite state-machine
    # with one state for text and one for code (within {})

    def reset(self, minindent):
        self.result = []
        self.state = StateText(self)
        self.indentation = self.minindent = minindent
        self.lineno = 0

    def enter(self, state):
        self.state.flush()
        self.state = state

    def process(self, raw_line):
        self.lineno += 1
        line = raw_line.strip()
        if line.startswith('# ') or line == '#':
            self.state.process_newline('\n')
            self.process_line(line[2:])
        elif line.startswith('= ') or line == '=':
            self.process_line(line[2:])
        elif line and line[:1] in '#=':
            raise SyntaxError(
                'Invalid template line {} - missing space after {}?'
                .format(self.lineno, line[0])
                + '\n' + raw_line)
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
        assert self.indentation > self.minindent
        self.indentation -= 1
    def emit(self, line):
        self.result.append(' ' * 4 * self.indentation + line)

    def get_source(self, fun):
        self.reset(minindent=2)
        context = dict(
            func_name=fun.__name__,
            signature=str(signature(fun)),
            define_wraps=self.DEFINE_WRAPS,
            wrap_expr=self.WRAP_EXPR,
            wrap_result=self.WRAP_RESULT)
        self.result = [DEFUN.format(**context)]
        for line in fun.__doc__.splitlines():
            self.process(line)
        self.state.flush()
        self.result.append(ENDFUN.format(**context))
        return '\n'.join(self.result)

    def compile(self, fun):
        '''
            Create a function that return a string defined by the doc-string.

            The returned function will have the same signature as the input.
        '''
        source = self.get_source(fun)
        env = {}
        try:
            exec(source, fun.__globals__, env)
        except SyntaxError as e:
            context = (inspect.getsourcefile(fun), e.lineno, e.offset, source)
            raise SyntaxError(e.msg, context)
        sablon_fun = env[fun.__name__]
        sablon_fun.source = source
        sablon_fun.__name__ = fun.__name__
        sablon_fun.__doc__ = fun.__doc__
        sablon_fun.__module__ = '{}/{}'.format(fun.__module__, fun.__name__)
        return sablon_fun


DEFUN = '''\
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
def __make_sablon():
    {define_wraps}
    def {func_name}{signature}:
        __fragments = []
        __output = __fragments.append
        def __output_value(__value):
           # ignore None to be able to define & use local functions
           if __value is not None:
               __output({wrap_expr}(__value))
        # - - - - - - - - - - - - - -\
'''
ENDFUN = '''\
        # - - - - - - - - - - - - - -
        return {wrap_result}(u''.join(__fragments))
    return {func_name}

{func_name} = __make_sablon()
'''


def sablon(fun):
    '''
        Create a function that return a string defined by the doc-string.

        The returned function will have the same signature as the input.
    '''
    return DocCompiler().compile(fun)
