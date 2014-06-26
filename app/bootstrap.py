from __future__ import print_function

from getpass import getpass
import readline
import sys
import os

import migrate.versioning.api as migrate
from migrate.versioning.exceptions import DatabaseAlreadyControlledError 

import annotateit
from annotateit import db
from annotateit.model import Consumer, User

if __name__ == '__main__':
    app = annotateit.create_app()

    print("\nCreating ElasticSearch indices... ")
    annotateit.create_indices(app)

    print("\nCreating SQLite database... ")

    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    print("AnnotateIt database URL: %s\n" % db_url)

    migrate_args = dict(url=db_url, debug='False', repository='migration')
    try:
        migrate.version_control(**migrate_args)
    except DatabaseAlreadyControlledError:
        print("  ...already created\n")

    migrate.upgrade(**migrate_args)

    print("done.\n")

    username = os.environ.get('ANNOTATEIT_USER', "admin")
    print("AnnotateIt admin user: %s\n" % username)

    password = os.environ.get('ANNOTATEIT_PASSWORD', "annotateit")
    print("AnnotateIt admin password set\n")

    email = os.environ.get('ANNOTATEIT_EMAIL', "admin@example.com")
    print("AnnotateIt admin email: %s\n" % email)

    ckey = 'annotateit'
    print("AnnotateIt primary consumer key: %s\n" % ckey)

    with app.test_request_context():
        print("\nCreating admin user... ")

        u = User(username, email, password)
        u.is_admin = True

        db.session.add(u)
        db.session.commit()

        print("done.")

        print("Creating primary consumer... ")

        c = Consumer(ckey)
        c.user_id = u.id

        db.session.add(c)
        db.session.commit()

        print("done.\n")

        print("Primary consumer secret: %s" % c.secret)
