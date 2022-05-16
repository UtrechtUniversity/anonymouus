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
import logging
import pandas as pd
from pathlib import Path
import re


class Validation:
    """ Validate deidentification of text files
        by comparing to a labeled ground truth
    """

    def __init__(self, anymdir: Path, gtfile: Path, keyfile: Path):
        self.gt = self._read_gt(gtfile)
        self.labels = self._gt_labels()
        self.raw_text = self.gt['task']['data']['my_text']
        self.substitutes = self._read_keys(keyfile)
        self.anym_text = self._read_anym(anymdir)

    def _read_gt(self, file: Path) -> dict:
        """Read manually labeled ground truth file

        Parameters
        ----------
        file : Path
            path to labeled ground truth file (.json)

        Returns
        -------
        dict
            _description_
        """

        with open(file, 'r') as f:
            gt = json.loads(f.read())

        return gt

    def _gt_labels(self) -> dict:
        """Extract PII labels from ground truth"""

        gt_labels = {
                    i['value']['text'].strip():
                    {'label': i['value']['labels'][0]}
                    for i in self.gt['result']
                    }

        return gt_labels

    def _read_keys(self, file: Path) -> dict:
        """ Read file with PII keys and substitutes

        Parameters
        ----------
        dir : Path
            path to key file

        Returns
        -------
        dict of str
            dictionary of PII keys and substitutes
        """
        with file.open() as f:
            reader = csv.DictReader(f)
            keys = {row['names']: row['subt'] for row in reader}

        return keys

    def _read_anym(self, dir: Path) -> str:
        """read anonymized file

        Parameters
        ----------
        dir : Path
            path to directory with anonymized file

        Returns
        -------
        str
            text content of anonymized file
        """

        files = list(dir.glob('*.txt'))

        for file in files:
            with open(file, 'r', encoding='utf8') as f:
                anym_text = f.read()

        return anym_text

    def _find_subt(self, name: str) -> str:
        """Find key(substitute) for a given name"""
        try:
            subt = self.substitutes[name.strip()]
        except KeyError:
            logging.error(f'No hash for {name}')
            subt = '__NOHASH__'

        return subt

    def _count_subt(self, item: str) -> int:
        """Count frequency of substitutes in anonymized text
           for a given PII item"""

        if self.labels[item]['label'] == 'EMAIL':
            subt = '__email'
        elif self.labels[item]['label'] == 'LOC':
            subt = '__location'
        else:  # item is a name
            subt = self._find_subt(item)

        freq_subt = len(re.findall(subt, self.anym_text))

        return freq_subt

    def _compute_freqs(self, item: str) -> dict:
        """Count frequencies in raw and anonymized text
           per PII item and its substitute

        Parameters
        ----------
        item : str
            PII element

        Returns
        -------
        dict of int
            _description_
        """



        freqs = {}
        # count freq of label in ground truth
        freq_gt = len(re.findall(item, self.raw_text))
        freqs['freq_gt'] = freq_gt

        # count freq of label in anonymized text
        freq_anym = len(re.findall(item, self.anym_text))
        freqs['freq_anym'] = freq_anym

        # count freq of substitute in anonymized text
        freq_subt = self._count_subt(item)
        freqs['freq_subt'] = freq_subt

        return freqs

    def _compute_stats(self, item: str) -> dict:
        """ Compute true positives, false positives, false negatives
            per PII item """

        stats = {}
        TP = self.labels[item]['freq_gt'] - self.labels[item]['freq_anym']
        if TP < 0:
            TP = 0
        stats['TP'] = TP

        # true positives cannot be more than substitutes
        if self.labels[item]['freq_subt'] > TP:
            self.labels[item]['freq_subt'] = TP
        FP = self.labels[item]['freq_subt'] - TP
        stats['FP'] = FP

        FN = self.labels[item]['freq_anym']
        # false negatives cannot be more than freq in gt
        if FN > self.labels[item]['freq_gt']:
            FN = self.labels[item]['freq_gt']
        stats['FN'] = FN

        return stats

    def _compute_metrics(self, grp_dict: dict, label: str) -> dict:
        """ Compute metrics for a label """
    
        metrics = {}
        try:
            precision = grp_dict[label]['TP'] / (grp_dict[label]['TP'] + grp_dict[label]['FP'])
        except ZeroDivisionError:
            precision = 0        
        metrics['precision'] = precision
        
        try:
            recall = grp_dict[label]['TP'] / (grp_dict[label]['TP'] + grp_dict[label]['FN'])
        except ZeroDivisionError:
            recall = 0   
        metrics['recall'] = recall
        
        try:
            f1 = 2*(precision*recall) / (precision+recall)
        except ZeroDivisionError:
            f1 = 0   
        metrics['f1'] = f1
        
        return metrics
    
    def validate(self) -> dict:
        """ Main method for validation. 
            Collect frequencies, stats and metrics on deidentification """

        for item in self.labels.keys():
            logging.debug(f'Compute frequencies for {item}')
            freqs = self._compute_freqs(item)
            self.labels[item].update(freqs)
            stats = self._compute_stats(item)
            self.labels[item].update(stats)

        # summarize frequencies per label category
        labels_df = pd.DataFrame(self.labels).transpose()
        gr_labels_df = labels_df.groupby('label').sum()
        gr_labels_dict = gr_labels_df.transpose().to_dict()

        for label in gr_labels_dict.keys():
            logging.debug(f'Compute metrics for {label}')
            metrics = self._compute_metrics(gr_labels_dict, label)
            gr_labels_dict[label].update(metrics)

        self._write_val(gr_labels_dict)

    def _write_val(self, gr_labels_dict: dict):
        """ Write results of validation to csv file"""

        validation_df = pd.DataFrame(gr_labels_dict).transpose()
        validation_df.to_csv("validation.csv")


def main():
    logging.basicConfig(level=logging.DEBUG)

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
    logging.debug(f"Metrics: {metrics}")

if __name__ == '__main__':
    main()
