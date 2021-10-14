# anonymoUUs

This description can be found [on GitHub](https://github.com/UtrechtUniversity/anonymouus)

The software in this package traverses a file-tree looking for keywords with the aim of replacing them with a substitute. It was designed to anonymize data: the goal was to substitute multiple id strings in multiple files with pseudo ids to avoid tracable relationships between data batches. A single data batch typically consists of multiple nested folders that contain multiple files in multiple formats. The file contents, file names and folder names may or may not contain ids. AnonymoUUs will replace them all. The package also deals with zipped folders.

The keyword-replacement mapping can be provided by the user in several forms: in dictionary, a csv file and a function. The result will be, depending on how you run the software, either a copied or replaced version of the original file-tree in which all replacements were made.

As of now, anonymoUUs supports text-based files, like .txt, .html, .json and .csv. UTF-8 encoding is assumed. But it is easy to extend the software to handle other formats as well. 

## Installation

In your terminal type:

`$ pip install anonymoUUs`

## Usage

In order to replace words or patterns you need a replacement-mapping in the form of:
1. a dictionary - the keys will be replaced by the values
2. the path to a csv file - a csv file will be converted in a dictionary, the first column provides keys, the second value provides values. Path can be a String, Path or PosixPath!
3. a function - a replacement function can be passed if a pattern is used. The function takes a found match and should return its replacement. The function must have at least one input argument.

### Example of replacement with a dictionary

Import the Anomymize class in your code and create an anonymization object like this:

```python
from anonymoUUs import Anonymize

# refer to csv files in which keywords and substitutions are paired
anonymize_csv = Anonymize('/Users/casper/Desktop/keys.csv')

# using a dictionary instead of a csv file:
my_dict = {
    'A1234': 'aaaa',
    'B9876': 'bbbb',
}
anonymize_dict = Anonymize(my_dict)
```

Putting regular expression in dictionaries is also possible.When using a dictionary only (absence of the `pattern` argument), the keys-pattern will be replaced by its value:

```
anon = Anonymize(
    {
        'regular-key': 'replacement-1',
        re.compile('ca.*?er'): 'replacement-2'
    }
)
```

### Example of replacement with a CSV file

```python
# specifying a zip-format to zip unpacked archives after processing (.zip is default)
anonymize_zip = Anonymize('/Users/casper/Desktop/keys.csv')
```

When using a csv-file, anonymoUUs will assume your file contains two columns: the left column contains the keywords which need to be replaced, the right column contains their substitutions. **Column headers are mandatory**, but don't have to follow a specific format.

It is possible to add a regular expression as keyword in the csv-file. Make sure they start with the prefix 'r#'. Example:

```
r#ca.*?er, replacement_string
```

The key will be compiles as a regex and replace every match with 'replacement_string'.


### Example of replacement by regex pattern and function

If you are replacing with a pattern you can also use a function to 'calculate' the replacement string:

```python
def replace(match, **kwargs):
    result = 'default-replacement'
    match = int(match)
    threshold = kwargs.get("threshold", 4000)
    if match < threshold:
        result = 'special-replacement'
    return result

anon = Anonymize(replace, pattern=r'\d{4}', threshold=1000)
anon.substitute(
    '/Users/casperkaandorp/Desktop/test.json', 
    '/Users/casperkaandorp/Desktop/result-folder'
)
```
Note the possibility to provide additional arguments when you initialize an Anonymize object that will be passed to the replcement function (in the previous example, the `threshold` is passed to the `replace` function).

### Other arguments

Performance is probably best when your keywords can be generalized into a single regular expressions. anonymoUUs will search these patterns and replace them instead of matching the entire dictionary/csv-file against file contents or file/folder-paths. Example:

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

It is also to specify how to re-zip unzipped folders:

```python
# specifying a zip-format to zip unpacked archives after processing (.zip is default)
anonymize_zip = Anonymize('/Users/casper/Desktop/keys.csv', zip_format='gztar')
```

### Windows usage

There is an issue with creating zip archives. Make sure you **run anonymoUUs as administrator**.

### Inplace replacements vs. replacements in a copy

anonymoUUs is able to create a copy of the processed file-tree or replace it. The `substitute` method takes a mandatory source-path argument (path to a file, folder or zip-archive, either a string or a [Path](https://docs.python.org/3/library/pathlib.html#basic-use) object) and an optional target-path argument (again, a string or [Path](https://docs.python.org/3/library/pathlib.html#basic-use) object). The target **needs to refer to a folder**, which can't be a sub-folder of the source-folder. The target-folder will be created if it doesn't exist.

When the target argument is provided, anonymoUUs will create a processed copy of the source into the target-folder. If the source is a single file, and the file path does not contain elements that will be replaced, and the target-folder is identical to the source folder, than the processed result will get a 'copy' extension to prevent overwriting.

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

### Reading contents of a file

Files will be opened depending on their extension. Non refognized extensions will be skipped. The standard version of this package assumes 'UTF-8' encoding. Errors are going to be ignored. Since reading file-contents is done with a single function, it will be easy to adjust (different encodings,etc) by overloading it in an extension:

```python
# standard reading function
def _read_file(self, source: Path):
    f = open(source, 'r', encoding='utf-8', errors='ignore')
    contents = list(f)
    f.close()
    return contents
```

## Todo

Cleaning up this document

Testing! Sweet momma, it needs testing.