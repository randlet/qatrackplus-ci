DEBUG = False
TEMPLATE_DEBUG = DEBUG

SELENIUM_USE_CHROME = False

DATABASES = {
    'default': {
        'ENGINE': 'sql_server.pyodbc',
        'NAME': 'qatrackplus',
        'USER': 'sa',
        'PASSWORD': 'Password12!',
        'HOST': '',
        'PORT': '',
        'OPTIONS': {
            'unicode_results': True
        }
    }
}

ALLOWED_HOSTS = ['*']
