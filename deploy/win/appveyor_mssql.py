DEBUG = False
TEMPLATE_DEBUG = DEBUG

SELENIUM_USE_CHROME = False

DATABASES = {
    'default': {
        'ENGINE': 'sql_server.pyodbc',
        'NAME': 'qatrackdb',
        'USER': 'sa',
        'PASSWORD': 'Password12!',
        'HOST': 'localhost\\SQL2019',
        'PORT': '',
        'OPTIONS': {}
    }
}
DATABASES['readonly'] = DATABASES['default']

ALLOWED_HOSTS = ['*']
