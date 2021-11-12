'''
Test the core of the anonymoUUs package: substitution of strings
'''
import pytest
from pathlib import Path
from anonymouus.anonymouus import Anonymize

# names,subt
# Jane Doe,aaaa
# Amsterdam,bbbb
# j.doe@gmail.com,cccc
# r#ca.*?er,dddd

@pytest.fixture(autouse=True,scope="class")
def anym_object():
    """Instantiate Anonymize class with test data; created object is used in all tests"""
    keys = Path.cwd()/'tests/test_data/keys.csv'
    anym = Anonymize(keys)

    return anym

def test_sub_regular(anym_object):
    """Test regular substitution of strings, without user options or flags"""
    strings = [
        'Jane Doe',
        'JaneDoe', 
        'amsterdam',
        'j.doe@gmail.com',
        'casper',
        'caterpillar']

    res = [anym_object._substitute_ids(s) for s in strings]
    exp = [
        'aaaa',
        'JaneDoe',
        'amsterdam',
        'cccc',
        'dddd',
        'ddddpillar']

    assert res == exp
