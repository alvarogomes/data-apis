from setuptools import setup, find_packages

setup(
    name='data-apis',
    version='0.1',
    packages = ['client'],
    include_package_data=True,
    install_requires=[
        'click',
        'httpx'
    ],
    entry_points='''
        [console_scripts]
        data-apis=client.main:cli
    ''',
)