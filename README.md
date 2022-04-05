# anonymoUUs

anonymoUUs is a Python package for replacing identifiable strings in multiple files and folders at once. It can be used to pseudonymise data files and therefore contributes to protecting personal data. 

The goal of anonymoUUs is to substitute multiple identifying strings with pseudo-IDs to avoid tracable relationships between data batches. A single data batch typically consists of multiple nested folders that contain multiple files in multiple formats. AnonymoUUs runs through the **entire** file tree, looking for keywords to replace them with the provided substitute, including in:  
- the file contents
- file names
- folder names
- zipped folders 

**Note**: Whereas replacing personal details with non-personal details can make data less identifiable, it does not guarantee anonymous data!

## Supported file formats

AnonymoUUs can work with multiple text-based file types, like `.txt`, `.html`, `.json` and `.csv`. UTF-8 encoding is assumed. Users have several options to provide keyword-replacement mappings and to customize the behaviour of the software, visit the [usage section](#usage) for more information.  

## Table of Contents
  * [Getting Started](#getting-started)
    + [Prerequisites](#prerequisites)
    + [Installation](#installation)
    + [Example workflow](#example-workflow)
  * [Usage](#usage)
    + [1. Input Data](#1-input-data)
    + [2. Mapping](#2-mapping)
    + [3. Create an Anonymize object](#3-create-an-anonymize-object)
    + [4. Substitute data](#4-substitute-data)
  * [Validation](#validation)  
    + [Prepare](#prepare)
    + [Validate](#validate)
  * [Attribution and academic use](#attribution-and-academic-use)
  * [Contributing](#contributing)
  * [Contact](#contact)

## Getting Started

### Prerequisites

To install and run anonymoUUs, you need:
- an active [Python](https://www.python.org/) installation;
- a folder containing the data to be pseudonymised;
- a keyword-replacement mapping file.

### Installation

To install anonymoUUs, in your terminal run:

```sh
$ pip install anonymoUUs
```

### Example workflow
To get started with a simple example, you can go through this [Jupyter notebook](/anonymouus/examples/try_testing.ipynb), which runs through a minimal example of anonymoUUs.

Prerequisites:
- download the testdata from the [test_data folder](/anonymouus/tests/test_data)
- make sure you have [jupyter notebook](https://jupyter.readthedocs.io/en/latest/install/notebook-classic.html) installed

## Usage
To run the software, you need to take the following steps:
1. Provide the path to the [data](#1-input-data) to be substituted
2. Provide the [keyword-replacement mapping](#2-mapping)
3. Create and customize the [Anonymize object](#3-create-an-anonymize-object)
4. Perform the [substitutions](#4-substitute-data)

### 1. Input Data
Provide the path to the folder where the data resides, for example:
```python
from pathlib import Path
test_data = Path('../test_data/')
```

Details:
- Files are opened depending on their extension. Extensions that are not recognised will be skipped. 
- Errors will be ignored.
- The standard version of this package assumes 'UTF-8' encoding. Since reading file-contents is done with a single function, it will be easy to adjust it, for example to also read other encodings. You can do so by overloading it in an extension:

```python
# standard reading function
def _read_file(self, source: Path):
    f = open(source, 'r', encoding='utf-8', errors='ignore')
    contents = list(f)
    f.close()
    return contents
```

### 2. Mapping
In order to replace words or patterns, you need a replacement-mapping. AnonymoUUs allows mappings in the form of a dictionary, a csv file or a function. 
- In all cases, the keys will be replaced by the provided values.
- It is also possible to provide string *patterns* to replace, using regular expressions (regex) in the keys. AnonymoUUs will replace every matching pattern with the provided replacement string.

#### Dictionary mapping
To use a dictionary-type mapping, simply provide the (path to the) dictionary (file) and apply the `Anonymize` function. Note that you can provide a regular expression using `re.compile('regex')` to look for string patterns.

```python
from anonymoUUs import Anonymize

# Using a dictionary and regular expression for subject 02:
my_dict = {
    'Bob': 'subject-01',
    re.compile('ca.*?er'): 'subject-02',
}

anonymize_dict = Anonymize(my_dict)
```

#### CSV file mapping
To use a CSV for mapping, simply provide the path to the file. AnonymoUUs converts the provided csv file into a dictionary.

Requirements:
- The csv file needs to contain column headers (any format)
- The csv file needs to have the keys (which need to be replaced, e.g., names) in the first column and the values (the replacements, e.g., numbers) in the second column.
- The path can be a String, Path or PosixPath. 

It is possible to add a regular expression as keyword in the csv-file. Make sure they start with the prefix `r#`:

| key | value |
| ---| --- |
| `r#ca.*?er` | `replacement string` |

```python
# Using a csv file
key_csv = test_data/'keys.csv'

anonymize_csv = Anonymize(key_csv)
```

#### Function mapping
If you are replacing strings with a pattern, you can also use a function to 'calculate' the replacement string. The function takes a found match and should return its replacement. The function must have at least one input argument.

```python
# Define function
def replace(match, **kwargs):
    result = 'default-replacement'
    match = int(match)
    threshold = kwargs.get("threshold", 4000)
    if match < threshold:
        result = 'special-replacement'
    return result

# Subsitute using the defined replace function
anon = Anonymize(replace, pattern=r'\d{4}', threshold=1000)
anon.substitute(
    '/Users/casperkaandorp/Desktop/test.json', 
    '/Users/casperkaandorp/Desktop/result-folder'
)
```
Note the possibility to provide additional arguments when you initialize an Anonymize object that will be passed to the replacement function (in this example, the `threshold` is passed to the `replace` function).

### 3. Create an Anonymize object
By default, the Anonymize function is case sensitive. Basic use:
```python
from anonymoUUs import Anonymize

anonymize_object = Anonymize(keys)
```

Performance is probably best when your keywords can be generalized into a single regular expression. AnonymoUUs will search these patterns and replace them instead of matching the entire dictionary/csv-file against file contents or file/folder-paths. Example:

```python
anonymize_regex = Anonymize(my_dict, pattern=r'[A-B]\d{4}')
```

#### Arguments
The regular expressions that take care of the replacements can be modified by using the `flag` parameter. It takes one or more variables [which can be found here](https://docs.python.org/3/library/re.html). Multiple variables are combined by a bitwise OR (the | operator). Example for a case-insensitive substitution:

```
anonymize_regex = Anonymize(my_dict, flags=re.IGNORECASE)
```

By using the `use_word_boundaries` argument (defaults to False), the algorithm ignores substring matches. If 'ted' is a key in your dictionary, without `use_word_boundaries` the algorithm will replace the 'ted' part in f.i. 'created_at'. You can overcome this problem by setting `use_word_boundaries` to True. It will put the `\b`-anchor around your regex pattern or dictionary keys. The beauty of the boundary anchors is that '@' is considered a boundary as well, and thus names in email addresses can be replaced. Example:

```
anonymize_regex = Anonymize(my_dict, use_word_boundaries=True)
```

It is also possible to specify how to re-zip unzipped folders:

```python
# specifying a zip-format to zip unpacked archives after processing (.zip is default)
anonymize_zip = Anonymize('/Users/casper/Desktop/keys.csv', zip_format='gztar')
```

### 4. Substitute data

The `substitute` method is the step where the specified keys will be replaced by the replacements. It will replace all occurrences of the specified words with the substutions, in all files in the provided source folder.

Basic use:
```python
anonymize_object.substitute(source_path, target_path)
```

Arguments:
- `source_path` (required) path to the original file, folder or zip-archive to perform the substitutions on, either a string or a [Path](https://docs.python.org/3/library/pathlib.html#basic-use) object
- `target_path` (optional): a string or [Path](https://docs.python.org/3/library/pathlib.html#basic-use) object indicating whre the results need to be written. The path will be created if it does not yet exist.

If `target_path` is provided, anonymoUUs will create a processed copy of the source into the target folder. If the source is a single file, and the file path does not contain elements that will be replaced, and the target folder is identical to the source folder, then the processed result will get a 'copy' extension to prevent overwriting.

When `target_path` is omitted, the source will be overwritten by a processed version of it.

```python
# process the datadownload.zip file, replace all patterns and write a copy to the 'bucket' folder.
anonymize_regex.substitute(
    '/Users/casper/Desktop/datadownload.zip', 
    '/Users/casper/Desktop/bucket'
)

# process the 'download' folder and replace the original by its processed version
anonymize_regex.substitute('/Users/casper/Desktop/download')

# process a single file, and replace it
anonymize_regex.substitute('/Users/casper/Desktop/my_file.json')
```

## Validation
The validation procedure determines the performance of anonymization software. 
It compares results of the automated anonymization with a manually labeled ground-truth. 
All occurrences of personal identifiable information in the ground-truth should be detected and correctly substituted in the automatically de-identified version.

### Prepare
Clone this repository to run the validation 
Make sure you have these data present:
* anonymized files
* key file
* manually labeled ground truth (created with Label Studio; json format)
Example data can be found in the [test_data](test_data/) in this folder

### Validate
Run from the commandline
```
$ cd tests
$ python validation.py [OPTIONS]

Options:
  --anymdir  path to folder with anonymized data
  --gtfile  path to labeled groundtruth file
  --keyfile  path to key file

```

## Attribution and academic use
The code in this project is licensed with [MIT](LICENSE.md).
This software is archived at Zenodo [![DOI](https://zenodo.org/badge/281087099.svg)](https://zenodo.org/badge/latestdoi/281087099)
Please cite this software using the metadata in the [citation file](CITATION.cff)

## Contributing
Contributions are what make the open source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

You can contribute by:
1. Opening an Issue
2. Suggesting edits to the code
3. Suggesting edits to the documentation
4. If you are unfamiliar with GitHub, feel free to [contact](#contact) us.

To contribute to content directly:

1. Fork the project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Contact
You can contact the Utrecht University Research Engineering team [by email](mailto:research.engineering@uu.nl).

Project Link: [https://github.com/UtrechtUniversity/anonymouus](https://github.com/UtrechtUniversity/anonymouus).
