from setuptools import setup, find_packages

setup(
    name='aioprogress',
    version='0.1.1',
    description='A high-performance, flexible async file downloader built with aiohttp.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Javad Dalirani',
    author_email='jdalirani82@example.com',
    url='https://github.com/javad2nd/aioprogress',
    packages=find_packages(),
    python_requires='>=3.7',
    install_requires=[
        'aiohttp',
        'aiofiles',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
