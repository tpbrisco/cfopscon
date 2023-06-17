import functools
from flask import has_request_context, request, current_app
import flask_login
import time


def log_access(fn):
    @functools.wraps(fn)
    def log_url_access(*args, **kwargs):
        if has_request_context():
            query = ''
            if len(request.query_string):
                query = '?{}'.format(request.query_string.decode('utf8'))
            if 'X-Forwarded-For' in request.headers:
                origin = request.headers.get('X-Forwarded-For').split(',')[0]
            else:
                origin = request.remote_addr
            if 'AUDIT' in current_app.config and current_app.config['AUDIT']:
                alog = {
                    'origin': origin,
                    'receive_time': time.strftime('%Y/%m/%d %H:%M:%ST%z', time.localtime()),
                    'username': flask_login.current_user.username.decode('utf-8'),
                    'http_method': request.method,
                    'path': request.path,
                    'query': query
                }
                current_app.config['AUDIT'].send(alog)
            print('access {} {} {} \"{} {}{}\"'.format(
                origin,
                time.strftime('[%Y/%m/%d %H:%M:%ST%z]', time.localtime()),
                flask_login.current_user.username.decode('utf-8'),
                request.method,
                request.path,
                query))
        return fn(*args, **kwargs)
    return log_url_access
