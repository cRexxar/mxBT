from distutils.core import setup
from setuptools import find_packages

setup(
    name='mexcBT',
    version='0.0.1',
    author='rexxar&stephen',
    # py_modules=['mexcBacktest']
    packages=find_packages('readyForInstall'),
    package_dir = {'': 'readyForInstall'},
    install_requires = [
        'cached-property==1.5.2',
        'cycler==0.11.0',
        'fonttools==4.33.3',
        'h5py==3.6.0',
        'kiwisolver==1.4.2',
        'matplotlib==3.5.1',
        'numpy==1.21.6',
        'packaging==21.3',
        'pandas==1.3.5',
        'Pillow==9.1.0',
        'plotly==5.7.0',
        'pyparsing==3.0.8',
        'python-dateutil==2.8.2',
        'pytz==2022.1',
        'scipy==1.7.3',
        'seaborn==0.11.2',
        'six==1.16.0',
        'tenacity==8.0.1',
        'typing-extensions==4.2.0',
    ]
)