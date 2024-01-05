
from opcon.modules import director
from opcon.modules import auth
from opcon.modules import config
from opcon.modules import accesslog
from opcon.modules import auditlog
from opcon.bosh.bosh_bp import bosh_bp
from opcon.api.api_bp import api_bp
from flask import (
    Flask,
    render_template,
    request,
    Response,
    redirect,
    url_for
)
from flask_apscheduler import APScheduler
from flask_bootstrap import Bootstrap
import requests
import uuid
import os
import sys
import time
import json
import re

# set up primary objects
app = Flask(__name__)
Bootstrap(app)
app.config['JSON_AS_ASCII'] = True
app.config['SECRET_KEY'] = uuid.uuid4().hex
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# main configuration dictionary
config = config.config(config_file=os.getenv('CONFIG_FILE', 'opcon.ini'))
if config.get('o_debug'):
    app.config['DEBUG'] = config.get('o_debug')
if config.get('o_auth_type'):
    app.config['USER_AUTH_TYPE'] = config.get('o_auth_type')
    app.config['USER_AUTH_DATA'] = config.get('o_auth_data')
    app.config['USER_AUTH_MOD'] = config.get('o_auth_mod')
    app.config['USER_AUTH_DEBUG'] = config.get('o_auth_debug')
    app.config['USER_AUTH_BRAND'] = config.get('o_auth_brand')
else:
    print("No auth type configured; this isn't going to go well", file=sys.stderr)
    sys.exit(1)
errands_acls = config.get('errands_acls')

user_auth = auth.user_authentication(app)
user_auth.ua_login_manager.init_app(app)
user_auth.ua_login_manager.login_view = 'login'

director = director.Director(config.get('o_director_url'),
                             config.get('o_bosh_user'),
                             config.get('o_bosh_pass'),
                             debug=config.get('o_debug'),
                             testing=config.get('o_testing'),
                             verify_tls=config.get('o_verify_tls'),
                             errands=errands_acls,
                             readonly=config.get('o_readonly'))
app.config.update({'AUTH': user_auth, 'DIRECTOR': director})
app.config.update({
    'DEPLOYMENT_GITHASH': os.getenv('DEPLOYMENT_GITHASH', 'no_hash'),
    'DEPLOYMENT_DATE': os.getenv('DEPLOYMENT_DATE', time.asctime()),
    'DEPLOYMENT_ACTOR': os.getenv('DEPLOYMENT_ACTOR', 'unknown')
    })

if config.get('o_audit_enable'):
    auditlog = auditlog.AuditLog(config.get('o_audit_data'),
                                 extra_fields=config.get('o_audit_extra_fields'),
                                 debug=config.get('o_audit_debug'))
    app.config.update({'AUDIT': auditlog})


# add jinja template for converting "Epoch" dates to time strings
@app.template_filter('datetime')
def format_datetime(value):
    return time.ctime(value)


@app.template_filter('regex_replace')
def regex_replace(s, find, replace):
    return re.sub(find, replace, s)


@app.route("/index.html")
@app.route("/")
@user_auth.flask_login_required
@accesslog.log_access
def index():
    return render_template("index.html", director=director,
                           stats=director.get_director_stats())


@app.route('/version', methods=['GET'])
def deployment_info():
    dpl_d = {'git_hash': app.config['DEPLOYMENT_GITHASH'],
             'deployment_date': app.config['DEPLOYMENT_DATE'],
             'deployment_actor': app.config['DEPLOYMENT_ACTOR']}
    return Response(json.dumps(dpl_d, indent=2),
                    status=200, content_type='application/json')


@user_auth.ua_login_manager.user_loader
def load_user(id):
    return user_auth.user_loader(id)


@app.route('/_callback', methods=['GET'])
def login_callback():
    auth_type = user_auth.ua_lib.auth_type
    if auth_type != 'oidc':
        print("got callback for non-oidc auth agent")
        return Response('not oidc enabled', 401)
    next_url = request.args.get('next')
    if not next_url:
        next_url = url_for('index')
    code = request.args.get("code")
    if not code:
        print("got callback with no code")
        # return all arguments for failing callback
        return render_template("login_failed.html", fail_args=request.args)
    # have auth code, next link - get token, and redirect there
    token_url, headers, body = user_auth.ua_lib.prepare_token_request(code)
    token_r = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(user_auth.ua_lib.client_id,
              user_auth.ua_lib.client_secret))
    if not token_r.ok:
        print("Failed to get token from {}: {}".format(token_url, token_r.text))
        return redirect(url_for('index'))
    # parse tokens
    token_dict = token_r.json()
    username = user_auth.ua_lib.get_user_from_token(token_dict['id_token'])
    user_auth.login_user(username, token_dict)
    # now that we've completed the user login, redirect back to "next"
    return redirect(next_url)


@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.args.get('next')
    if next_url is not None and not next_url.startswith('http'):
        next_url = url_for('index')
    ua_type = user_auth.ua_lib.auth_type
    ua_debug = app.config['USER_AUTH_DEBUG']
    if ua_debug:
        print("ua_type={}".format(ua_type))
    if request.method == 'POST':
        if ua_type == 'userpass':
            username = request.form['username']
            password = request.form['password']
            user_auth.login_user(username, password)
            return redirect(next_url)
        elif ua_type == 'oidc':
            request_uri = user_auth.ua_lib.prepare_request_uri(
                user_auth.ua_lib.oidc_config['authorization_endpoint'],
                redirect_url="/_callback",
                scope=["openid", "email", "profile"])
            if ua_debug:
                print("POST oidc render brand={} request_uri={}".format(
                    user_auth.ua_lib.auth_brand,
                    user_auth.ua_lib.code_request_uri))
            render_template("login_oidc.html",
                            ua_brand=user_auth.ua_lib.auth_brand,
                            ua_action=user_auth.ua_lib.request_uri)
        return render_template("login_csv.html")
    if request.method == 'GET':
        # GET assumes we want to login, redirect to form based on ua_type
        if ua_type == 'userpass':
            return render_template('login_csv.html')
        elif ua_type == 'oidc':
            if ua_debug:
                print("GET oidc render brand={} code_request_uri={}".format(
                    user_auth.ua_lib.auth_brand,
                    user_auth.ua_lib.code_request_uri))
            return render_template('login_oidc.html',
                                   ua_brand=user_auth.ua_lib.auth_brand,
                                   ua_action=user_auth.ua_lib.code_request_uri)
        else:
            return render_template('login_csv.html')
    return render_template(url_for('index'))


@app.route('/login_redirect', methods=['GET', 'POST'])
def login_redirect():
    if request.method == 'POST':
        print("request POST args: {}".format(request.form))
    elif request.method == 'GET':
        print("request GET args: {}".format(request.args))
    return Response('isallright', 200)


@app.route('/logout')
@accesslog.log_access
def logout():
    user_auth.logout_user()
    return redirect(url_for('index'))


app.register_blueprint(bosh_bp, url_prefix='/bosh')
print("api enabled:", config.get('o_api_enable'))
if config.get('o_api_enable'):
    app.register_blueprint(api_bp, url_prefix='/api')


if not director.connect() and not config.get('o_testing'):
    print("Cannot connect to director {}; exiting".format(config.get('o_director_url')))
    sys.exit(1)
if not config.get('o_testing'):
    director.login()
    director.get_deployments()
print("scheduled oauth update in %d seconds" % (
    director.oauth_token_expires() - 30))
scheduler.add_job(id='oauth-refresh',
                  func=director.refresh_token,
                  trigger='interval',
                  seconds=director.oauth_token_expires() - 30)
scheduler.add_job(id='deployments-refresh',
                  func=director.get_deployments,
                  trigger='interval',
                  seconds=120)
if __name__ == '__main__':
    app.run(debug=config['o_debug'])
