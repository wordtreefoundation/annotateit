from __future__ import print_function

from getpass import getpass
import readline
import sys
import os

import migrate.versioning.api as migrate

import annotateit
from annotateit import db
from annotateit.model import Consumer, User

if __name__ == '__main__':
    app = annotateit.create_app()

    username = os.environ.get('ANNOTATEIT_USER', "admin")
    print("AnnotateIt admin user: %s" % username)

    password = os.environ.get('ANNOTATEIT_PASSWORD', "annotateit")
    print("AnnotateIt admin password: %s" % password)

    email = os.environ.get('ANNOTATEIT_EMAIL', "admin@example.com")
    print("AnnotateIt admin email: %s" % email)

    db_url = app.config['SQLALCHEMY_DATABASE_URI']
    print("AnnotateIt database URL: %s" % db_url)


    print("\nCreating ElasticSearch indices... ")
    annotateit.create_indices(app)
    print("done.\n")

    migrate_args = dict(url=db_url, debug='False', repository='migration')
    try:
        print("Creating SQLite database... ")
        migrate.version_control(**migrate_args)
        print("done.\n")
    except:
        print("  ...already created\n")

    print("Migrating database... ")
    migrate.upgrade(**migrate_args)
    print("done.")

    ckey = os.environ.get('CONSUMER_KEY', 'annotateit')
    csecret = os.environ.get('CONSUMER_SECRET', 'annotate.it.secret')

    with app.test_request_context():
        users_count = User.query.count()
        print("Users in DB: " + str(users_count))
        
        if users_count == 0:
            print("Creating admin user... ")

            u = User(username, email, password)
            u.is_admin = True

            db.session.add(u)
            db.session.commit()

            print("done.\n")

            print("Creating primary consumer... ")

            c = Consumer(ckey)
            c.user_id = u.id
            c.secret = csecret

            db.session.add(c)
            db.session.commit()

            print("done.\n")

            print("Primary consumer key: %s" % c.key)
            print("Primary consumer secret: %s" % c.secret)
        else:
            print("Updating primary consumer... ")

            u = User.query.filter(username='admin').first()
            c = Consumer.query.filter(user_id=u.id).first()

            c.key = ckey
            c.secret = csecret

            db.session.add(c)
            db.session.commit()

            print("done.\n")

            print("Primary consumer key: %s" % c.key)
            print("Primary consumer secret: %s" % c.secret)
