# anonymoUUs

anonymoUUs is a Python package for pseudonomizing strings in multiple files and folders at once.

The software in this package traverses a file-tree looking for keywords with the aim of replacing them with a substitute. The goal is to substitute multiple id strings in multiple files with pseudo ids to avoid tracable relationships between data batches. A single data batch typically consists of multiple nested folders that contain multiple files in multiple formats. The file contents, file names and folder names may or may not contain ids. AnonymoUUs will replace them all. The package also deals with zipped folders. 

The anonymoUUs software is applicable to multiple types of text-based files, like .txt, .html, .json and .csv. UTF-8 encoding is assumed. Users have several options to provide keyword-replacement mappings and to customize the behaviour of the software, visit the [usage section](#usage) for more information.  


## Table of Contents

- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
- [Usage](#usage)
    - [Subsection](#subsection)
- [Links](#links)
- [Contributing](#contributing)
- [Contact](#contact)

## Getting Started

### Prerequisites

To install and run this project you need to have [Python](https://www.python.org/) installed.


### Installation

To install the project, in your terminal run:

```sh
$ pip install anonymoUUs
```

## Manual
Get started with the anonymoUUs package by trying it out in this [notebook](/anonymouus/examples/try_testing.ipynb) manual

Prerequisites:
* download the testdata from the [test_data folder](/anonymouus/tests/test_data)
* make sure you have [jupyter notebook](https://jupyter.org/install) installed


## Usage

This section describes how to run the project. It is highly recommended to use screenshots (on MacOS the combination `shift+cmd+4` and `spacebar` creates great screenshots).

### Subsection

## Contributing

Contributions are what make the open source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

To contribute:

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


## Contact

UU Research Engineering team [contact us by email](mailto:research.engineering@uu.nl)

Project Link: [https://github.com/UtrechtUniversity/anonymouus](https://github.com/UtrechtUniversity/anonymouus)

