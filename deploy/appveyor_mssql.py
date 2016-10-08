DEBUG = False
TEMPLATE_DEBUG = DEBUG

SELENIUM_USE_CHROME = False

DATABASES = {
    'default': {
        'ENGINE': 'sql_server.pyodbc',
        'NAME': 'qatrackdb',
        'USER': 'sa',
        'PASSWORD': 'Password12!',
        'HOST': 'localhost\SQLExpress',
        'PORT': '',
        'OPTIONS': {
            'unicode_results': True
        }
    }
}

ALLOWED_HOSTS = ['*']
