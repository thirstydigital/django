import hashlib
import re

from django.conf import settings
from django import http
from django.utils.text import compress_sequence, compress_string
from django.utils.cache import patch_vary_headers

re_accepts_gzip = re.compile(r'\bgzip\b')

class GZipMiddleware(object):
    """
    This middleware compresses content if the browser allows gzip compression.
    It sets the Vary header accordingly, so that caches will base their storage
    on the Accept-Encoding header.
    """
    def process_response(self, request, response):
        # It's not worth attempting to compress really short responses.
        if hasattr(response, 'content') and len(response.content) < 200:
            return response

        patch_vary_headers(response, ('Accept-Encoding',))

        # Avoid gzipping if we've already got a content-encoding.
        if response.has_header('Content-Encoding'):
            return response

        # MSIE have issues with gzipped response of various content types.
        if "msie" in request.META.get('HTTP_USER_AGENT', '').lower():
            ctype = response.get('Content-Type', '').lower()
            if not ctype.startswith("text/") or "javascript" in ctype:
                return response

        ae = request.META.get('HTTP_ACCEPT_ENCODING', '')
        if not re_accepts_gzip.search(ae):
            return response

        if hasattr(response, 'content'):
            # Return the compressed content only if it's actually shorter.
            compressed_content = compress_string(response.content)
            if len(compressed_content) >= len(response.content):
                return response
            response.content = compressed_content
            response['Content-Length'] = str(len(response.content))
        elif hasattr(response, 'streaming_content'):
            # Delete the `Content-Length` header for streaming content, because
            # we won't know the compressed size until we stream it.
            response.streaming_content = \
                compress_sequence(response.streaming_content)
            del response['Content-Length']
        else:
            # Return the original response, because we don't know how to
            # replace it's content.
            return response
        response['Content-Encoding'] = 'gzip'

        # Use ETags, if requested.
        if settings.USE_ETAGS:
            if hasattr(response, 'content'):
                etag = '"%s;gzip"' % hashlib.md5(response.serialize()).hexdigest()
            elif response.has_header('ETag'):
                etag = re.sub(r'"$', ';gzip"', response['ETag'])
            if 'etag' in locals():
                if 200 <= response.status_code < 300 and request.META.get('HTTP_IF_NONE_MATCH') == etag:
                    cookies = response.cookies
                    response = http.HttpResponseNotModified()
                    response.cookies = cookies
                else:
                    response['ETag'] = etag

        return response
