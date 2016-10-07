DEBUG = False
TEMPLATE_DEBUG = DEBUG

SELENIUM_USE_CHROME = False

DATABASES = {
    'default': {
        'ENGINE': 'sqlserver_ado',
        'NAME': 'qatrackplus',
        'USER': 'qatrackplus',
        'PASSWORD': 'qatrackplus',
        'HOST': '',
        'PORT': '',
        'OPTIONS': {
            'provider': 'sqlncli11'
        }
    }
}

ALLOWED_HOSTS = ['*']
