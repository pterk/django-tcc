from setuptools import setup, find_packages

version = '0.1'

setup(
    name='tcc',
    version=version,
    description="Simple but effective comments app",
    #long_description=open('readme').read(),
    keywords='',
    author='Peter van Kampen',
    author_email='pterk@datatailors.com',
    url='',
    license='BSD',
    packages=find_packages(),
    # namespace_packages=[],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
)
