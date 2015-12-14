from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import unittest
import form as m


class Test_tokenize(unittest.TestCase):

    def assert_tokens(self, tokens, line):
        self.assertEqual(tokens, list(m.tokenize(line)))

    def test_text(self):
        self.assert_tokens([('text', 'some text')], 'some text')

    def test_empty(self):
        self.assert_tokens([], '')

    def test_text_with_escaped_braces(self):
        self.assert_tokens(
            [
                ('text', 'some '), ('text', '{'), ('text', ' text '), ('text', '}'),
            ],
            'some {{ text }}')

    def test_expr_block(self):
        self.assert_tokens(
            [
                ('text', 'some '),
                ('code', '{'), ('text', 'variable'), ('xcode', '}'),
                ('text', ' substitution'),
            ],
            'some {variable} substitution')

    def test_code_block(self):
        self.assert_tokens(
            [
                ('text', 'conditional'), ('text', ':'), ('text', ' '),
                ('code', '{'), ('text', 'if cond'), ('xcode_block', ':}'),
                ('text', ' substitution '),
                ('xblock_code', '{:'), ('text', 'else'), ('xcode_block', ':}'),
                ('text', ' alternative '),
                ('xblock_code', '{:'), ('xcode', '}'),
            ],
            'conditional: {if cond:} substitution {:else:} alternative {:}')


class Test_form(unittest.TestCase):

    def test_empty(self):
        @m.form
        def f():
            ''
        self.assertEqual('', f())

    def test_empty_with_comment(self):
        @m.form
        def f():
            'empty text - this line is a comment'
        self.assertEqual('', f())

    def test_text(self):
        @m.form
        def f():
            '''
            # text on a new line
            '''
        self.assertEqual('\ntext on a new line', f())

    def test_skipping_newline_before_text(self):
        @m.form
        def f():
            '''
            # line
            =  continuation
            '''
        self.assertEqual('\nline continuation', f())

    def test_one_word_on_two_lines(self):
        @m.form
        def f():
            '''
            = wo
            = rd
            '''
        self.assertEqual('word', f())

    def test_lines(self):
        @m.form
        def f():
            '''
            # two
            comment
            # lines
            '''
        self.assertEqual('\ntwo\nlines', f())

    def test_insert_expression(self):
        @m.form
        def inc(n):
            '''
            = {n} + 1 = {n + 1}
            '''
        self.assertEqual('1 + 1 = 2', inc(1))
        self.assertEqual('2 + 1 = 3', inc(2))

    def test_code_blocks_and_recursion(self):
        # see definition of binary below
        self.assertEqual('0', binary(0))
        self.assertEqual('1', binary(1))
        self.assertEqual('11', binary(3))
        self.assertEqual('1101', binary(13))
        self.assertEqual('1010', binary(10))
        self.assertEqual('10000000', binary(128))

    def test_code_formatting(self):
        # see definition of binary and binary_expanded below
        self.assertEqual(binary(0), binary_expanded(0))
        self.assertEqual(binary(1), binary_expanded(1))
        self.assertEqual(binary(3), binary_expanded(3))
        self.assertEqual(binary(13), binary_expanded(13))
        self.assertEqual(binary(10), binary_expanded(10))
        self.assertEqual(binary(128), binary_expanded(128))

    def test_methods(self):
        class SomeView:
            @m.form
            def one(self):
                '= 1'
            @m.form
            def two(self):
                '= ({self.one()} + {self.one()})'
            @m.form
            def five(self):
                '= ({self.two()} + {self.two()} + {self.one()})'
        self.assertEqual('((1 + 1) + (1 + 1) + 1)', SomeView().five())

    def test_local_forms(self):
        @m.form
        def f(str):
            '''
                r is a local function that reverses a string

            = {def r(s):}{''.join(reversed(s))}{:}

                r can be used from now on:

            = {str} reversed is {r(str)}
            '''
        self.assertEqual('asd reversed is dsa', f('asd'))

# Functions referencing each other (or themselves) by name
# is unfortunately possible only if they are defined in global scope.
#
# Alternatively they can call each other through an object
# e.g. through self: see test_methods above

@m.form
def binary(n):
    '''
    = {if n // 2 :}{binary(n // 2)}{:}{n % 2}
    '''


@m.form
def binary_expanded(n):
    # same as `binary` above but with some comments
    # and spread over multiple lines
    '''
    = {if n // 2 :}{

        within code blocks whitespaces (including newlines) are ignored
        so it does not matter if we start the line with # or =

    #     binary(n // 2)
    # }{:}

        choosing line start characters do matter outside code blocks

    = {n % 2}
    '''


if __name__ == '__main__':
    unittest.main()
