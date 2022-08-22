import pathlib
from typing import List, Any, Dict

from setuptools import setup, find_packages # type: ignore

def get_version(version_file: pathlib.Path) -> str:
    locls: Dict[Any, str] = {}
    exec(open(version_file).read(), {}, locls)
    return locls["__version__"]

root = pathlib.Path(__file__).parent.resolve()
readme_file = root/"README.md"
version_file = root/"src"/"cocotb_TileLink"/"_version.py"

if __name__ == "__main__":
    setup(
        name="cocotb-TileLink",
        license="Apache-2.0",
        version=get_version(version_file),
        author="Antmicro",
        description="TileLink cocotb drivers",
        long_description=readme_file.read_text(encoding="utf-8"),
        long_description_content_type="text/markdown",
        packages=find_packages("src"),
        package_dir={"": "src"},
        install_requires=[
            "cocotb>=1.5.0.dev,<1.7",
            "cocotb-bus>=0.2.1",
            "numpy"
        ],
        python_requires='>=3.5'
    )
