'''
Test the core of the anonymoUUs package: substitution of strings
'''

import pytest
from pathlib import Path
import re
from anonymouus.anonymouus import Anonymize

# Options for providing keys and replacement values
key_csv = Path.cwd()/'tests/test_data/keys.csv'
key_dict = {
'Jane Doe': 'aaaa',
'Amsterdam':'bbbb',
'j.doe@gmail.com':'cccc',
re.compile('ca.*?er'):'dddd'
} 

# Input data for testing
ids = [
    'Jane Doe',
    'JaneDoe', 
    'amsterdam',
    'j.doe@gmail.com',
    'casper',
    'caterpillar']

# Expected answers
exp_orig =        ['aaaa','JaneDoe','amsterdam','cccc','dddd','ddddpillar']
exp_case =   ['aaaa','JaneDoe','bbbb','cccc','dddd','ddddpillar']
exp_bounds = ['aaaa','JaneDoe','amsterdam','cccc','dddd','caterpillar']


opt_exp = {'orig':[0,False,exp_orig],
           'case':[re.IGNORECASE,False,exp_case],
           'bounds':[0,True,exp_bounds]
            }

@pytest.mark.parametrize('opts',[
                                opt_exp['orig'],
                                opt_exp['case'],
                                opt_exp['bounds']
                                ]
                            )
@pytest.mark.parametrize('keys',[  
                                key_csv,
                                key_dict                      
                                ]
                            )
def test_substitute(keys,opts):
    """Test substitution of strings"""

    anym = Anonymize(keys,flags=opts[0],use_word_boundaries=opts[1])
    res = [anym._substitute_ids(s) for s in ids]
    assert res == opts[2]