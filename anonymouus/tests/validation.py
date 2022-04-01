"""validation of deidentification procedure

Evaluate the performance of the deidentification by comparing it to a labeled ground truth.
To run the validation you need to have the following data present:
* anonymized files 
* key file
* manually labeled ground truth (created with Label Studio)
Examples can be found in the test_data in this folder

NB This code is developed for one file and case-dependent deidentifaction.
Code can be improved by including multiple files+folders and considering case-indepency and word boundaries.

"""

import argparse
import pandas as pd
from pathlib import Path
import re


class Validation:
    """ Validate deidentification by comparing to a labeled ground truth """
    
    def __init__(self):
        pass


def main():
    test_data  = Path.cwd()/'tests/test_data'

    parser = argparse.ArgumentParser()
    parser.add_argument("--anym", "-a", help="Path to folder with anonymized data", 
                        default = test_data/'anonymized')
    parser.add_argument("--gt", "-g", help="Path to labeled groundtruth file", 
                        default = test_data/'labeled.json')
    parser.add_argument("--keys", "-k", help="Path to keys file", 
                        default = test_data/'keys.csv')                                        
    args = parser.parse_args()

    print(args)

if __name__ == '__main__':
    main()