#    Copyright 2018 Simon Biggs

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""A set of utilities to manage the docker instance of qatrack
"""

import sys
import os
import zipfile
import time
import datetime
# import shutil
import pathlib
import subprocess
from glob import glob

import psycopg2


DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_HOST = "qatrack-postgres"
DB_PORT = 5432

QATRACK_DIRECTORY = "/usr/src/qatrackplus"
UPLOADS_DIRECTORY: str = os.path.join(
    QATRACK_DIRECTORY, "qatrack/media/uploads")
SITE_CSS: str = os.path.join(
    QATRACK_DIRECTORY, "qatrack/static/qatrack_core/css/site.css")

DATA_DIRECTORY: str = os.path.join(
    QATRACK_DIRECTORY, "deploy/docker/user-data")
BACKUP_DIRECTORY: str = os.path.join(
    DATA_DIRECTORY, "backup-management/backups")
RESTORE_DIRECTORY: str = os.path.join(
    DATA_DIRECTORY, "backup-management/restore")

DATABASE_DUMP_FILE: str = 'database_dump.sql'


def wait_for_postrgres():
    """Use this to wait for postgres to be ready
    """
    while True:
        try:
            with psycopg2.connect(database=DB_NAME, user=DB_USER,
                                  password=DB_PASSWORD, host=DB_HOST) as conn:
                conn
                break

        except psycopg2.OperationalError:
            time.sleep(1)


def run_backup():
    """A method to backup qatrackplus, this needs to be rewritten to directly
    use postgres
    """

    pathlib.Path(BACKUP_DIRECTORY).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.fromtimestamp(
        time.time()).strftime('%Y%m%d%H%M%S')

    backup_filepath = os.path.join(
        BACKUP_DIRECTORY, 'UTC_{}.zip'.format(timestamp))

    wait_for_postrgres()

    popen = subprocess.Popen(
        ['pg_dump', '-h', DB_HOST, '-U', DB_USER],
        stdout=subprocess.PIPE)

    with zipfile.ZipFile(backup_filepath, 'w') as backup_zip:
        backup_zip.writestr(DATABASE_DUMP_FILE, popen.stdout.read())
        popen.wait()

        for dirname, _, files in os.walk(UPLOADS_DIRECTORY):
            backup_zip.write(dirname)
            for filename in files:
                backup_zip.write(os.path.join(dirname, filename))

        backup_zip.write(SITE_CSS)

    popen = subprocess.Popen(
        ['stat', '-c', '%u:%g', '/usr/src/qatrackplus'],
        stdout=subprocess.PIPE)
    subprocess.run(
        ['chown', '-R', popen.stdout.read().rstrip(), backup_filepath])
    popen.wait()


def run_restore():
    """A method to restore a qatrackplus backup, this needs to be rewritten to
    directly use postgres
    """

    pathlib.Path(RESTORE_DIRECTORY).mkdir(parents=True, exist_ok=True)

    restore_filelist = glob(os.path.join(RESTORE_DIRECTORY, '*.zip'))

    if len(restore_filelist) == 1:
        restore_filepath = restore_filelist[0]
        print('Restoring QATrack+ from {}'.format(
            os.path.basename(restore_filepath)))

        # Don't remove previous uploads, they will get overwritten if they
        # have the same name
        # shutil.rmtree(UPLOADS_DIRECTORY)

        print('Files restored:')
        with zipfile.ZipFile(restore_filepath, 'r') as restore_zip:
            restore_zip.extract(DATABASE_DUMP_FILE)

            for filename in restore_zip.namelist():
                if filename.startswith('usr/src/qatrackplus/'):
                    print(filename)
                    restore_zip.extract(filename, '/')

        print('Restoring database:')
        sys.stdout.flush()
        wait_for_postrgres()

        with open(DATABASE_DUMP_FILE, 'r') as database_dump:

            with psycopg2.connect(database='template1', user=DB_USER,
                                  password=DB_PASSWORD, host=DB_HOST) as conn:
                with conn.cursor() as cur:
                    conn.autocommit = True
                    cur.execute("""
                        UPDATE pg_database
                        SET datallowconn = 'false'
                        WHERE datname = %s;""", (DB_NAME,))
                    cur.execute("""
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = %s;""", (DB_NAME,))
                    cur.execute("DROP DATABASE {};".format(DB_NAME))
                    cur.execute("CREATE DATABASE {};".format(DB_NAME))
                    cur.execute("""
                        UPDATE pg_database
                        SET datallowconn = 'true'
                        WHERE datname = %s;""", (DB_NAME,))

            subprocess.run(
                ['psql', '-h', DB_HOST, '-U', DB_USER, DB_NAME],
                stdin=database_dump)

        os.unlink(DATABASE_DUMP_FILE)
        os.unlink(restore_filepath)

    if len(restore_filelist) > 1:
        raise ValueError(
            'Only one restoration file should be placed within the restore '
            'directory')
