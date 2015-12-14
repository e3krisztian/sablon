from __future__ import unicode_literals
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import unittest
from sablon.html import html_sablon, HTML


def indent(text):
    indent = '  '
    keepends = True
    return HTML(indent + indent.join(text.splitlines(keepends)))


@html_sablon
def cell(value):
    '''
    = <td>{value}</td>
    '''


@html_sablon
def html_row(values):
    '''
    = <tr>
    = {for value in values:}
    # {indent(cell(value))}
    = {:}
    # </tr>
    '''


@html_sablon
def html_table(rows):
    '''
    = <table>
    = {for row in rows:}
    # {indent(html_row(row))}
    = {:}
    # </table>
    '''


@html_sablon
def html_table_with_macros(rows):
    '''
    = {def cell(value):}
    =     <td>{value}</td>
    = {:}

    = {def html_row(values):}
    =   <tr>
    = {for value in values:}
    # {cell(value)}
    = {:}
    #   </tr>
    = {:}

    = <table>
    = {for row in rows:}
    # {html_row(row)}
    = {:}
    # </table>
    '''


result = '''\
<table>
  <tr>
    <td>Lorem</td>
    <td>ipsum</td>
    <td>dolor</td>
  </tr>
  <tr>
    <td>sit</td>
    <td>amet,</td>
    <td>quote-&lt;</td>
  </tr>
</table>'''


class Test(unittest.TestCase):

    def test(self):
        rows = ['Lorem ipsum dolor'.split(), 'sit amet, quote-<'.split()]
        self.assertEqual(result, html_table(rows))

    def test_macros(self):
        rows = ['Lorem ipsum dolor'.split(), 'sit amet, quote-<'.split()]
        self.assertEqual(result, html_table_with_macros(rows))


if __name__ == '__main__':
    unittest.main()
