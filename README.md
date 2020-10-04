# UUnonymous

This description can be found [on GitHub here](https://github.com/UtrechtUniversity/uunonymous)

UUnonymous facilitates the replacement of keywords or regex-patterns within a file tree or zipped archive. It recursively traverses the tree, opens supported files and substitutes any found pattern or keyword with a replacement. Besides contents, UUnonymous will substitue keywords/patterns in file/folder-paths as well.

The result will be either a copied or replaced version of the original file-tree with all substitutions made.

As of now, UUnonymous supports text-based files, like .txt, .html, .json and .csv. UTF-8 encoding is assumed. Besides text files, UUnonymous is also able to handle (nested) zip archives. These archives will be unpacked in a temp folder, processed and zipped again.

## Installation

`$ pip install UUnonymous`

## Usage

Import the Anomymize class in your code and create an anonymization object like this:

```
from uunonymous import Anonymize

# refer to csv files in which keywords and substitutions are paired
anonymize_csv = Anonymize('/Users/casper/Desktop/keys.csv')

# using a dictionary instead of a csv file:
my_dict = {
    'A1234': 'aaaa',
    'B9876': 'bbbb',
}
anonymize_dict = Anonymize(my_dict)

# specifying a zip-format to zip unpacked archives after processing (.zip is default)
anonymize_zip = Anonymize('/Users/casper/Desktop/keys.csv', zip_format='gztar')
```

When using a csv-file, UUnonymous will assume your file contains two columns: the left column contains the keywords which need to be replaced, the right column contains their substitutions. **Column headers are mandatory**, but don't have to follow a specific format.

It is possible to add a regular expression as keyword in the csv-file. Make sure they start with the prefix 'r#'. Example:

```
r#ca.*?er, replacement_string
```

The key will be compiles as a regex and replace every match with 'replacement_string'.


When using a dictionary only (absence of the `pattern` argument), the keys will be replaced by their values. Again, it is possible to use (compiled) regular expressions as keys. The expression will replace all matches with its value. Example:

```
anon = Anonymize(
    {
        'regular-key': 'replacement-1',
        re.compile('ca.*?er'): 'replacement-2'
    }
)
```

Performance might be enhanced when your keywords can be generalized into a single regular expressions. UUnynomize will search these patterns and replace them instead of matching the entire dictionary/csv-file against file contents or file/folder-paths. Example:

```
anonymize_regex = Anonymize(my_dict, pattern=r'[A-B]\d{4}')
```

By default is case sensitive by default. The regular expressions that take care of the replacements can be modified by using the `flag` parameter. It takes one or more variables [which can be found here](https://docs.python.org/3/library/re.html). Multiple variables are combined by a bitwise OR (the | operator). Example for a case-insensitive substitution:

```
anonymize_regex = Anonymize(my_dict, flags=re.IGNORECASE)
```

By using the `use_word_boundaries` argument (defaults to False), the algorithm ignores substring matches. If 'ted' is a key in your dictionary, without `use_word_boundaries` the algorithm will replace the 'ted' part in f.i. 'created_at'. You can overcome this problem by setting `use_word_boundaries` to True. It will put the `\b`-anchor around your regex pattern or dictionary keys. The beauty of the boundary anchors is that '@' is considered a boundary as well, and thus names in email addresses can be replaced. Example:

```
anonymize_regex = Anonymize(my_dict, use_word_boundaries=True)
```

### Windows usage

There is an issue with creating zip archives. Make sure you **run UUnonymous as administrator**.

### Inplace replacements vs. replacements in a copy

UUnonymous is able to create a copy of the processed file-tree or replace it. The `substitute` method takes a mandatory source-path argument (path to a file, folder or zip-archive, either a string or a [Path](https://docs.python.org/3/library/pathlib.html#basic-use) object) and an optional target-path argument (again, a string or [Path](https://docs.python.org/3/library/pathlib.html#basic-use) object). The target **needs to refer to a folder**, which can't be a sub-folder of the source-folder. The target-folder will be created if it doesn't exist.

When the target argument is provided, UUnonymous will create a processed copy of the source into the target-folder. If the source is a single file, and the file path does not contain elements that will be replaced, and the target-folder is identical to the source folder, than the processed result will get a 'copy' extension to prevent overwriting.

When the target argument is omitted, the source will be overwritten by a processed version of it:

```
# process the datadownload.zip file, replace all patterns and write
# a copy to the 'bucket' folder.
anonymize_regex.substitute(
    '/Users/casper/Desktop/datadownload.zip', 
    '/Users/casper/Desktop/bucket'
)

# process the 'download' folder and replace the original by its processed 
# version
anonymize_regex.substitute('/Users/casper/Desktop/download')

# process a single file, and replace it
anonymize_regex.substitute('/Users/casper/Desktop/my_file.json')
```

## Todo

Fix the infinite loop that occurs when the source folder shares the same parent folder as the target folder

Testing ;)