from setuptools import setup

# import ``__version__`` from code base
exec(open('lambdo/version.py').read())

setup(
    name='lambdo',
    version=__version__,

    # descriptive metadata for upload to PyPI
    description='Workflow engine for time series feature engineering and forecasting',
    author='Alexandr Savinov',
    author_email='savinov@conceptoriented.org',
    license='MIT License',
    keywords = "feature engineering, data science, machine learning, forecasting, time series",
    url='http://conceptoriented.org',

    test_suite='nose.collector',
    tests_require=['nose'],

    # dependencies
    install_requires=[
        'numpy>=1.14.5',
        'scipy>=1.1.0',
        'pandas>=0.23.3',
        'scikit-learn>=0.19.1',
    ],
    zip_safe=True,

    # package content (what to include)
    packages=['lambdo'],
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        '': ['*.md', '*.txt', '*.rst'],
        # And include any *.msg files found in the 'hello' package, too:
        'hello': ['*.msg'],
    },

    # It will generate lambdo.exe and lambdo-script.py in the Scripts folder of Python
    entry_points={
        'console_scripts': [
            'lambdo=lambdo.main:main'
        ],
    },
    # These files will be copied to Scripts folder of Python
    scripts=[
        #'scripts/lambdo.bat',
        #'scripts/lambdo',
        #'scripts/lambdo.py',
    ],
)
