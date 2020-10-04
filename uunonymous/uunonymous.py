import csv
import re
import shutil
import tempfile

from collections import OrderedDict
from pathlib import Path, PosixPath
from typing import Union


class Anonymize:

    def __init__(
            self, 
            substitution_dict: Union[dict, Path],
            pattern: str=None,
            flags=0,
            use_word_boundaries: bool=False,
            zip_format: str='zip',
        ):

        # expression behaviour modifiers
        self.flags = flags

        # if there is no substitution dictionary then convert the csv 
        # substitution table into a dictionary
        if type(substitution_dict) is dict:
            self.substitution_dict = substitution_dict
        else:
            self.substitution_dict = self._convert_csv_to_dict(
                substitution_dict
            )

        # using word boundaries around pattern or dict keys, avoids
        # substring-matching
        self.use_word_boundaries = use_word_boundaries

        # the regular expression to find certain patterns
        if pattern != None:
            if self.use_word_boundaries == True:
                pattern = r'\b{}\b'.format(pattern)
            self.pattern = re.compile(pattern, flags=self.flags)
        else:
            self.pattern = False
            # re-order the OrderedDict such that the longest
            # keys are first: ensures that shorter versions of keys
            # will not be substituted first if bigger substitutions 
            # are possible
            self._reorder_dict()
            # add word boundaries if requested
            if self.use_word_boundaries == True:
                self.substitution_dict = dict([
                    (r'\b{}\b'.format(key), value)
                    for key, value in self.substitution_dict.items()
                ])

        # this is for processed zip archives
        self.zip_format = zip_format

        # Are we going to make a copy?
        self.copy = False



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
            self.substitution_dict.items(), 
            key=lambda t: len(t[0]) if type(t[0]) is str else 100000, 
            reverse=True
        )
        self.substitution_dict = OrderedDict(new_dict)


    def substitute(self, 
        source_path: Union[str, Path], 
        target_path: Union[str, Path]=None
        ):

        # ensure source_path is a Path object
        if type(source_path) is str:
            source_path = Path(source_path)

        # make sure source exists:
        if not source_path.exists():
            raise RuntimeError('source path does not exist')  

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

        if extension in ['.txt', '.csv', '.html', '.htm', '.xml', '.json']:
            self._process_txt_based_file(source, target)
        elif extension in ['.zip', '.gzip', '.gz']:
            self._process_zip_file(source, target, extension)
        else:
            self._process_unknown_file_type(source, target)


    def _process_target(self,
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


    def _process_txt_based_file(self,
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
        # write processed file
        self._write_file(target, substituted_contents)


    def _process_unknown_file_type(self,
        source: Path,
        target: Path
        ):

        if self.copy == False:
            # just rename the file
            self._rename_file_or_folder(source, target)
        else:
            # copy source into target
            self._copy_file(source, target)


    def _process_zip_file(self, 
        source: Path,
        target: Path,
        extension: str
        ):

        # create a temp folder to extract to
        with tempfile.TemporaryDirectory() as tmp_folder:
            # extract our archive
            shutil.unpack_archive(source, tmp_folder)
            # this is hacky, but inevitable: I want an in-place
            # processing, maybe we were copying, I have to switch it
            # off and on again
            copy = self.copy
            self.copy = False
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


    def _substitute_ids(self, string: str):
        '''Heart of this class: all matches of the regular expression will be
        substituted for the corresponding value in the id-dictionary'''
        if self.pattern == False:
            #
            # This might be more efficient:
            # https://en.wikipedia.org/wiki/Aho%E2%80%93Corasick_algorithm
            #
            # loop over dict keys, try to find them in string and replace them 
            # with their values
            for key, value in self.substitution_dict.items():
                if type(key) is re.Pattern:
                    key = key.pattern
                string = re.sub(key, str(value), string, flags=self.flags)

        else:
            # identify patterns and substitute them with appropriate substitute
            string = self.pattern.sub(
                lambda match: self.substitution_dict.get(
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
        f = open(source, 'r', encoding='utf-8')
        contents = list(f)
        f.close()
        return contents


    def _write_file(self, path: Path, contents: str):
        f = open(path, 'w', encoding='utf-8')
        f.writelines(contents)
        f.close()


    def _remove_file(self, path: Path):
        path.unlink()

    
    def _remove_folder(self, path: Path):
        shutil.rmtree(path)


    def _rename_file_or_folder(self, source: Path, target: Path):
        source.replace(target)


    def _copy_file(self, source: Path, target: Path):
        if source != target:
            shutil.copy(source, target)



