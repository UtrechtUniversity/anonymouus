'''
Test the core of the anonymoUUs package: substitution of strings
'''
import pytest
from pathlib import Path
import re
from anonymouus.anonymouus import Anonymize

# names,subt
# Jane Doe,aaaa
# Amsterdam,bbbb
# j.doe@gmail.com,cccc
# r#ca.*?er,dddd

# Input data for testing
ids = [
    'Jane Doe',
    'JaneDoe', 
    'amsterdam',
    'j.doe@gmail.com',
    'casper',
    'caterpillar']

keys = Path.cwd()/'tests/test_data/keys.csv'


def test_regular():
    """Test regular substitution of strings, without user options or flags"""

    anym = Anonymize(keys)

    res = [anym._substitute_ids(s) for s in ids]
    exp = [
        'aaaa',
        'JaneDoe',
        'amsterdam',
        'cccc',
        'dddd',
        'ddddpillar']

    assert res == exp

def test_ignore_case():
    """Test case-independent substitution of strings, without user options or flags"""

    anym = Anonymize(keys,flags=re.IGNORECASE)

    res = [anym._substitute_ids(s) for s in ids]
    exp = [
        'aaaa',
        'JaneDoe',
        'bbbb',
        'cccc',
        'dddd',
        'ddddpillar']

    assert res == exp

def test_word_boundaries():
    """Test case-independent substitution of strings, without user options or flags"""

    anym = Anonymize(keys,use_word_boundaries=True)

    res = [anym._substitute_ids(s) for s in ids]
    exp = [
        'aaaa',
        'JaneDoe',
        'amsterdam',
        'cccc',
        'dddd',
        'caterpillar']

    assert res == exp