"""validation of deidentification procedure

Evaluate the performance of the deidentification by comparing it to a labeled
ground truth. To run the validation make sure you have these data present:
* anonymized files 
* key file
* manually labeled ground truth (created with Label Studio)
Examples can be found in the test_data in this folder

NB This code is developed for one file and case-dependent deidentifaction.
TODO include multiple files+folders
TODO include case-indepency and word boundaries.

"""

import argparse
import csv
import json
import pandas as pd
from pathlib import Path
import re


class Validation:
    """ Validate deidentification by comparing to a labeled ground truth """
    
    def __init__(self, anymdir, gtfile, keyfile):
        self.gt_labels = self.read_gt(gtfile)
        self.keys = self.read_keys(keyfile)
        self.anym_text = self.read_anym(anymdir)

    def read_gt(self, file):
        """ Read manually labeled ground truth file """

        with open(file, 'r') as f:
            gt_labels = json.loads(f.read())

        return gt_labels

    def read_keys(self, file):
        """ Read file with PII keys and substitutes"""
        with file.open() as f:
            reader = csv.DictReader(f)
            keys = {row['names']: row['subt'] for row in reader}

        return keys    

    def read_anym(self, dir):
        """ Read all anonymized files"""
        
        files = list(dir.glob('*.txt'))

        for file in files:
            with open(file, 'r', encoding='utf8') as f:
                anym_text = f.read()

        return anym_text


def main():
    test_data = Path.cwd()/'tests/test_data'

    parser = argparse.ArgumentParser()
    parser.add_argument("--anymdir", "-a", help="Folder with anonymized data",
                        default=test_data/'anonymized')
    parser.add_argument("--gtfile", "-g", help="Labeled groundtruth file",
                        default=test_data/'labeled.json')
    parser.add_argument("--keyfile", "-k", help="Keys file", 
                        default=test_data/'keys.csv')                                        
    args = parser.parse_args()

    validator = Validation(args.anymdir, args.gtfile, args.keyfile)


if __name__ == '__main__':
    main()