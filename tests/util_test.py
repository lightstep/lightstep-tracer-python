import sys
import unittest

from lightstep import util

class UtilTest(unittest.TestCase):
    
    def test_merge_dicts(self):
        self.assertEqual(None, util._merge_dicts())
        self.assertEqual(None, util._merge_dicts(None))
        self.assertEqual(None, util._merge_dicts(None, None))
        self.assertEqual(None, util._merge_dicts({}))
        self.assertEqual(None, util._merge_dicts({}, {}))
        self.assertEqual(None, util._merge_dicts({}, None, {}, None))

        self.assertEqual({'a': 'b'}, util._merge_dicts({'a': 'b'}))
        self.assertEqual({'a': 'b', 'c': 'd'}, util._merge_dicts({'a': 'b'},{'c': 'd'}))
        self.assertEqual({'a': 'b', 'c': 'd', 'e': 'f'}, util._merge_dicts({'a': 'b','c': 'd'},{'e': 'f'}))
        self.assertEqual({'a': 'b', 'c': 'd', 'e': 'f'}, util._merge_dicts({}, {'a': 'b','c': 'd'}, None, {'e': 'f'}))

        self.assertEqual({'a': 'c', 'e': 'f'}, util._merge_dicts({'a': 'b', 'e': 'f'}, {'a': 'c'}))
    
    def test_coerce_str(self):
        # For Python 2, we expect ascii values (bytes).
        # For Python 3, we expect utf-8 values.

        if sys.version_info[0] == 2:
            self.assertEqual('str', util._coerce_str('str'))
            self.assertEqual('unicode', util._coerce_str(u'unicode'))
            self.assertEqual('hard unicode char: \xe2\x80\x8b', util._coerce_str(u'hard unicode char: \u200b'))
        else:
            self.assertEqual('str', util._coerce_str(b'str'))
            self.assertEqual('unicode', util._coerce_str('unicode'))
            self.assertEqual('hard unicode char: \u200b', util._coerce_str(b'hard unicode char: \xe2\x80\x8b'))


if __name__ == '__main__':
    unittest.main()
