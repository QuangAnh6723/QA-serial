from setuptools import setup, find_packages

def parse_requirements(filename):
    """Read requirements.txt, bỏ dòng rỗng, comment."""
    with open(filename, "r") as f:
        lines = [line.strip() for line in f]
        reqs = [line for line in lines if line and not line.startswith('#')]
    return reqs

setup(
    name="serial-command-tester",
    version="1.0.0",
    description="PyQt6 Serial Command Tester",
    author="Your Name",
    packages=find_packages(),
    include_package_data=True,
    install_requires=parse_requirements("requirements.txt"),
    package_data={"": ["ui/*.ui"]},
)