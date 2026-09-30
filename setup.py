from setuptools import setup, find_packages

setup(
    name='intent_platform',
    version='0.1.0',
    package_dir={'intent_platform': '.'},
    packages=['intent_platform', 'intent_platform.core', 'intent_platform.ui', 'intent_platform.config', 'intent_platform.database'],
)
