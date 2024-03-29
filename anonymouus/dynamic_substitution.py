import os
import csv
import uuid
import logging
from datetime import datetime
from pathlib import Path
from inspect import signature


class DynamicSubstitution:

    def __init__(self,
                 logger=None,
                **kwargs
                 ):

        self.mapping_result_file = None
        self.code_generator_function = None
        self.buffer_max = 1000
        self.memory = []
        if logger:
            self.logger = logger
        self.kwargs = kwargs

    def _log(self, message, level=logging.INFO):
        if self.logger:
            if level==logging.ERROR:
                self.logger.error(message)
            elif level==logging.WARNING:
                self.logger.warning(message)
            else:
                self.logger.info(message)

    def _code_generator(self):
        return str(uuid.uuid4())

    def set_code_generator(self, function):
        '''
        Example: set_code_generator(lambda x: hashlib.md5(x.encode('utf-8')).hexdigest())
        '''
        if callable(function):
            sig = signature(function)
            if len(sig.parameters) < 1:
                raise RuntimeError("Generator function needs to accept at least one argument (even if it doesn't actually use it).")
            try:
                function('test', **self.kwargs)
                self.code_generator_function = function
            except Exception as exception:
                raise RuntimeError(f'Generator function raised error at test: {str(exception)}') from exception
        else:
            raise RuntimeError(f"Generator function '{function}' is not callable.")

    def get_translation_table(self):
        return self.memory

    def _backup_existing_result_file(self, mapping_result_file):
        if not Path(mapping_result_file).is_file():
            return

        backup_file = Path(mapping_result_file)

        while backup_file.is_file():
            now = datetime.now()
            stamp = now.strftime("%Y-%m-%d-%H%M%S")
            filename, file_extension = os.path.splitext(mapping_result_file)
            backup_file = Path(f"{filename}--{stamp}{file_extension}")

        os.rename(mapping_result_file, backup_file)
        self._log(f"Backed up previous mapping result file to '{backup_file}'")

    def write_translation_table(self, mapping_result_file):
        if len(self.memory) == 0:
            self._log("Nothing to write (no pseudonyms recorded)")
            return

        try:
            open(mapping_result_file, "w")
        except Exception as exception:
            # unlink(self.backup_file)
            raise exception

        self._backup_existing_result_file(mapping_result_file)

        keys = self.memory[0].keys()
        with open(mapping_result_file, 'w', newline='',
                    encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, keys)
            dict_writer.writeheader()
            dict_writer.writerows(self.memory)

        self._log(f"Wrote {len(self.memory):,} pseudonyms to '{mapping_result_file}'")

        pseudonyms = len([x['pseudonym'] for x in self.memory])
        pseudonyms_uniq = len(list(set([x['pseudonym'] for x in self.memory])))

        if pseudonyms != pseudonyms_uniq:
            self._log(f"Generated only {pseudonyms_uniq:,} unique pseudonyms out of a total of {pseudonyms:,}", level=logging.WARNING)

    def subtitute(self, string):
        mem = [x for x in self.memory if x['original'] == string]
        if len(mem) == 1:
            pseudonym = mem[0]['pseudonym']
        elif len(mem) > 1:
            raise ValueError(f"DynamicSubstitution registered double entry!? ({mem})")
        else:
            if self.code_generator_function:
                pseudonym = self.code_generator_function(string, **self.kwargs)
            else:
                pseudonym = self._code_generator()

            if len([x for x in self.memory if x['pseudonym'] == pseudonym])>0:
                self._log(f"Generator function generated a duplicate: '{pseudonym}'.", level=logging.WARNING)

            self.memory.append({'original': string, 'pseudonym': pseudonym})

        return pseudonym
