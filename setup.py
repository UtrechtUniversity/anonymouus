from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='UUnonymous',
    version='0.0.1',
    description='A tool to substitue patterns/names in a file tree',
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url='https://github.com/UtrechtUniversity/uunonymous',
    author='C.S. Kaandorp',
    author_email='c.s.kaandorp@uu.nl',
    license='MIT',
    packages=['uunonymous'],
    python_requires = '>=3.6',
    zip_safe=False
)