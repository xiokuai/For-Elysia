from setuptools import setup, Extension
from Cython.Build import cythonize
import os

ext_modules = [
    Extension(
        "zhiai._fastvm",
        ["zhiai/_fastvm.pyx"],
    )
]

setup(
    name="zhiai",
    ext_modules=cythonize(ext_modules, language_level="3"),
)
