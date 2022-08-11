import csv
import re
import shutil
import tempfile
import pandas as pd
import uuid
import logging

from collections import OrderedDict
from inspect import signature, Parameter
from pathlib import Path, PosixPath, WindowsPath
from typing import Callable, Union
from itertools import groupby

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
            **kwargs
        ):

        self.logger = get_logger(name=type(self).__name__,log_file=log_file)

        # expression behaviour modifiers
        self.flags = flags

        # using word boundaries around pattern or dict keys, avoids
        # substring-matching
        self.use_word_boundaries = use_word_boundaries
        # if you use word boundaries, you might want to preprocess the
        # strings. You can do this with preprocess text, that function
        # must have at least one argument for the string itself
        # mds 2022.08 not sure why we would need a preprocerssor in case of word boundaries
        # but it might come in handy sometime anyhow.
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
            self.logger.info(f"Mapping: using dictionary")

        elif mapping_type in [str, Path, PosixPath, WindowsPath]:
            self.mapping = self._convert_csv_to_dict(mapping)
            self.logger.info(f"Mapping: using file '{mapping}'")

        elif callable(mapping):
            # raise an error if the callable is not accompanied by a
            # pattern
            if pattern is None:
                raise ValueError('A mapping function can only be used in conjunction with a pattern')
            else:
                self.mapping = mapping
                self.mapping_is_function = True
                self.kwargs = kwargs
                self.logger.info(f"Mapping: using function '{mapping.__qualname__}'")

        else:
            msg = 'mapping must be a dictionary, path (str, Path, PosixPath, WindowsPath) ' + \
                f'or function. Found type: {mapping_type}'
            raise TypeError(msg)

        # Word-boundaries: let's add them here, it's a one time
        # overhead thing. Not the prettiest code.
        # the regular expression to find certain patterns
        # mds 2022.08: not sure why there is an explicit switch for word boundaries which just adds to the regex ppl are going
        # to provide themselves anyway. If they know regex, they'll also know how to add word boundaries to an expression.
        if pattern is not None:
            if self.use_word_boundaries is True:
                pattern = r'\b{}\b'.format(pattern)
            self.pattern = re.compile(pattern, flags=self.flags)
            self.logger.info(f"Matching: using pattern '{self.pattern.pattern}'")
        else:
            self.pattern = False

            if not self.mapping_is_function:
                # re-order the OrderedDict such that the longest
                # keys are first: ensures that shorter versions of keys
                # will not be substituted first if bigger substitutions
                # are possible
                # mds 2022.08: but this won't prevent re-substitution of smaller codes in larger ones that were already done.
                # might be interesting to experiment with using something like unprintable characters to do a first stage
                # substitution to avoid re-substitutions.
                self._reorder_dict()
                # add word boundaries if requested
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
        self.cols_case_sensitive = False

    def _convert_csv_to_dict(self, path_to_csv: str):
        '''Converts 2-column csv file into dictionary. Left
        column contains ids, right column contains substitutions.
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
        reader = csv.DictReader(open(path_to_csv))
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

        self.logger.info(f"input path: '{source_path}'")
        self.logger.info(f"output path: '{target_path}'")

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

    def _traverse_tree(self,
        source: Path,
        target: Path
        ):

        if source.is_file():
            self._process_file(source, target)
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

        # process target
        target = self._process_target(source, target)

        extension = source.suffix

        if extension in [ '.csv' ] and (self.cols_pseudonymize or self.cols_exclude):
            self.logger.info(f"processing CSV-file '{source}'")
            self._process_csv_file(source, target)
        elif extension in ['.txt', '.csv', '.html', '.htm', '.xml', '.json']:
            self.logger.info(f"processing text based file '{source}'")
            self._process_txt_based_file(source, target)
        elif extension in ['.zip', '.gzip', '.gz']:
            self.logger.info(f"processing archive '{source}'")
            self._process_zip_file(source, target, extension)
        else:
            self.logger.info(f"processing unknown type '{source}'")
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
        substituted_contents = [self._substitute_ids(line) for line in contents]
        if self.copy == False:
            # remove the original file
            self._remove_file(source)
            self.logger.info(f"removed '{source}'")
        # write processed file
        self._write_file(target, substituted_contents)

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
                self.logger.info(f"removed '{source}'")

    def _substitute_ids(self, string: str):
        '''Heart of this class: all matches of the regular expression will be
        substituted for the corresponding value in the id-dictionary'''
        # preprocess if necessary
        if callable(self.preprocess_text):
            string = self.preprocess_text(string)

        if self.pattern is False:
            #
            # This might be more efficient:
            # https://en.wikipedia.org/wiki/Aho%E2%80%93Corasick_algorithm
            #
            # loop over dict keys, try to find them in string and replace them
            # with their values
            for key, value in self.mapping.items():
                if type(key) is re.Pattern:
                    key = key.pattern
                string = re.sub(key, str(value), string, flags=self.flags)

        else:

            if self.mapping_is_function:
                # if there is a mapping function involved, we will use that
                string = self.pattern.sub(
                    lambda match: self.mapping(match.group(), **self.kwargs),
                    string
                )
            else:
                # identify patterns and substitute them with appropriate substitute
                string = self.pattern.sub(
                    lambda match: self.mapping.get(
                        match.group(),
                        match.group()
                    ),
                    string
                )

        return string

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
        self.logger.info(f"wrote '{path}'")

    def _remove_file(self, path: Path):
        path.unlink()

    def _remove_folder(self, path: Path):
        shutil.rmtree(path)

    def _rename_file_or_folder(self, source: Path, target: Path):
        source.replace(target)

    def _copy_file(self, source: Path, target: Path):
        if source != target:
            shutil.copy(source, target)

    def set_cols_pseudonymize(self, cols_pseudonymize:list):
        self._cols_consistency(cols_pseudonymize)
        self._cols_sanity_check(cols_pseudonymize)
        self.cols_pseudonymize = list(map(lambda x: x.strip(),cols_pseudonymize))
        self.logger.info(f"CSV-columns to pseudonymize: {'; '.join(self.cols_pseudonymize)}")

    def set_cols_exclude(self, cols_exclude:list):
        self._cols_consistency(cols_exclude)
        self._cols_sanity_check(cols_exclude)
        self.cols_exclude = list(map(lambda x: x.strip(),cols_exclude))
        self.logger.info(f"CSV-columns to exclude: {'; '.join(self.cols_exclude)}")

    def set_cols_case_sensitive(self, case_sensitive:bool):
        self.cols_case_sensitive = bool(case_sensitive)

    def substitute_string(self,source: str):
        if not type(source) is str:
            raise ValueError("Source is no string")

        if len(source)==0:
            return

        return self._substitute_ids(source)

    def _cols_consistency(self,cols):
        if len([x for x in cols if isinstance(x,str)])!=len(cols):
            raise ValueError("Column indices should be strings (column headers)")

    def _cols_sanity_check(self,cols):
        multiples = [x for x in [[key,len(list(group))] for key, group in groupby(sorted(cols))] if x[1]>1]
        if len(multiples)!=0:
            raise ValueError(f"Column indices are not unique: {'; '.join([str(x[0]) for x in multiples])}")

    def _process_csv_file(
        self,
        source: Path,
        target: Path
        ):

        # read contents
        contents = pd.read_csv(source, dtype=str)

        # also fetch a header line that allows double column names
        # (pd.read_csv() adds ".1" etc. to doubles)
        with open(source) as f:
          reader = csv.reader(f)
          original_header_line = next(reader)
          original_header_line = list(map(lambda x: x.strip(),original_header_line))

        contents.columns = map(lambda x: x.strip(),contents.columns)

        if not self.cols_case_sensitive:
            contents.columns = map(lambda x: x.lower(),contents.columns)
            self.cols_pseudonymize = list(map(lambda x: x.lower(),self.cols_pseudonymize))
            self.cols_exclude = list(map(lambda x: x.lower(),self.cols_exclude))

        # scan header line to detect ambiguous column names
        # (i.e. multiple columns with the same header)
        if not self.cols_case_sensitive:
            self.header_line = map(lambda x: x.lower(),original_header_line)
        else:
            self.header_line = original_header_line

        multiples = [x for x in [[key,len(list(group))] for key, group in groupby(sorted(self.header_line))] if x[1]>1]
        subst_multiples = [x for x in multiples if x[0] in self.cols_pseudonymize]
        if len(subst_multiples)!=0:
            self.logger.warning(f"{source}: ambiguous column(s): {'; '.join([ f'{str(x[0])} ({str(x[1])}x)' for x in subst_multiples])}. Only the first instance(s) will be pseudonymised.")

        if len(self.cols_pseudonymize)>0:
            # detect columns that don't actually exist in source files
            missing_cols = [x for x in self.cols_pseudonymize if x not in contents.columns ]
            if len(missing_cols)>0:
                # raise ValueError(f"Some column(s) do not exist in {source}: {'; '.join(missing_cols)}. Valid columns: {'; '.join(header_line)}")
                self.logger.warning(f"{source}: column(s) to pseudonymize do not exist: {'; '.join(missing_cols)}")

            columns_to_pseudonymize = self.cols_pseudonymize
        else:
            columns_to_pseudonymize = list(contents.columns)

        # go through all rows
        for index, row in contents.iterrows():
            # go through updatable columns
            for column in columns_to_pseudonymize:
                # if column actually exists in source
                if column in contents.columns:
                    # substitute
                    contents.at[index,column] = self.substitute_string(contents.at[index,column])

        # convert pseudonymised data to CSV, using the original header
        self.substituted_contents = contents.to_csv(path_or_buf=None,index=False,header=original_header_line)

        # remove unwanted columns
        self._exclude_columns()

        if self.copy == False:
            # remove the original file
            self._remove_file(source)

        # write processed file
        self._write_file(target, self.substituted_contents)

    def _exclude_columns(self):
        if len(self.cols_exclude)==0:
            return

        columns_to_delete = []

        for column in self.cols_exclude:
            if column in self.header_line:
                columns_to_delete.append(self.header_line.index(column))

        if len(columns_to_delete)==0:
            return

        new_lines = []
        reader = csv.reader(self.substituted_contents.splitlines())
        for line in list(reader):
            new_lines.append([x for key,x in enumerate(line) if not key in columns_to_delete])

        self.substituted_contents = pd.DataFrame(new_lines).to_csv(path_or_buf=None,index=False,header=None)


class AdHocCodeMapper:

    translation_table_file = None
    code_generator_function = None
    memory = []

    def __init__(self,translation_table_file,log_file):
        self.logger = get_logger(name=type(self).__name__,log_file=log_file)
        self.translation_table_file = translation_table_file

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

    def write_translation_table(self):
        if len(self.memory)>0:
            keys = self.memory[0].keys()
            with open(self.translation_table_file, 'w', newline='') as output_file:
                dict_writer = csv.DictWriter(output_file, keys)
                dict_writer.writeheader()
                dict_writer.writerows(self.memory)
            self.logger.info(f"Wrote to translation table to '{self.translation_table_file}'")
        else:
            self.logger.error("Nothing to write: made no substitutions.")

    def subtitute(self,string):
        mem = [x for x in self.memory if x['original']==string]
        if len(mem)==1:
            return mem[0]['pseudonym']
        elif len(mem)>1:
            raise ValueError(f"Double entry!? {self.memory}")
        else:
            if self.code_generator_function:
                out = self.code_generator_function(string)
            else:
                out = self._code_generator()
            self.memory.append({'original':string,'pseudonym':out})
            return out

    def _code_generator(self):
        return str(uuid.uuid4())
