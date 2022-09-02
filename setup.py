from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='anonymoUUs',
    version='0.0.10',
    description='A tool to substitue patterns/names in a file tree',
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url='https://github.com/UtrechtUniversity/anonymouus',
    author='C.S. Kaandorp, M.D. Schermer',
    author_email='m.d.schermer@uu.nl',
    license='MIT',
    packages=['anonymouus'],
    python_requires = '>=3.10',
    zip_safe=False,
    install_requires=['pandas','charset_normalizer','xlrd','odfpy','openpyxl','xlsxwriter']
)
