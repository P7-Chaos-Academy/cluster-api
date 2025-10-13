from setuptools import setup, find_packages

setup(
    name="kubernetes-job-api",
    version="1.0.0",
    description="A REST API for creating and managing Kubernetes jobs",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "Flask==2.3.3",
        "flask-restx==1.3.0", 
        "kubernetes==27.2.0",
        "PyYAML==6.0.1",
        "Werkzeug==2.3.7",
        "marshmallow==3.20.1"
    ],
    entry_points={
        "console_scripts": [
            "k8s-job-api=run:main",
        ],
    },
)