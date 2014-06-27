from setuptools import setup, find_packages

setup(
    name = 'annotateit',
    version = '2.3.0',
    packages = find_packages(),

    install_requires = [
        'Flask==0.9',
        'Flask-Mail==0.7.2',
        'Flask-SQLAlchemy==0.16',
        'Flask-WTF==0.8',
        'SQLAlchemy==0.7.8',
        'sqlalchemy-migrate==0.7.2',
        'itsdangerous==0.17',
        'decorator==3.3.3',
        'iso8601==0.1.4',
        'negotiate==0.0.1',
        'elasticsearch',
        'PyJWT==0.1.4'
    ],
)
