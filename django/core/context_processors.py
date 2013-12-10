"""
A set of request processors that return dictionaries to be merged into a
template context. Each function takes the request object as its only parameter
and returns a dictionary to add to the context.

These are referenced from the setting TEMPLATE_CONTEXT_PROCESSORS and used by
RequestContext.
"""

from django.conf import settings
from django.utils.encoding import StrAndUnicode

def auth(request):
    """
    Returns context variables required by apps that use Django's authentication
    system.

    If there is no 'user' attribute in the request, uses AnonymousUser (from
    django.contrib.auth).
    """
    if hasattr(request, 'user'):
        user = request.user
    else:
        from django.contrib.auth.models import AnonymousUser
        user = AnonymousUser()
    context_extras = {
        'user': user,
        'perms': PermWrapper(user),
    }
    # Add authentication (and session) LazyMessages to the context too.
    context_extras.update(messages(request))
    return context_extras

def messages(request):
    """
    Returns messages for the session and the current user.

    Note that this processor is only useful to use explicity if you are not
    using the (enabled by default) auth processor, as it also provides the
    messages (by calling this method).

    The messages are lazy loaded, so no messages are retreived and deleted
    unless requested from the template.

    Both contrib.session and contrib.auth are optional. If neither is provided,
    no 'messages' variable will be added to the context.
    """
    if hasattr(request, 'session') or hasattr(request, 'user'):
        return {'messages': LazyMessages(request)}
    return {}

def debug(request):
    "Returns context variables helpful for debugging."
    context_extras = {}
    if settings.DEBUG and request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS:
        context_extras['debug'] = True
        from django.db import connection
        context_extras['sql_queries'] = connection.queries
    return context_extras

def i18n(request):
    context_extras = {}
    context_extras['LANGUAGES'] = settings.LANGUAGES
    if hasattr(request, 'LANGUAGE_CODE'):
        context_extras['LANGUAGE_CODE'] = request.LANGUAGE_CODE
    else:
        context_extras['LANGUAGE_CODE'] = settings.LANGUAGE_CODE

    from django.utils import translation
    context_extras['LANGUAGE_BIDI'] = translation.get_language_bidi()

    return context_extras

def media(request):
    """
    Adds media-related context variables to the context.

    """
    return {'MEDIA_URL': settings.MEDIA_URL}

def request(request):
    return {'request': request}

# PermWrapper and PermLookupDict proxy the permissions system into objects that
# the template system can understand.

class PermLookupDict(object):
    def __init__(self, user, module_name):
        self.user, self.module_name = user, module_name

    def __repr__(self):
        return str(self.user.get_all_permissions())

    def __getitem__(self, perm_name):
        return self.user.has_perm("%s.%s" % (self.module_name, perm_name))

    def __nonzero__(self):
        return self.user.has_module_perms(self.module_name)

class PermWrapper(object):
    def __init__(self, user):
        self.user = user

    def __getitem__(self, module_name):
        return PermLookupDict(self.user, module_name)

# LazyMessages is used by the `messages` and `auth` context processors.

class LazyMessages(StrAndUnicode):
    """
    A lazy proxy for session and authentication messages.
    """
    def __init__(self, request):
        self.request = request

    def __iter__(self):
        return iter(self.messages)

    def __len__(self):
        return len(self.messages)

    def __nonzero__(self):
        return bool(self.messages)

    def __unicode__(self):
        return unicode(self.messages)

    def _get_messages(self):
        if hasattr(self, '_messages'):
            return self._messages
        # First, retreive any messages for the user.
        if hasattr(self.request, 'user') and \
           hasattr(self.request.user, 'get_and_delete_messages'):
            self._messages = self.request.user.get_and_delete_messages()
        else:
            self._messages = []
        # Next, retrieve any messages for the session.
        if hasattr(self.request, 'session'):
            self._messages += self.request.session.get_and_delete_messages()
        return self._messages
    messages = property(_get_messages)
