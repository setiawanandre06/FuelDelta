"""Package metadata compatible with Python 3.3.5."""

from setuptools import find_packages, setup


setup(
    name="FuelDelta",
    version="0.1.0",
    description="Fuel-saving coaching for Assetto Corsa",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.3",
    install_requires=[],
)
