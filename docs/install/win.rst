Installing and Deploying QATrack+ on Windows Server
===================================================


.. note::

    This guide assumes you have at least a basic level of familiarity with
    Windows Server, SQL Server Management Studio and the command line.


New Installation
----------------

This guide is going to walk you through installing QATrack+ on a Windows Server
2016 server with IIS 10 serving static assets (images, javascript and
stylesheets) and acting as a reverse proxy for a CherryPy web server which
serves our Django application (QATrack+).  SQL Server 2016 will be used as the
database.If you are upgrading an existing installation, please see the sections
below on upgrading from v0.2.8 or v0.2.9.


.. note::

    This guide assumes you have SQL Server Management Studio (SSMS) and Internet
    Information Services (IIS) installed/enabled


The steps we will be undertaking are:

.. contents::
    :local:
    :depth: 1


Installing git
~~~~~~~~~~~~~~

Go to http://git-scm.com and download the latest version of git (msysgit) for
Windows (Git-2.19.0 at the time of writing).  Run the installer.  I just leave
all the settings on the defaults but you are free to modify them if you like.


.. note::

    If you choose to use the default MinTTY over the Windows default console
    window, be aware you need to preface all python commands with 'winpty'
    for example 'winpty python manage.py migrate'



.. _install_py3_win:

Installing Python 3
~~~~~~~~~~~~~~~~~~~

Go to http://www.python.org/download/ and download the latest Python 3.6.X
(3.6.6 at the time of writing).  Run the installer and on the first page, make
sure you click the `Add Python 3.6 to PATH` option before choosing "Customize
Installation".

On the second page of the installer, leave the defaults and click "Next".

On the third page, make sure you have "Install for all users" selected (this
is important!) before clicking "Install".


.. warning::

    Python 3.7 is a recently released version of Python which is not
    compatible with Django 1.11 and hence QATrack+


Checkout the latest release of QATrack+ source code from BitBucket
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Open a Windows PowerShell terminal and then create a directory for QATrack+ and
check out the source code, use the following commands:

.. code-block:: console

    mkdir C:\deploy
    cd C:\deploy
    git clone https://bitbucket.org/tohccmedphys/qatrackplus.git



Setting up our Python environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ensure you have python3 installed correctly and on your PATH by running:

.. code-block:: console

    python --version
    # should print e.g. Python 3.6.6

We're now ready to install all the libraries QATrack+ depends on.

.. code-block:: console

    mkdir venvs
    python -m pip install --upgrade pip
    python -m venv venvs\qatrack3
    .\venvs\qatrack3\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    cd qatrackplus
    pip install -r requirements\win.txt
    python manage.py collectstatic

.. warning::

    If you are going to be using :ref:`Active Directory <active_directory>` for
    authenticating your users, you need to install pyldap.  There are binaries
    available on this page: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyldap.
    Download the binary relevant to your Python 3 installation (e.g.
    pyldap‑2.4.45‑cp36‑cp36m‑win_amd64.whl) and then pip install it:

    .. code-block:: console

        pip install C:\path\to\pyldap‑2.4.45‑cp36‑cp36m‑win_amd64.whl


Checking everything is functional so far
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Lets take a minute and check everything is now functioning as it should. Run
the QATrack+ test suite like so:

.. code-block:: console

    py.test -m "not selenium"

This should take a few minutes to run and should exit with output that looks
similar to the following:

.. code-block:: console

    Results (88.45s):
        440 passed
          2 skipped
         11 deselected


Creating a database with SQL Server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Open SQL Server Management Studio and enter 'localhost' for the server name and
click Connect.

In the Object Explorer frame, right click the Databases folder and select "New
Database...".

Enter 'qatrackplus' as the database name and click OK.

Back in the Object Explorer frame, right click on the main Security folder and
click New Login...  Set the login name to 'qatrack', select SQL Server
Authentication. Enter 'qatrackpass' (or whatever you like) for the password
fields and uncheck Enforce Password Policy. Click OK.

Back in the Object Explorer frame, expand the qatrackdb database,
right click on Security and select New->User.

Enter 'qatrack' as the User name and Login name and then in the
Database Role Membership (or Owned Schemas) region select 'db_datawriter', 'db_datareader' and
'db_owner'.  Click OK.

Configuring QATrack+ to use your new database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Copy the example local_settings file:

.. code-block:: console

    cp deploy\win\local_settings.py qatrack\local_settings.py


and then edit it setting the `DATABASES['default']['ENGINE']` key to
`sql_server.pyodbc`:


.. code-block:: python

    DEBUG = False

    DATABASES = {
        'default': {
            'ENGINE': 'sql_server.pyodbc',
            'NAME': 'qatrackplus',
            'USER': '',  # USER/PWD can usually be left blank if SQL server is running on the same server as QATrack+
            'PASSWORD': '',
            'HOST': '', # leave blank unless using remote server or SQLExpress (use 127.0.0.1\\SQLExpress or COMPUTERNAME\\SQLExpress)
            'PORT': '', # Set to empty string for default. Not used with sqlite3.
            'OPTIONS': {
            }
        }
    }

    ALLOWED_HOSTS = ['127.0.0.1', 'localhost']  # See local settings docs

We will load some configuration data into our new database from the command
prompt:

.. code-block:: console

    python manage.py migrate
    python manage.py createsuperuser
    Get-ChildItem .\fixtures\defaults\*\*json | foreach {python manage.py loaddata $_.FullName}


Configuring CherryPy to Serve QATrack+
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to have QATack+ start when you reboot your server, or restart after a
crash, we will run QATrack+ with a CherryPy server installed as a Windows
service (running on port 8080, see note below if you need to change the port).

.. code-block:: console

    cp deploy\win\QATrack3CherryPyService.py .
    python QATrack3CherryPyService.py --startup=auto install
    python QATrack3CherryPyService.py start


Your QATrack+ installation is now installed as a Windows Service running on
port 8080 (see note below).  You may also wish to configure the service to
email you in the event of a crash (see the Recovery tab of the
QATrackCherryPyService configuration dialogue).

.. note::

    If you need to run QATrack+ on a different port, edit
    C:\\deploy\\qatrackplus\\QATrack3CherryPyService.py and set the PORT
    variable to a different port (e.g. 8008)


Setting up IIS
~~~~~~~~~~~~~~

We are going to use IIS for two purposes: first, it is going to serve all of
our static media (css, js and images) and second it is going to act as a
reverse proxy to forward the QATrack+ specific requests to CherryPy.

Before starting please make sure you have both `URL Rewrite 2.0
<https://www.iis.net/downloads/microsoft/url-rewrite>`__ and `Application
Request Routing 3.0
<http://www.iis.net/downloads/microsoft/application-request-routing>`__ IIS
modules installed.

Enabling Proxy in Application Request Routing
.............................................

Application Request Routing needs to have the proxy setting enabled. To do
this, click on the top level server in the left side panel, and then double
click the `Application Request Routing` icon. In the `Actions` panel click the
`Server Proxy Settings` and then check `Enable proxy` at the top.  Leave all
the other settings the same and click `Apply` and then `Back to ARR Cache`.

Enabling Static Content Serving in IIS
......................................

IIS is not always set up to serve static content. To enable this, open the
Server Manager software, click Manage, then `Add Roles and Features` then
`Next`, `Next`.  In the `Roles` widget, select `Web Server(IIS)->Common HTTP
Features` and make sure `Static Content` is selected.


Setting up the site and URL rewrite rules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have Applicationn Request Routing installed and proxies enabled, in
the left panel of IIS under Sites, select the default Web Site and click Stop
on the right hand side.

.. figure:: images/stop_default.png
    :alt: Stop default website

    Stop default website

Now right click on Sites and click Add Web Site

.. figure:: images/stop_default.png
    :alt: Add a new web site

    Add a new web site

Enter QATrack Static for the Site Name and "C:\\deploy\\qatrackplus\\qatrack\\" for
the Physical Path then click OK and answer Yes to the warning.

To test that setup worked correctly open a browser on your server and enter the
address http://localhost/static/qa/img/tux.png You should see a picture of the
Linux penguin.

Next, select the top level server in the Connections pane and then double click
URL Rewrite (you may need to restart IIS if you installed it and don't see it
here)

.. figure:: images/url_rewrite.png
    :alt: URL Rewrite

    URL Rewrite

In the top right click Add Rule and select Blank Rule.

Give it a name of QATrack Static and enter ^(static|media)/.\* for the
Pattern field, and select None for the Action type.
Make sure `Stop processing of subsequent rules` is checked.

.. figure:: images/static_rule.png
    :alt: Static Rule

    Static URL Rewrite Rule

When finished click Apply, then Back To Rules and then add another blank rule.
Give it a name of QATrack Reverse Proxy, enter ^(.\*) for the Pattern and
http://localhost:8080/{R:1} for the Rewrite URL.  In the Server Variables
section add a new Server Variable with the Name=HTTP\_X\_FORWARDED\_HOST and
the Value=yourservername.com (replace yourservername with whatever your domain
is!).  Finally, make sure both Append query string and Stop processing of
subsequent rules are checked.

.. figure:: images/reverse_proxy.png
    :alt: URL Rewrite Reverse Proxy

    URL Rewrite Reverse Proxy

Your URL rewrites should look like the following (order is important!)

.. figure:: images/url_rules.png
    :alt: URL Rewrite rules

    URL Rewrite rules

You should now be able to visit http://localhost/ in a browser on your server
and see the QATrack+ login page.  Congratulations, you now have a functional
QATrack+ setup on your Windows Server!

.. note::

    There are many different ways to configure IIS.  The method I've used
    above is simple and works well when QATrack+ is the only web service
    running on a server.


What Next
~~~~~~~~~

* Check the :ref:`the settings page <qatrack-config>` for any available
  customizations you want to add to your QATrack+ installation (don't forget to
  restart your QATrack CherryPy Service after changing any settings!)

* Automate the :ref:`backup of your QATrack+ installation <qatrack_backup>`.

* Read the :ref:`Administration Guide <admin_guide>`, :ref:`User Guide
  <users_guide>`, and :ref:`Tutorials <tutorials>`.


Wrap Up
~~~~~~~

This guide shows only one of many possible method of deploying QATrack+ on
Windows.  It is very similar to what is used at The Ottawa Hospital Cancer
Centre and it has proven to be a very solid setup.  If you're stuck with a
Windows stack it will likely work for you too.  Please post on the
:mailinglist:`QATrack+ Google Group <>` if you get stuck!


Upgrading from version 0.2.8
----------------------------

In order to upgrade from version 0.2.8 you must first uprade to version 0.2.9.
If you hit an error along the way, stop and figure out why the error is
occuring before proceeding with the next step!  If you want assistance with the
process, please post to to the :mailinglist:`Mailing List <>`.

.. contents::
    :local:


Open A Terminal & Activate your virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We will use Powershell for this, but feel free to use Git Bash (or plain old
CMD) if you prefer.  Open a Powershell window and and activate your existing
virtual environment:

.. code-block:: console

    cd C:\deploy\
    .\venvs\qatrack\bin\Activate.ps1

    # or if you are using git bash then you need to do

    cd /c/deploy/
    source ./venvs/qatrack/bin/activate


Backing up your database
~~~~~~~~~~~~~~~~~~~~~~~~

It is **extremely** important you back up your database before attempting to
upgrade. It is recommended you use SQLServer Management Studio to dump a
backup file, but you can also generate a json dump of your database (possibly
extremely slow!):

.. code-block:: console

    cd C:\deploy\qatrackplus\
    python manage.py dumpdata --natural > backup-0.2.8-$(date -I).json


Checking out version 0.2.9
~~~~~~~~~~~~~~~~~~~~~~~~~~

First we must check out the code for version 0.2.9:

.. code-block:: console

    git fetch origin
    git checkout v0.2.9.1

.. warning::

    If you get any errors using git (e.g. trying to check out v0.2.9.1) that
    you don't know how to handle, please stop and get help!


Update your existing virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There were a number of changes in dependencies for version 0.2.9 so we need to
update our virtual env:

.. code-block:: console

    pip install --upgrade pip
    pip install -r requirements\base.txt


Migrate your database
~~~~~~~~~~~~~~~~~~~~~

The next step is to migrate the 0.2.8 database schema to 0.2.9:

.. code-block:: console

    python manage.py syncdb
    python manage.py migrate

Assuming that proceeds without errors you can proceed to `Upgrading from
version 0.2.9` below. If you get an error in this step, you may need to
adjust your local_settings.py file to include the `OPTIONS` key in your
`DATABASES` setting:

.. code-block:: python

    DATABASES = {
        'default': {
            'ENGINE': 'sqlserver_ado',
            'NAME': 'YOURDBNAME',
            'USER': '',
            'PASSWORD': '',
            'HOST': '',      # leave blank unless using remote server or SQLExpress (use 127.0.0.1\\SQLExpress or COMPUTERNAME\\SQLExpress)
            'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
            'OPTIONS': {
                'provider': 'sqlncli11', # might need to use 'sqlncli10',
                'use_legacy_date_fields': True,
            }
        }
    }



Upgrading from version 0.2.9
----------------------------

The steps below will guide you through upgrading a version 0.2.9 installation
to 0.3.0.  If you hit an error along the way, stop and figure out why the error
is occuring before proceeding with the next step!

.. contents::
    :local:

Verifying your Python 3 version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unlike QATrack+ v0.2.9 which runs on Python 2.7, QATrack+ 0.3.0 only runs on
Python version 3.5 or 3.6 (and probably 3.4!).  You will need to ensure you
have one of those Python versions installed.  Instructions for installing
Python 3.6 are :ref:`given above <install_py3_win>`. After installing Python 3
open a new PowerShell window and verify Python3 is installed correctly:


.. code-block:: console

    python --version
    # should result in e.g.
    Python 3.6.6


.. note::

    If your python version says 2.7.x then you need to edit your PATH
    environment variable. Remove Python 2 paths and/or insert Python 3 paths.


Backing up your database
~~~~~~~~~~~~~~~~~~~~~~~~

It is **extremely** important you back up your database before attempting to
upgrade. It is recommended you use SQLServer Management Studo to dump a backup
file, but you can also generate a json dump of your database (possibly
extremely slow!):

.. code-block:: console


    cd C:\deploy\
    .\venvs\qatrack\bin\Activate.ps1
    cd qatrackplus\
    python manage.py dumpdata --natural > backup-0.2.9-$(date -I).json


Checking out version 0.3.0
~~~~~~~~~~~~~~~~~~~~~~~~~~

First we must check out the code for version 0.3.0:

.. code-block:: console

    git fetch origin
    git checkout v0.3.0.13


Create and activate your new virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you currently have a virtualenv activated, deactivate it with the
`deactivate` command:

.. code-block:: console

    deactivate


We need to create a new virtual environment with the Python 3 interpreter:

.. code-block:: console

    cd C:\deploy
    python -m pip install --upgrade pip
    python -m venv .\venvs\qatrack3
    .\venvs\qatrack3\Scripts\Activate.ps1

We're now ready to install all the libraries QATrack+ depends on.

.. code-block:: console

    cd C:\deploy\qatrackplus\
    python -m pip install --upgrade pip
    pip install -r requirements\win.txt
    python manage.py collectstatic

.. warning::

    If you are going to be using :ref:`Active Directory <active_directory>` for
    authenticating your users, you need to install pyldap.  There are binaries
    available on this page: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyldap.
    Download the binary relevant to your Python 3 installation (e.g.
    pyldap‑2.4.45‑cp36‑cp36m‑win_amd64.whl) and then pip install it:

    .. code-block:: console

        pip install C:\path\to\pyldap‑2.4.45‑cp36‑cp36m‑win_amd64.whl


Update your local_settings.py file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now is a good time to review your `local_settings.py` file. There are a few
new settings that you may want to configure.  The settings are documented in
:ref:`the settings page <qatrack-config>`. Most importantly you need to
update your database driver to use `sql_server.pyodbc`. Open your
local_settings.py file and set the DATABASES['default']['ENGINE'] key to
`sql_server.pyodbc`. If you had any `OPTIONS` keys set, you should remove
those:


.. code-block:: python

    DATABASES = {
        'default': {
            'ENGINE': 'sql_server.pyodbc',
            'NAME': 'yourdatabasename',
            'USER': '',
            'PASSWORD': '',
            'HOST': '',
            'PORT': '',
            'OPTIONS': {
            }
        }
    }


Migrate your database
~~~~~~~~~~~~~~~~~~~~~

The next step is to update the v0.2.9 schema to v0.3.0:

.. code-block:: console

    python manage.py migrate --fake-initial

and load some initial service log data:

.. code-block:: console

    Get-ChildItem .\fixtures\defaults\units\*json | foreach {python manage.py loaddata $_.FullName}
    Get-ChildItem .\fixtures\defaults\service_log\*json | foreach {python manage.py loaddata $_.FullName}

Check the migration log
.......................

During the migration above you may have noticed some warnings like:


    | Note: if any of the following tests process binary files (e.g. images, dicom files etc) rather than plain text, you must edit the calculation and replace 'FILE' with 'BIN_FILE'. Tests:
    |
    | Test name 1 (test-1)
    | Test name 2 (test-2)
    | ...

This data is also available in the `logs\migrate.log` file.  Because the way
Python handles text encodings / files has changed in Python 3, you will
need to update any upload test that handles binary data by changing the
`FILE` reference in the calculation procedure to `BIN_FILE`. For example change:

.. code-block:: python

    data = FILE.read()
    # do something with data

to:

.. code-block:: python

    data = BIN_FILE.read()
    # do something with data


You may have also seen warnings like:


    |  The test named 'yourtestname' with ID=1234 needs to be updated to be
    |  compatible with Python 3.


While most Test calculation procedures will be compatible with both Python 2
and Python 3, there have been some syntactical changes in the language which
may require you to update a calculation procedure to be Python 3 compatible.


Update your CherryPy Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First, stop your existing `QATrack CherryPy Service` using the `Services`
Windows application. Then back in your PowerShell window you can install
our new Python 3 CherryPy Windows Service:

.. code-block:: console

    cp deploy\win\QATrack3CherryPyService.py .
    python QATrack3CherryPyService.py --startup=auto install
    python QATrack3CherryPyService.py start


Your QATrack+ v0.3.0 installation is now running as a Windows Service on port
8080 (see note below).  You may also wish to configure the service to email you
in the event of a crash (see the Recovery tab of the QATrackCherryPyService
configuration dialogue).

.. note::

    If you need to run QATrack+ on a different port, edit
    C:\\deploy\\qatrackplus\\QATrack3CherryPyService.py and set the PORT
    variable to a different port (e.g. 8008)


Once you have verified everything is working correctly, you can either
disable the automatic startup of your original QATrackCherryPyService, or
delete the service entirely.


IIS Changes
~~~~~~~~~~~

If you plan on using the QATrack+ API, you will want to modify your reverse
proxy url rewrite and add a new Server Variable.  Open up IIS and navigate
to your reverse proxy rewrite rule and then in the Server Variables
section add a new Server Variable with the Name=HTTP\_X\_FORWARDED\_HOST and
the Value=yourservername.com (replace yourservername with whatever your domain
is!).

.. figure:: images/reverse_proxy.png
    :alt: URL Rewrite Reverse Proxy

    URL Rewrite Reverse Proxy


Last Word
~~~~~~~~~

There are a lot of steps getting everything set up so don't be discouraged if
everything doesn't go completely smoothly! If you run into trouble, please get
in touch on the :mailinglist:`mailing list <>`.

