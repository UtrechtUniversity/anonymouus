import csv
import re
import shutil
import tempfile
import logging
import os
import charset_normalizer
import pandas as pd
from pandas import DataFrame
from collections import OrderedDict
from inspect import signature, Parameter
from pathlib import Path, PosixPath, WindowsPath
from typing import List, Callable, Union, Dict, Tuple, Optional
from itertools import groupby
from datetime import datetime
from anonymouus.utils import get_logger
from anonymouus.date_replacer import DateReplacer

"""
Documentation items
- Code assumes first line in mapping file to be fieldnames (w/o checks or
  feedback).
- Only with mapping & no word boundaries: partial double pseudonymization can
  occur if a pseudonymn of a longer original string contains a shorter original
  string also in the mapping.
- 'Use word boundaries' turns original strings into regex's and pre- and append
  \b for word boundaries. Theoretically this might cause trouble if an original
  string compiles as a regex.
- 'Use word boundaries' no longer works when using pattern, as it is more
  transparent to have users add the \b to their pattern themselves.
- CSV/ODS: multiple columns with the same header will receive ".1"
  etc. suffixes, and only the first will be pseudonymized or excluded (w/o
  warning). 'starts with' option allows more flexibility.
- Be aware that *all* files are copied to the target directory, including those
  that cannot be processed. This may include hidden files or files of which the
  name starts with a period.
- substitute_dates: this is not restricted to specified CSV-columns; it's all
  or nothing.

  took out XLSX due to engine errors

"""

class CsvHandling:

    cols_match_styles = ['exact', 'starts_with']

    def __init__(self,
                cols_pseudonymize: List[str] = [],
                cols_exclude: List[str] = [],
                sheets_pseudonymize: List[str] = [],
                sheets_exclude: List[str] = [],
                cols_case_sensitive: bool = False,
                cols_match_style: str = 'exact'
    ) -> None:
        self.set_cols_pseudonymize(cols_pseudonymize)
        self.set_cols_exclude(cols_exclude)
        self.set_sheets_pseudonymize(sheets_pseudonymize)
        self.set_sheets_exclude(sheets_exclude)
        self.set_cols_case_sensitive(cols_case_sensitive)
        self.set_cols_match_style(cols_match_style)

    def set_cols_pseudonymize(self, cols_pseudonymize: List[str]):
        self._cols_consistency(cols_pseudonymize)
        self._cols_sanity_check(cols_pseudonymize)
        self.cols_pseudonymize = self.cols_sanitize(cols_pseudonymize)

    def set_cols_exclude(self, cols_exclude: List[str]):
        self._cols_consistency(cols_exclude)
        self._cols_sanity_check(cols_exclude)
        self.cols_exclude = self.cols_sanitize(cols_exclude)

    def set_sheets_pseudonymize(self, sheets_pseudonymize: List[str]):
        self.sheets_pseudonymize = sheets_pseudonymize

    def set_sheets_exclude(self, sheets_exclude: List[str]):
        self.sheets_exclude = sheets_exclude

    def set_cols_case_sensitive(self, cols_case_sensitive: bool):
        if not isinstance(cols_case_sensitive, bool):
            raise ValueError("Expected boolean")
        self.cols_case_sensitive = cols_case_sensitive

    def set_cols_match_style(self, cols_match_style: str):
        if not cols_match_style in self.cols_match_styles:
            raise ValueError("Invalid column match style:" +
                             f"'{cols_match_style}'; " +
                             f"valid values: {'; '.join(self.cols_match_styles)}")
        self.cols_match_style = cols_match_style

    def cols_sanitize(self, cols: List[str]) -> List[str]:
        cols = list(map(lambda x: x.strip(), cols))
        cols = list(map(lambda x: re.sub(r'(\s)+', ' ', x), cols))
        return cols

    def _cols_consistency(self, cols: List[str]):
        if len([x for x in cols if isinstance(x, str)]) != len(cols):
            raise ValueError("Column indices should be strings (headers)")

    def _cols_sanity_check(self, cols: List[str]):
        multiples = [x for x in [[key, len(list(group))]
                     for key, group in groupby(sorted(cols))] if x[1] > 1]
        if len(multiples) != 0:
            raise ValueError("Column indices are not unique: " +
                             f"{'; '.join([str(x[0]) for x in multiples])}")


class Anonymize:

    def __init__(
            self,
            mapping: Union[dict, Path, Callable],
            pattern: str = None,
            flags=0,
            use_word_boundaries: bool = True,
            date_replacer: DateReplacer = None,
            session_id: str = None,
            zip_format: str = 'zip',
            preprocess_text: Callable = None,
            log_file: str = None,
            log_level: int = logging.INFO,
            **kwargs
            ):

        self.logger = get_logger(name=type(self).__name__, log_file=log_file,
                                 log_level=log_level)

        # session id
        self.session_id = session_id if session_id is not None else '{:%Y-%m-%dT%H:%M}'.format(datetime.now())
        self.session_id = re.sub(r'[^\w_-]', '_', self.session_id)[:32]
        self.logger.info("Session ID: %s", self.session_id)

        # expression behaviour modifiers
        self.flags = flags

        # using word boundaries around pattern or dict keys, avoids
        # substring-matching
        self.use_word_boundaries = use_word_boundaries

        # if you use word boundaries, you might want to preprocess the
        # strings. You can do this with preprocess text, that function
        # must have at least one argument for the string itself
        if preprocess_text and self._check_callable(preprocess_text):
            self.preprocess_text = preprocess_text

        self.mapping = None
        self.mapping_is_function = False
        self.mapping_file = None
        # if there is no substitution dictionary then convert the csv
        # substitution table into a dictionary

        if isinstance(self.mapping, dict):
            self.mapping = mapping
            self.logger.info("Method: mapping; using dictionary (%s items)",
                             len(self.mapping))

        elif isinstance(self.mapping, str) or \
             isinstance(self.mapping, Path) or \
             isinstance(self.mapping, PosixPath) or \
             isinstance(self.mapping, WindowsPath):
            self.mapping_file = mapping
            self.mapping = self._convert_csv_to_dict(mapping)
            self.logger.info("Method: mapping; using file: '%s' (%s items)",
                             self.mapping_file, len(self.mapping))

        elif callable(mapping):
            # raise an error if the callable is not accompanied by a pattern
            if pattern is None:
                raise ValueError("A mapping function can only be used in " +
                                 "conjunction with a pattern")

            self.mapping = mapping
            self.mapping_is_function = True
            self.kwargs = kwargs
            self.logger.info("Method: function; using function: '%s'",
                             mapping.__qualname__)

        else:
            msg = 'Mapping must be a dictionary, path ' + \
                  '(str, Path, PosixPath, WindowsPath) ' + \
                  f'or function. Found type: {type(mapping)}'
            raise TypeError(msg)

        if pattern is not None:
            # # have user add boundaries to their pattern themselves
            # if self.use_word_boundaries is True:
            #     pattern = r'\b{}\b'.format(pattern)
            # the regular expression to find certain patterns
            self.pattern = re.compile(pattern, flags=self.flags)
            self.logger.info("Matching: using pattern '%s'",
                             self.pattern.pattern)
        else:
            self.pattern = False

            if not self.mapping_is_function:
                # re-order the OrderedDict such that the longest
                # keys are first: ensures that shorter versions of keys
                # will not be substituted first if bigger substitutions
                # are possible
                # mds 2022.08: this won't prevent re-substitution of smaller
                # codes in larger ones that were already done.
                # (only relevant with mapping file and no word boundaries)
                self._reorder_dict()
                # Word-boundaries: let's add them here, it's a one time
                # overhead thing. Not the prettiest code.
                if self.use_word_boundaries:
                    replacement_list = []
                    for key, value in self.mapping.items():
                        if not isinstance(key, re.Pattern):
                            key = r'\b{}\b'.format(key)
                        else:
                            key = re.compile(r'\b{}\b'.format(key.pattern))
                        replacement_list.append((key, value))
                    self.mapping = dict(replacement_list)

        # this is for processed zip archives
        self.zip_format = zip_format

        # Are we going to make a copy?
        self.copy = False

        self.csv_handling = CsvHandling()
        self.sheet_source: str
        self.sheet_contents: DataFrame

        if date_replacer and self._check_callable(date_replacer):
            self.date_replacer = date_replacer

        self.stats = {
            "subs_made": 0,
            "subs_grand_total": 0,
            "processed_lines": 0,
            "processed_files": 0,
            "dates": 0
        }

    def set_cols_pseudonymize(self, cols_pseudonymize: List[str]):
        self.csv_handling.set_cols_pseudonymize(cols_pseudonymize)
        self.logger.info("Column(s) to pseudonymize: %s",
                         '; '.join(self.csv_handling.cols_pseudonymize))

    def set_cols_exclude(self, cols_exclude: List[str]):
        self.csv_handling.set_cols_exclude(cols_exclude)
        self.logger.info("Column(s) to exclude: %s",
                         '; '.join(self.csv_handling.cols_exclude))

    def set_cols_case_sensitive(self, case_sensitive: bool):
        self.csv_handling.set_cols_case_sensitive(bool(case_sensitive))
        self.logger.info("Column headers case sensitive: %s",
                         self.csv_handling.cols_case_sensitive)

    def set_cols_match_style(self, cols_match_style: str):
        self.csv_handling.set_cols_match_style(cols_match_style)
        self.logger.info("Column headers match style: %s",
                         self.csv_handling.cols_match_style)

    def set_sheets_pseudonymize(self, sheets_pseudonymize: List[str]):
        self.csv_handling.set_sheets_pseudonymize(sheets_pseudonymize)
        self.logger.info("Spreadsheet sheet(s) to pseudonymize: %s",
                         '; '.join(self.csv_handling.sheets_pseudonymize))

    def set_sheets_exclude(self, sheets_exclude: List[str]):
        self.csv_handling.set_sheets_exclude(sheets_exclude)
        self.logger.info("Spreadsheet sheet(s) to exclude: %s",
                         '; '.join(self.csv_handling.sheets_exclude))

    def substitute(self,
                   source_path: Union[str, Path],
                   target_path: Union[str, Path] = None
                   ):
        self.logger.info(f"Input path: '{source_path}'")
        self.logger.info(f"Output path: '{target_path}'")

        # ensure source_path is a Path object
        if isinstance(source_path, str):
            source_path = Path(source_path)

        # make sure source exists:
        if not source_path.exists():
            raise FileNotFoundError("Source path does not exist")

        # ensure we have a target Path
        if target_path is None:
            # no target path, target is parent of source
            target_path = source_path.parent
        else:
            # convert to Path if necessary
            if isinstance(target_path, str):
                target_path = Path(target_path)
            # we will produce a copy
            self.copy = True

            # check if target is not a subfolder of source
            if source_path in target_path.parents:
                raise RuntimeError("Target path cannot be a subfolder of source path")

            # adding session id subfolder
            target_path = Path(target_path) / Path(self.session_id)

            # target path must be a folder
            if target_path.exists():
                if target_path.is_file():
                    raise RuntimeError("Target path must be a folder")
            else:
                # folder doesn't exist, create it
                self._make_dir(target_path)

        # start traversing
        self._traverse_tree(source_path, target_path)

        self.logger.info("%s codes and %s dates replaced in %s files.",
                         self.stats["subs_grand_total"],
                         self.date_replacer.replacements_made if self.date_replacer else 0,
                         self.stats["processed_files"])

    def substitute_string(self, source: str) -> str:
        if not isinstance(source, str):
            raise ValueError("Source is no string")

        if len(source) == 0:
            return ""

        new_source = self._substitute_ids(source)
        new_source = self._substitute_dates(new_source)
        return new_source

    def _convert_csv_to_dict(self, path_to_csv: Union[str, Path]) -> Dict:
        '''
        Converts 2-column csv file into dictionary. Left
        column contains ids, right column contains substitutions.
        Be aware: by default, DictReader assumes the first row to be
        fieldnames.
        '''
        # this nested function takes care of stripping, escaping and
        # converting dict keys into regulare expressions
        def process_key_value_pair(key_value_pair):
            # convert to list
            kvp = list(key_value_pair.values())
            # get key and value
            key = kvp[0].strip()
            value = kvp[1].strip()
            # if key starts with r# then this is a regex
            if key.startswith('r#'):
                key = re.compile(key[2:])
            else:
                # otherwise, escape key
                key = re.escape(key)
            # return
            return (key, value)

        # read csv file
        with open(path_to_csv, encoding='utf-8') as file:
            reader = csv.DictReader(file,
                                    dialect=self._get_csv_dialect(path_to_csv))
        # convert ordered dict into a plain dict, strip any white space
        data = [process_key_value_pair(kvp) for kvp in reader]

        # return ordered dictionary
        return OrderedDict(data)

    def _reorder_dict(self):
        '''Re-order the substitution dictionary such that longest keys
        are processed earlier, regex's come first'''
        new_dict = sorted(
            self.mapping.items(),
            key=lambda t: len(t[0]) if isinstance(t[0], str) else 100000,
            reverse=True
        )
        self.mapping = OrderedDict(new_dict)

    def _traverse_tree(self, source: Path, target: Path):
        if source.is_file():
            self._process_file(source, target)
        else:
            # this is a folder, rename/create if necessary
            (source, target) = self._process_folder(source, target)

            for child in source.iterdir():
                self._traverse_tree(child, target)

    def _process_folder(self, source: Path, target: Path) -> Tuple[Path, Path]:
        result = None

        # process target
        target = self._process_target(source, target)

        if self.copy:
            # we are making a copy, create this folder in target
            self._make_dir(target)
            result = (source, target)
        else:
            # we are only doing a substitution, rename
            self._rename_file_or_folder(source, target)
            result = (target, target)

        return result

    def _process_file(self, source: Path, target: Path):
        if hasattr(self, 'mapping_file') \
                and not self.mapping_file is None \
                and (Path(source) == Path(self.mapping_file)):
            self.logger.warning("Mapping file '%s' in source folder; " +
                                "skipping.", source)
            return

        # process target
        target = self._process_target(source, target)

        extension = source.suffix

        if extension in ['.csv']:
            self.logger.info(f"Processing CSV-file '{source}'")
            self._process_csv_file(source, target)
        elif extension in ['.odf', '.odt', '.ods']:
            self.logger.info(f"Processing spreadsheet '{source}'")
            self._process_spreadsheet(source, target)
        elif extension in ['.txt', '.html', '.htm', '.xml', '.json']:
            self.logger.info(f"Processing text based file '{source}'")
            self._process_txt_based_file(source, target)
        elif extension in ['.zip', '.gzip', '.gz']:
            self.logger.info(f"Processing archive '{source}'")
            self._process_zip_file(source, target)
        else:
            self.logger.info(f"Processing unknown type '{source}'")
            self._process_unknown_file_type(source, target)

        self.stats["processed_files"] += 1

    def _process_target(self, source: Path, target: Path) -> Path:
        substituted_name = self._substitute_ids(source.name)
        substituted_name = self._substitute_dates(substituted_name)
        new_target = target / substituted_name

        # if we are in copy mode, and the new_targets is identical
        # to the source, we need to differentiate
        if self.copy and new_target == source:
            new_target = (new_target.parent / new_target.name). \
                         with_suffix('.copy' + new_target.suffix)

        return new_target

    def _process_txt_based_file(self, source: Path, target: Path):
        # read contents
        contents = self._read_file(source)

        # substitute
        self.stats["subs_made"] = 0
        substituted_contents = [self._substitute_ids(line)
                                for line in contents]

        substituted_contents = [self._substitute_dates(line)
                                for line in substituted_contents]

        if not self.copy:
            # remove the original file
            self._remove_file(source)
            self.logger.info(f"Removed '{source}'")

        # write processed file
        self._write_file(target, substituted_contents)
        self.logger.info("%s: %s substitutions in %s lines.",
                         os.path.basename(target),
                         self.stats["subs_made"], len(contents))

    def _process_unknown_file_type(self, source: Path, target: Path):
        if not self.copy:
            # just rename the file
            self._rename_file_or_folder(source, target)
        else:
            # copy source into target
            self._copy_file(source, target)

    def _process_zip_file(self, source: Path, target: Path):
        # create a temp folder to extract to
        with tempfile.TemporaryDirectory() as tmp:
            # turn folder into Path object
            tmp_folder = Path(tmp)
            # extract our archive
            shutil.unpack_archive(source, tmp_folder)
            # this is hacky, but inevitable: I want an in-place
            # processing, maybe we were copying, I have to switch it
            # off and on again
            copy = self.copy
            self.copy = False
            # this is also a weird one: apparently Mac produces
            # a MACOSX folder when it zips something, I am
            # not interested
            macosx_folder = (tmp_folder / '__MACOSX')
            if macosx_folder.exists() and macosx_folder.is_dir():
                shutil.rmtree(macosx_folder, ignore_errors=True)

            # perform the substitution
            self.substitute(tmp_folder)
            # zip up the substitution
            shutil.make_archive(
                str(target.parent / target.with_suffix('')),
                self.zip_format,
                tmp_folder
            )
            # restore the copy feature
            self.copy = copy
            # remove original zipfile if we are not producing a copy
            if not self.copy:
                self._remove_file(source)
                self.logger.info(f"Removed '{source}'")

    def _process_spreadsheet(self, source: Path, target: Path):
        xlsx = pd.read_excel(source,
                             sheet_name=None,
                             index_col=None,
                             keep_default_na=False,
                             engine="odf"
                             )

        self.stats["subs_made"] = 0
        self.stats["processed_lines"] = 0

        with pd.ExcelWriter(target) as writer:
            for sheet in xlsx:
                if sheet in self.csv_handling.sheets_exclude:
                    self.logger.info("%s: excluding sheet '%s'.",
                                     os.path.basename(target), sheet)
                    continue

                if len(self.csv_handling.sheets_pseudonymize) == 0 \
                        or sheet in self.csv_handling.sheets_pseudonymize:
                    self.sheet_source = f"{source} > {sheet}"
                    self.sheet_contents = xlsx[sheet]

                    # process contents
                    self._process_sheet()

                    # remove unwanted columns
                    self._exclude_columns()

                    # convert to dataframe and write
                    dataframe = pd.DataFrame.from_dict(self.sheet_contents)
                    dataframe.to_excel(writer, sheet_name=sheet, index=False)

                elif len(self.csv_handling.sheets_pseudonymize) > 0 \
                        and sheet not in self.csv_handling.sheets_pseudonymize:
                    self.logger.info("%s: skipping sheet '%s'.",
                                     os.path.basename(target), sheet)

        # optionally remove the original file
        if not self.copy:
            self._remove_file(source)

        self.logger.info("%s: %s substitutions in %s lines.",
                         os.path.basename(target),
                         self.stats["subs_made"],
                         self.stats["processed_lines"])

    def _process_csv_file(self, source: Path, target: Path):
        # read contents
        self.sheet_contents = pd.read_csv(
            source,
            dtype=str,
            dialect=self._get_csv_dialect(source),
            encoding=self._get_file_encoding(source)
            )

        # process contents
        self.stats["subs_made"] = 0
        self.stats["processed_lines"] = 0
        self.sheet_source = str(source)
        self._process_sheet()

        # remove unwanted columns
        self._exclude_columns()

        # convert to CSV and write
        self._write_file(target, self.sheet_contents.to_csv(path_or_buf=None,
                                                            index=False))

        # optionally, remove the original file
        if not self.copy:
            self._remove_file(source)

        self.logger.info("%s: %s substitutions in %s lines.",
                         os.path.basename(target),
                         self.stats["subs_made"],
                         self.stats["processed_lines"])

    def _process_sheet(self):
        # clean up sheet's column headers
        self.sheet_contents.columns = \
            self.csv_handling.cols_sanitize(self.sheet_contents.columns)

        # make everything lower if not case-sensitive
        if not self.csv_handling.cols_case_sensitive:
            self.sheet_contents.columns = list(map(lambda x: x.lower(),
                                               self.sheet_contents.columns))
            self.csv_handling.cols_pseudonymize = \
                list(map(lambda x: x.lower(),
                self.csv_handling.cols_pseudonymize))
            self.csv_handling.cols_exclude = list(map(lambda x: x.lower(),
                                     self.csv_handling.cols_exclude))

        if len(self.csv_handling.cols_pseudonymize) > 0:
            # selected columns to pseudonymize
            if self.csv_handling.cols_match_style == 'starts_with':
                # find matches if 'starts_with' (useful for repeating headers)
                columns_to_pseudonymize = []
                for column in self.csv_handling.cols_pseudonymize:
                    columns_to_pseudonymize = columns_to_pseudonymize + \
                        [x for x in self.sheet_contents.columns
                         if x.startswith(column)]
            else:
                # use literal
                columns_to_pseudonymize = self.csv_handling.cols_pseudonymize

            # detect columns that don't actually exist in source files
            missing_cols = [x for x in self.csv_handling.cols_pseudonymize
                            if x not in self.sheet_contents.columns]

            if len(missing_cols) > 0:
                self.logger.warning("%s: column(s) to pseudonymize do " +
                                    "not exist: %s", self.sheet_source,
                                    '; '.join(missing_cols))
        else:
            # do all columns
            columns_to_pseudonymize = list(self.sheet_contents.columns)

        # go through all rows
        for index, _ in self.sheet_contents.iterrows():
            # go through updatable columns
            for column in columns_to_pseudonymize:
                # if column actually exists in source
                if not column in self.sheet_contents.columns:
                    continue
                # substitute
                self.sheet_contents.at[index, column] = \
                    self.substitute_string(
                        str(self.sheet_contents.at[index, column])
                    )
            self.stats["processed_lines"] += 1

        if self.date_replacer:
            # go through all rows
            for index, _ in self.sheet_contents.iterrows():
                # go through all columns
                for column in list(self.sheet_contents.columns):
                    self.sheet_contents.at[index, column] = \
                       self._substitute_dates(
                            str(self.sheet_contents.at[index, column])
                        )

    def _exclude_columns(self):
        if len(self.csv_handling.cols_exclude) == 0:
            return

        if self.csv_handling.cols_match_style == 'starts_with':
            columns_to_exclude = []
            for column in self.csv_handling.cols_exclude:
                columns_to_exclude = columns_to_exclude + \
                                     [x for x in self.sheet_contents.columns
                                      if x.startswith(column)]
        else:
            columns_to_exclude = self.csv_handling.cols_exclude

        exclude = []

        for column in columns_to_exclude:
            if column in self.sheet_contents.columns:
                exclude.append(list(self.sheet_contents.columns).index(column))

        if len(exclude) == 0:
            return

        self.sheet_contents.drop(self.sheet_contents.columns[exclude], axis=1,
                                 inplace=True)

    def _get_csv_dialect(self, path_to_file) -> type:
        with open(path_to_file,
                  encoding=self._get_file_encoding(path_to_file)) as csvfile:
            dialect = csv.Sniffer().sniff(csvfile.readline())
        return dialect

    def _get_file_encoding(self, path_to_file: Path) -> str:
        with open(path_to_file, 'rb') as file:
            data = file.read()  # or a chunk, f.read(1000000)
        encoding = charset_normalizer.detect(data).get("encoding")
        return encoding

    def _substitute_ids(self, string: str) -> str:
        '''Heart of this class: all matches of the regular expression will be
        substituted for the corresponding value in the id-dictionary'''

        # preprocess if necessary
        if callable(self.preprocess_text):
            string = self.preprocess_text(string)

        if self.pattern is False:
            # This might be more efficient:
            # https://en.wikipedia.org/wiki/Aho%E2%80%93Corasick_algorithm
            #
            # loop over dict keys, try to find them in string and replace them
            # with their values
            for key, value in self.mapping.items():
                if isinstance(key, re.Pattern):
                    key = key.pattern
                string, subs_made = re.subn(key, str(value), string,
                                                   flags=self.flags)
                self._update_subs_count(subs_made)
        else:
            if self.mapping_is_function:
                # if there is a mapping function involved, we will use that
                string, subs_made = self.pattern.subn(
                    lambda match: self.mapping(match.group(), **self.kwargs),
                    string
                )
                self._update_subs_count(subs_made)
            else:
                # identify patterns and make substitutions
                string, subs_made = self.pattern.subn(
                    lambda match: self.mapping.get(
                        match.group(),
                        match.group()
                    ),
                    string
                )
                self._update_subs_count(subs_made)

        return string

    def _update_subs_count(self, num):
        self.stats["subs_made"] += num
        self.stats["subs_grand_total"] += num

    def _substitute_dates(self, string: str) -> str:
        if not self.date_replacer:
            return string
        return self.date_replacer(string)

    # FILE OPERATIONS, OVERRIDE THESE IF APPLICABLE
    def _make_dir(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)

    def _read_file(self, source: Path):
        with open(source, 'r', encoding='utf-8', errors='ignore') as file:
            contents = list(file)
        return contents

    def _write_file(self, path: Path, contents: List[str]):
        with open(path, 'w', encoding='utf-8') as file:
            file.writelines(contents)
        self.logger.info("Wrote '%s", path)

    def _remove_file(self, path: Path):
        path.unlink()

    def _remove_folder(self, path: Path):
        shutil.rmtree(path)

    def _rename_file_or_folder(self, source: Path, target: Path):
        source.replace(target)

    def _copy_file(self, source: Path, target: Path):
        if source != target:
            shutil.copy(source, target)

    def _check_callable(self, function):
        if not callable(function):
            raise ValueError(f"{str(function)} not callable")

        sig = signature(function)
        if len(sig.parameters) == 0:
            raise ValueError(f"{function.__name__} needs to accept at least one argument")
        if len(sig.parameters) > 1:
            # more than 1 parameter, do the other parameters
            # have default values?
            parameters = list(sig.parameters.keys())[1:]
            pars_without_default = [
                sig.parameters[k].default == Parameter.empty
                for k in parameters
            ]
            if any(pars_without_default):
                raise ValueError(f"{function.__name__} should take one positional argument \
                    that takes a string; all other arguments must have a default value.")
        
        return True
