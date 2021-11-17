"""File that holds all fixtures to be used in pytest tests """

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


@pytest.fixture(scope="module")
def anym_object(request):
    print("\nAnonymize object created with key csv")
    if request.param == 'reg':
        anym_obj = Anonymize(key_csv)
        return anym_obj
    elif request.param == 'case':
        anym_case = Anonymize(key_csv,flags=re.IGNORECASE)
        return anym_case
    elif request.param == 'bounds':
        anym_bounds = Anonymize(key_csv,use_word_boundaries=True)
        return anym_bounds



