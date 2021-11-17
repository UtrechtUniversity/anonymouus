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

# Expected answers
exp =        ['aaaa','JaneDoe','amsterdam','cccc','dddd','ddddpillar']
exp_case =   ['aaaa','JaneDoe','bbbb','cccc','dddd','ddddpillar']
exp_bounds = ['aaaa','JaneDoe','amsterdam','cccc','dddd','caterpillar']

@pytest.mark.parametrize('anym_object,expected',[
                            ('reg',exp),
                            ('case',exp_case),
                            ('bounds',exp_bounds)
                            ],
                        indirect = True
                        )
def test_substitute(anym_object,expected):
    """Test substitution of strings"""

    res = [anym_object._substitute_ids(s) for s in ids]
    assert res == expected



# #@pytest.mark.parametrize("keys",[key_csv,key_dict])
# @pytest.mark.parametrize("option,expected",[
#                             (anym,exp),
#                             (anym_case,exp_case),
#                             (anym_bounds,exp_bounds)
#                             ]
#                         )
# def test_substitute(option,expected):
#     """Test substitution of strings"""

#     anym = Anonymize(key_csv,option)
#     res = [anym._substitute_ids(s) for s in ids]
#     assert res == expected


# def test_regular():
#     """Test regular substitution of strings, without user options or flags"""

#     anym = Anonymize(key_csv)

#     res = [anym._substitute_ids(s) for s in ids]
#     exp = [
#         'aaaa',
#         'JaneDoe',
#         'amsterdam',
#         'cccc',
#         'dddd',
#         'ddddpillar']

#     assert res == exp

# def test_ignore_case(key_csv):
#     """Test case-independent substitution of strings, without user options or flags"""

#     anym = Anonymize(key_csv,flags=re.IGNORECASE)

#     res = [anym._substitute_ids(s) for s in ids]
#     exp = [
#         'aaaa',
#         'JaneDoe',
#         'bbbb',
#         'cccc',
#         'dddd',
#         'ddddpillar']

#     assert res == exp

# def test_word_boundaries(key_csv):
    # """Test case-independent substitution of strings, without user options or flags"""

    # anym = Anonymize(key_csv,use_word_boundaries=True)

    # res = [anym._substitute_ids(s) for s in ids]
    # exp = [
    #     'aaaa',
    #     'JaneDoe',
    #     'amsterdam',
    #     'cccc',
    #     'dddd',
    #     'caterpillar']

    # assert res == exp