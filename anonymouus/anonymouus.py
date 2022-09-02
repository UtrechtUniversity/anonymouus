import csv
import re
import shutil
import tempfile
import uuid
import logging
import os
import pandas as pd
import charset_normalizer

from collections import OrderedDict
from inspect import signature, Parameter
from pathlib import Path, PosixPath, WindowsPath
from typing import Callable, Union
from itertools import groupby
from datetime import datetime

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
- CSV/XLS(X)/ODS: multiple columns with the same header will receive ".1" etc. suffixes,
  and only the first will be pseudonymized or excluded (w/o warning).
  'starts with' option allows more flexibility.
- Be aware that *all* files are copied to the target directory, including those
  that cannot be processed. This may include hidden files or files of which the
  name starts with a period.
"""

def get_logger(name,log_level=logging.INFO,log_file=None):
    # adding logger (screen only)
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    # formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] %(message)s')
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger

class Anonymize:

    def __init__(
            self,
            mapping: Union[dict, Path, Callable],
            pattern: str=None,
            flags=0,
            use_word_boundaries: bool=True,
            zip_format: str='zip',
            preprocess_text: Callable=None,
            log_file: str=None,
            log_level: int=logging.INFO,
            **kwargs
        ):

        self.logger = get_logger(name=type(self).__name__,log_file=log_file,log_level=log_level)

        # expression behaviour modifiers
        self.flags = flags

        # using word boundaries around pattern or dict keys, avoids
        # substring-matching
        self.use_word_boundaries = use_word_boundaries

        # if you use word boundaries, you might want to preprocess the
        # strings. You can do this with preprocess text, that function
        # must have at least one argument for the string itself
        self.preprocess_text = preprocess_text
        if callable(self.preprocess_text):
            sig = signature(self.preprocess_text)
            if len(sig.parameters) == 0:
                raise ValueError("""
                    preprocess_text must be assigned to a function with at
                    least one argument"""
                )
            elif len(sig.parameters) > 1:
                # more than 1 parameter, do the other parameters
                # have default values?
                parameters = list(sig.parameters.keys())[1:]
                pars_without_default = [
                    sig.parameters[k].default == Parameter.empty
                    for k in parameters
                ]
                if any(pars_without_default):
                    raise ValueError("""
                        preprocess_text must be aassigned to a function with
                        one positional argument (the first) that takes a
                        string, all other arguments must have a default
                        value.
                    """)

        self.mapping = None
        self.mapping_is_function = False
        # if there is no substitution dictionary then convert the csv
        # substitution table into a dictionary
        mapping_type = type(mapping)

        if mapping_type is dict:
            self.mapping = mapping
            self.logger.info(f"Method: mapping; using dictionary ({len(self.mapping)} items)")

        elif mapping_type in [str, Path, PosixPath, WindowsPath]:
            self.mapping_file = mapping
            self.mapping = self._convert_csv_to_dict(mapping)
            self.logger.info(f"Method: mapping; using file: '{self.mapping_file}' ({len(self.mapping):,} items)")

        elif callable(mapping):
            # raise an error if the callable is not accompanied by a pattern
            if pattern is None:
                raise ValueError('A mapping function can only be used in conjunction with a pattern')
            else:
                self.mapping = mapping
                self.mapping_is_function = True
                self.kwargs = kwargs
                self.logger.info(f"Method: function; using function: '{mapping.__qualname__}'")

        else:
            msg = 'Mapping must be a dictionary, path (str, Path, PosixPath, WindowsPath) ' + \
                f'or function. Found type: {mapping_type}'
            raise TypeError(msg)

        if pattern is not None:
            # # have user add boundaries to their pattern themselves
            # if self.use_word_boundaries is True:
            #     pattern = r'\b{}\b'.format(pattern)
            # the regular expression to find certain patterns
            self.pattern = re.compile(pattern, flags=self.flags)
            self.logger.info(f"Matching: using pattern '{self.pattern.pattern}'")
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
                if self.use_word_boundaries == True:
                    replacement_list = []
                    for key, value in self.mapping.items():
                        if type(key) is not re.Pattern:
                            key = r'\b{}\b'.format(key)
                        else:
                            key = re.compile(r'\b{}\b'.format(key.pattern))
                        replacement_list.append((key, value))
                    self.mapping = dict(replacement_list)

        # this is for processed zip archives
        self.zip_format = zip_format

        # Are we going to make a copy?
        self.copy = False

        self.cols_pseudonymize = []
        self.cols_exclude = []
        self.spread_sheets_pseudonymize = []
        self.spread_sheets_exclude = []
        self.cols_case_sensitive = False
        self.cols_match_style = 'exact'
        self.num_of_subs_made = 0
        self.subs_grand_total = 0
        self.processed_lines = 0
        self.processed_files = 0

    def set_cols_pseudonymize(self, cols_pseudonymize:list):
        self._cols_consistency(cols_pseudonymize)
        self._cols_sanity_check(cols_pseudonymize)
        self.cols_pseudonymize = self._cols_sanitize(cols_pseudonymize)
        self.logger.info(f"Column(s) to pseudonymize: {'; '.join(self.cols_pseudonymize)}")

    def set_cols_exclude(self, cols_exclude:list):
        self._cols_consistency(cols_exclude)
        self._cols_sanity_check(cols_exclude)
        self.cols_exclude = self._cols_sanitize(cols_exclude)
        self.logger.info(f"Column(s) to exclude: {'; '.join(self.cols_exclude)}")

    def set_cols_case_sensitive(self, case_sensitive:bool):
        self.cols_case_sensitive = bool(case_sensitive)
        self.logger.info(f"Column headers case sensitive: {self.cols_case_sensitive}")

    def set_cols_match_style(self, cols_match_style:str):
        cols_match_styles = ['exact','starts_with']
        if cols_match_style in cols_match_styles:
            self.cols_match_style = cols_match_style
        else:
            raise ValueError(f"Invalid column match style: '{cols_match_style}'; valid values: {'; '.join(cols_match_styles)}")
        self.logger.info(f"Column headers match style: {self.cols_match_style}")

    def _cols_consistency(self, cols:list):
        if len([x for x in cols if isinstance(x,str)])!=len(cols):
            raise ValueError("Column indices should be strings (column headers)")

    def _cols_sanity_check(self, cols:list):
        multiples = [x for x in [[key,len(list(group))] for key, group in groupby(sorted(cols))] if x[1]>1]
        if len(multiples)!=0:
            raise ValueError(f"Column indices are not unique: {'; '.join([str(x[0]) for x in multiples])}")

    def _cols_sanitize(self, cols:list):
        cols = list(map(lambda x: x.strip(),cols))
        cols = list(map(lambda x: re.sub('(\s)+',' ',x),cols))
        return cols

    def set_spread_sheets_pseudonymize(self, spread_sheets_pseudonymize:list):
        self.spread_sheets_pseudonymize = spread_sheets_pseudonymize
        self.logger.info(f"Spreadsheet sheets to pseudonymize: {'; '.join(self.spread_sheets_pseudonymize)}")

    def set_spread_sheets_exclude(self, spread_sheets_exclude:list):
        self.spread_sheets_exclude = spread_sheets_exclude
        self.logger.info(f"Spreadsheet sheets to exclude: {'; '.join(self.spread_sheets_exclude)}")

    def _convert_csv_to_dict(self, path_to_csv: str):
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
        reader = csv.DictReader(open(path_to_csv),dialect=self._get_csv_dialect(path_to_csv))
        # convert ordered dict into a plain dict, strip any white space
        data = [process_key_value_pair(kvp) for kvp in reader]

        # return ordered dictionary
        return OrderedDict(data)

    def _reorder_dict(self):
        '''Re-order the substitution dictionary such that longest keys
        are processed earlier, regex's come first'''
        new_dict = sorted(
            self.mapping.items(),
            key=lambda t: len(t[0]) if type(t[0]) is str else 100000,
            reverse=True
        )
        self.mapping = OrderedDict(new_dict)

    def substitute(self,
        source_path: Union[str, Path],
        target_path: Union[str, Path]=None
        ):

        self.logger.info(f"Input path: '{source_path}'")
        self.logger.info(f"Output path: '{target_path}'")

        # ensure source_path is a Path object
        if type(source_path) is str:
            source_path = Path(source_path)

        # make sure source exists:
        if not source_path.exists():
            raise FileNotFoundError("Source path does not exist")

        # ensure we have a target Path
        if target_path == None:
            # no target path, target is parent of source
            target_path = source_path.parent
        else:
            # convert to Path if necessary
            if type(target_path) is str:
                target_path = Path(target_path)
            # we will produce a copy
            self.copy = True

            # check if target is not a subfolder of source
            if source_path in target_path.parents:
                raise RuntimeError('the target path can\'t be a subfolder of the source path')

            # target path must be a folder!
            if target_path.exists():
                if target_path.is_file():
                    raise RuntimeError('target path must be a folder')
            else:
                # folder doesn't exist, create it
                self._make_dir(target_path)

        # start traversing
        self._traverse_tree(source_path, target_path)

        self.logger.info(f"Made {self.subs_grand_total:,} substitutions in {self.processed_files} files.")

    def substitute_string(self,source: str):
        if not type(source) is str:
            raise ValueError("Source is no string")

        if len(source)==0:
            return

        return self._substitute_ids(source)

    def _traverse_tree(self,
        source: Path,
        target: Path
        ):

        if source.is_file():
            self._process_file(source, target)
            self.processed_files += 1
        else:
            # this is a folder, rename/create if necessary
            (source, target) = self._process_folder(source, target)

            for child in source.iterdir():
                self._traverse_tree(child, target)

    def _process_folder(self,
        source: Path,
        target: Path
        ) -> Path:

        result = None

        # process target
        target = self._process_target(source, target)

        if self.copy == True:
            # we are making a copy, create this folder in target
            self._make_dir(target)
            result = (source, target)
        else:
            # we are only doing a substitution, rename
            self._rename_file_or_folder(source, target)
            result = (target, target)

        return result

    def _process_file(self,
        source: Path,
        target: Path
        ):

        if hasattr(self,'mapping_file') and (Path(source) == Path(self.mapping_file)):
            self.logger.warning(f"Mapping file '{source}' in source folder; skipping.")
            return

        # process target
        target = self._process_target(source, target)

        extension = source.suffix

        if extension in ['.csv']:
            self.logger.info(f"Processing CSV-file '{source}'")
            self._process_csv_file(source, target)
        elif extension in ['.xls','.xlsx','.ods']:
            self.logger.info(f"Processing spreadsheet '{source}'")
            self._process_xlsx_file(source, target)
        elif extension in ['.txt', '.html', '.htm', '.xml', '.json']:
            self.logger.info(f"Processing text based file '{source}'")
            self._process_txt_based_file(source, target)
        elif extension in ['.zip', '.gzip', '.gz']:
            self.logger.info(f"Processing archive '{source}'")
            self._process_zip_file(source, target, extension)
        else:
            self.logger.info(f"Processing unknown type '{source}'")
            self._process_unknown_file_type(source, target)

    def _process_target(
        self,
        source: Path,
        target: Path
        ):

        substituted_name = self._substitute_ids(source.name)
        new_target = target / substituted_name

        # if we are in copy mode, and the new_targets is identical
        # to the source, we need to differentiate
        if self.copy and new_target == source:
            new_target = (new_target.parent / new_target.name).with_suffix('.copy' + new_target.suffix)

        return new_target

    def _process_txt_based_file(
        self,
        source: Path,
        target: Path
        ):
        # read contents
        contents = self._read_file(source)

        # substitute
        self.num_of_subs_made = 0
        substituted_contents = [self._substitute_ids(line) for line in contents]

        if self.copy == False:
            # remove the original file
            self._remove_file(source)
            self.logger.info(f"Removed '{source}'")
        # write processed file
        self._write_file(target, substituted_contents)
        self.logger.info(f"{os.path.basename(target)}: {self.num_of_subs_made:,} substitutions in {len(contents)} lines.")

    def _process_unknown_file_type(
        self,
        source: Path,
        target: Path
        ):
        if self.copy == False:
            # just rename the file
            self._rename_file_or_folder(source, target)
        else:
            # copy source into target
            self._copy_file(source, target)

    def _process_zip_file(
            self,
            source: Path,
            target: Path,
            extension: str
        ):
        # create a temp folder to extract to
        with tempfile.TemporaryDirectory() as tmp_folder:
            # turn folder into Path object
            tmp_folder = Path(tmp_folder)
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
            self.substitute(Path(tmp_folder))
            # zip up the substitution
            shutil.make_archive(
                target.parent / target.with_suffix(''),
                self.zip_format,
                tmp_folder
            )
            # restore the copy feature
            self.copy = copy
            # remove original zipfile if we are not producing a copy
            if self.copy == False:
                self._remove_file(source)
                self.logger.info(f"Removed '{source}'")

    def _process_xlsx_file(
        self,
        source: Path,
        target: Path
        ):

        xlsx = pd.read_excel(source,sheet_name=None,index_col=None,keep_default_na=False)

        self.num_of_subs_made = 0
        self.processed_lines = 0

        with pd.ExcelWriter(target) as writer:
            for sheet in xlsx:
                if sheet in self.spread_sheets_exclude:
                    self.logger.info(f"{os.path.basename(target)}: excluding sheet '{sheet}'.")
                    continue

                if len(self.spread_sheets_pseudonymize)==0 or sheet in self.spread_sheets_pseudonymize:
                    self.sheet_source = f"{source} > {sheet}"
                    self.sheet_contents = xlsx[sheet]

                    # process contents
                    self._process_sheet()

                    # remove unwanted columns
                    self._exclude_columns()

                    # convert to dataframe and write
                    df = pd.DataFrame.from_dict(self.sheet_contents)
                    df.to_excel(writer, sheet_name=sheet, index=False)

                elif len(self.spread_sheets_pseudonymize)>0 and sheet not in self.spread_sheets_pseudonymize:
                    self.logger.info(f"{os.path.basename(target)}: skipping sheet '{sheet}'.")

        # optionally remove the original file
        if self.copy == False:
            self._remove_file(source)

        self.logger.info(f"{os.path.basename(target)}: {self.num_of_subs_made:,} substitutions in {self.processed_lines:,} lines.")

    def _process_csv_file(
        self,
        source: Path,
        target: Path
        ):

        # read contents
        self.sheet_contents = pd.read_csv(
            source,
            dtype=str,
            dialect=self._get_csv_dialect(source),
            encoding=self._get_file_encoding(source)
            )

        # process contents
        self.num_of_subs_made = 0
        self.processed_lines = 0
        self.sheet_source = source
        self._process_sheet()

        # remove unwanted columns
        self._exclude_columns()

        # convert to CSV and write
        self._write_file(target, self.sheet_contents.to_csv(path_or_buf=None, index=False))

        # optionally, remove the original file
        if self.copy == False:
            self._remove_file(source)

        self.logger.info(f"{os.path.basename(target)}: {self.num_of_subs_made:,} substitutions in {self.processed_lines:,} lines.")

    def _process_sheet(self):
        # clean up sheet's column headers
        self.sheet_contents.columns = self._cols_sanitize(self.sheet_contents.columns)

        # make everything lower if not case-sensitive
        if not self.cols_case_sensitive:
            self.sheet_contents.columns = list(map(lambda x: x.lower(),self.sheet_contents.columns))
            self.cols_pseudonymize = list(map(lambda x: x.lower(),self.cols_pseudonymize))
            self.cols_exclude = list(map(lambda x: x.lower(),self.cols_exclude))

        if len(self.cols_pseudonymize)>0:
            # selected columns to pseudonymize
            if self.cols_match_style == 'starts_with':
                # find matches if 'starts_with' (useful for repeating column headers)
                columns_to_pseudonymize = []
                for column in self.cols_pseudonymize:
                    columns_to_pseudonymize = columns_to_pseudonymize + [x for x in self.sheet_contents.columns if x.startswith(column)]
            else:
                # use literal
                columns_to_pseudonymize = self.cols_pseudonymize

            # detect columns that don't actually exist in source files
            missing_cols = [x for x in self.cols_pseudonymize if x not in self.sheet_contents.columns ]
            if len(missing_cols)>0:
                # raise ValueError(f"Some column(s) do not exist in {source}: {'; '.join(missing_cols)}. Valid columns: {'; '.join(header_line)}")
                self.logger.warning(f"{self.sheet_source}: column(s) to pseudonymize do not exist: {'; '.join(missing_cols)}")
        else:
            # do all columns
            columns_to_pseudonymize = list(contents.columns)

        # go through all rows
        for index, row in self.sheet_contents.iterrows():
            # go through updatable columns
            for column in columns_to_pseudonymize:
                # if column actually exists in source
                if column in self.sheet_contents.columns:
                    # substitute
                    self.sheet_contents.at[index,column] = self.substitute_string(str(self.sheet_contents.at[index,column]))
            self.processed_lines += 1

    def _exclude_columns(self):
        if len(self.cols_exclude)==0:
            return

        if self.cols_match_style == 'starts_with':
            columns_to_exclude = []
            for column in self.cols_exclude:
                columns_to_exclude = columns_to_exclude + [x for x in self.sheet_contents.columns if x.startswith(column)]
        else:
            columns_to_exclude = self.cols_exclude

        exclude = []

        for column in columns_to_exclude:
            if column in self.sheet_contents.columns:
                exclude.append(list(self.sheet_contents.columns).index(column))

        if len(exclude)==0:
            return

        self.sheet_contents.drop(self.sheet_contents.columns[exclude], axis=1, inplace=True)

    def _get_csv_dialect(self,path_to_file):
        with open(path_to_file,encoding=self._get_file_encoding(path_to_file)) as csvfile:
            dialect = csv.Sniffer().sniff(csvfile.read(1024))
        return dialect

    def _get_file_encoding(self,path_to_file):
        with open(path_to_file,'rb') as f:
            data = f.read()  # or a chunk, f.read(1000000)
        encoding=charset_normalizer.detect(data).get("encoding")
        return encoding

    def _substitute_ids(self, string: str):
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
                if type(key) is re.Pattern:
                    key = key.pattern
                string, num_of_subs_made = re.subn(key, str(value), string, flags=self.flags)
                self._update_subs_count(num_of_subs_made)
        else:
            if self.mapping_is_function:
                # if there is a mapping function involved, we will use that
                string, num_of_subs_made = self.pattern.subn(
                    lambda match: self.mapping(match.group(), **self.kwargs),
                    string
                )
                self._update_subs_count(num_of_subs_made)
            else:
                # identify patterns and substitute them with appropriate substitute
                string, num_of_subs_made = self.pattern.subn(
                    lambda match: self.mapping.get(
                        match.group(),
                        match.group()
                    ),
                    string
                )
                self._update_subs_count(num_of_subs_made)

        return string

    def _update_subs_count(self,num):
        self.num_of_subs_made += num
        self.subs_grand_total += num

    # FILE OPERATIONS, OVERRIDE THESE IF APPLICABLE
    def _make_dir(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)

    def _read_file(self, source: Path):
        f = open(source, 'r', encoding='utf-8', errors='ignore')
        contents = list(f)
        f.close()
        return contents

    def _write_file(self, path: Path, contents: str):
        f = open(path, 'w', encoding='utf-8')
        f.writelines(contents)
        f.close()
        self.logger.info(f"Wrote '{path}'")

    def _remove_file(self, path: Path):
        path.unlink()

    def _remove_folder(self, path: Path):
        shutil.rmtree(path)

    def _rename_file_or_folder(self, source: Path, target: Path):
        source.replace(target)

    def _copy_file(self, source: Path, target: Path):
        if source != target:
            shutil.copy(source, target)


class AdHocCodeMapper:

    mapping_result_file = None
    code_generator_function = None
    buffer_max = 1000
    memory = []

    def __init__(self,mapping_result_file,log_file,log_level=logging.INFO):
        self.logger = get_logger(name=type(self).__name__,log_file=log_file,log_level=log_level)
        self.mapping_result_file = mapping_result_file
        self._backup_existing_result_file()

        try:
            open(mapping_result_file, "w")
        except Exception as e:
            # unlink(self.backup_file)
            raise e

    def __del__(self):
        self.write_translation_table(flush=True)
        self.logger.info(f"Wrote {len(self.memory):,} pseudonyms to '{self.mapping_result_file}'")

    def _backup_existing_result_file(self):
        f = Path(self.mapping_result_file)
        if not f.is_file():
            return

        self.backup_file = Path(self.mapping_result_file)

        while self.backup_file.is_file():
            now = datetime.now()
            stamp = now.strftime("%Y-%m-%d-%H:%M:%S")
            filename, file_extension = os.path.splitext(self.mapping_result_file)
            self.backup_file = Path(f"{filename}--{stamp}{file_extension}")

        os.rename(self.mapping_result_file,self.backup_file)
        self.logger.info(f"Backed up previous mapping result file to '{self.backup_file}'")

    def set_code_generator(self,function):
        '''
        Example: set_code_generator(lambda x: hashlib.md5(x.encode('utf-8')).hexdigest())
        '''
        if callable(function):
            sig = signature(function)
            if len(sig.parameters) != 1:
                raise RuntimeError(f"Generator function is required to accept one argument (even if it is unused).")
            try:
                function('test')
                self.code_generator_function = function
            except Exception as e:
                raise RuntimeError(f"Generator function raised error at test: {str(e)}")
        else:
            raise RuntimeError(f"Code generator function '{function}' is not callable.")

    def get_translation_table(self):
        return self.memory

    def write_translation_table(self,flush=False):
        if (len(self.memory)>0) and ((len(self.memory) % self.buffer_max == 0) or flush):
            keys = self.memory[0].keys()
            with open(self.mapping_result_file, 'w', newline='') as output_file:
                dict_writer = csv.DictWriter(output_file, keys)
                dict_writer.writeheader()
                dict_writer.writerows(self.memory)
            self.logger.debug(f"Wrote {len(self.memory)} pseudonyms...")

    def subtitute(self,string):
        mem = [x for x in self.memory if x['original']==string]
        if len(mem)==1:
            pseudonym = mem[0]['pseudonym']
        elif len(mem)>1:
            raise ValueError(f"AdHocCodeMapper registered double entry!?: {mem}")
        else:
            if self.code_generator_function:
                pseudonym = self.code_generator_function(string)
            else:
                pseudonym = self._code_generator()
            self.memory.append({'original':string,'pseudonym':pseudonym})
            self.write_translation_table()
        return pseudonym

    def _code_generator(self):
        return str(uuid.uuid4())
