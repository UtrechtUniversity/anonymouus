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
        self.gt = self.read_gt(gtfile)
        self.labels = self.gt_labels()
        self.raw_text = self.gt['task']['data']['my_text']
        self.keys = self.read_keys(keyfile)
        self.anym_text = self.read_anym(anymdir)

    def read_gt(self, file: Path) -> dict:
        """ Read manually labeled ground truth file """

        with open(file, 'r') as f:
            gt = json.loads(f.read())

        return gt

    def gt_labels(self) -> dict:
        """Extract PII labels from ground truth"""

        gt_labels = {
                    i['value']['text'].strip():
                    {'label': i['value']['labels'][0]}
                    for i in self.gt['result']
                    }

        return gt_labels

    def read_keys(self, file: Path) -> dict:
        """ Read file with PII keys and substitutes"""
        with file.open() as f:
            reader = csv.DictReader(f)
            keys = {row['names']: row['subt'] for row in reader}

        return keys

    def read_anym(self, dir: Path) -> str:
        """ Read all anonymized files"""

        files = list(dir.glob('*.txt'))

        for file in files:
            with open(file, 'r', encoding='utf8') as f:
                anym_text = f.read()

        return anym_text

    def find_key(self, name: str) -> str:
        """Find key(substitute) for a given name"""
        try:
            subt = self.keys[name.strip()]
        except KeyError:
            print(f'No hash for {name}')
            subt = '__NOHASH__'

        return subt

    def count_subt(self, item: str) -> int:
        """Count frequency of substitutes in anonymized text
           for a given PII item"""

        if self.labels[item]['label'] == 'EMAIL':
            subt = '__email'
        elif self.labels[item]['label'] == 'LOC':
            subt = '__location'
        else:  # item is a name
            subt = self.find_key(item)

        freq_subt = len(re.findall(subt, self.anym_text))

        return freq_subt

    def compute_freqs(self, item: str) -> dict:
        """Count frequencies in raw and anonymized text
           per PII item and its substitute"""

        freqs = {}
        # count freq of label in ground truth
        freq_gt = len(re.findall(item, self.raw_text))
        freqs['freq_gt'] = freq_gt

        # count freq of label in anonymized text
        freq_anym = len(re.findall(item, self.anym_text))
        freqs['freq_anym'] = freq_anym

        # count freq of substitute in anonymized text
        freq_subt = self.count_subt(item)
        freqs['freq_subt'] = freq_subt

        return freqs

    def compute_stats(self, item: str) -> dict:
        """ Compute true positives, false positives, false negatives
            per PII item """

        stats = {}
        TP = self.labels[item]['freq_gt'] - self.labels[item]['freq_anym']
        if TP < 0:
            TP = 0
        stats['TP'] = TP

        if self.labels[item]['freq_subt'] > TP:
            self.labels[item]['freq_subt'] = TP
        FP = self.labels[item]['freq_subt'] - TP
        stats['FP'] = FP

        FN = self.labels[item]['freq_anym']
        if FN > self.labels[item]['freq_gt']:
            FN = self.labels[item]['freq_gt']
        stats['FN'] = FN

        return stats

    def validate(self) -> dict:
        """Validate deidentification"""

        for item in self.labels.keys():

            freqs = self.compute_freqs(item)
            self.labels[item].update(freqs)

        # summarize frequencies per label category
        labels_df = pd.DataFrame(self.labels).transpose()
        grp_df = labels_df.groupby('label').sum()
        grp_dict = grp_df.transpose().to_dict()

        for label in grp_dict.keys():
            metrics = self.compute_metrics(label)
            grp_dict[label].update(metrics)

        return grp_dict


def main():
    test_data = Path.cwd()/'anonymouus/tests/test_data'

    parser = argparse.ArgumentParser()
    parser.add_argument("--anymdir", type = Path, help = "Folder with anonymized data",
                        default = test_data / "anonymized")
    parser.add_argument("--gtfile", type = Path, help="Labeled groundtruth file",
                        default = test_data / "labeled.json")
    parser.add_argument("--keyfile", type = Path, help = "Keys file",
                        default = test_data / "keys.csv")
    args = parser.parse_args()

    validator = Validation(args.anymdir, args.gtfile, args.keyfile)
    metrics = validator.validate()


if __name__ == '__main__':
    main()
