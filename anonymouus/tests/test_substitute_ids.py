'''
Test the core of the anonymoUUs package: substitution of strings
'''
import pytest
from pathlib import Path
import re
from anonymouus.anonymouus import Anonymize

# Input data for testing
ids = [
    'Jane Doe',
    'JaneDoe', 
    'amsterdam',
    'j.doe@gmail.com',
    'casper',
    'caterpillar']

# Options for providing keys and replacement values
key_csv = Path.cwd()/'tests/test_data/keys.csv'
key_dict = {
'Jane Doe': 'aaaa',
'Amsterdam':'bbbb',
'j.doe@gmail.com':'cccc',
re.compile('ca.*?er'):'dddd'
} 

# Anonymize instances 
anym = Anonymize(keys)
anym_case = Anonymize(keys,flags=re.IGNORECASE)
anym_bounds = Anonymize(keys,use_word_boundaries=True)

# Expected answers
exp =        ['aaaa','JaneDoe','amsterdam','cccc','dddd','ddddpillar']
exp_case =   ['aaaa','JaneDoe','bbbb','cccc','dddd','ddddpillar']
exp_bounds = ['aaaa','JaneDoe','amsterdam','cccc','dddd','caterpillar']


def test_substitute(anym,expected):
    """Test substitution of strings"""

    res = [anym._substitute_ids(s) for s in ids]
    assert res == exp





@pytest.fixture
def anym_object(request):
    """Create Anonymize object"""
    return Anonymize(request.param)

@pytest.mark.parametrize(
    'anym_object',
    ([1, 2, 3], [2, 4, 6], [6, 8, 10]),
    indirect=True
)




@pytest.mark.parametrize('keys', [key_csv,key_dict])
def test_regular(keys):
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

@pytest.mark.parametrize('keys', [key_csv,key_dict])
def test_ignore_case(keys):
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

def test_word_boundaries(keys):
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