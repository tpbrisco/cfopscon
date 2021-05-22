
from opcon.modules import director
from opcon.modules import boshforms
from opcon.modules import auth
from opcon.modules import config
from flask import (
    Flask,
    render_template,
    request,
    Response,
    redirect,
    stream_with_context,
    flash,
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

# see "is_gunicorn" comments below for confusion with gunicorn
# gunicorn gets very confused with command-line parsing options, even if
# unused. it appears the optparse library is stepped all over between the
# application and gunicorn libraries.
# "is_gunicorn" is used to disable the main application parsing (or even
# loading the optparse library)
is_gunicorn = "gunicorn" in os.getenv('SERVER_SOFTWARE', '')

# set up primary objects
app = Flask(__name__)
Bootstrap(app)
app.config['JSON_AS_ASCII'] = True
app.config['SECRET_KEY'] = uuid.uuid4().hex
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# main configuration dictionary
config = config.config(command_line=not is_gunicorn, config_file='opcon.ini')
if config.get('o_debug'):
    app.config['DEBUG'] = config.get('o_debug')
if config.get('o_auth_type'):
    app.config['USER_AUTH_TYPE'] = config.get('o_auth_type')
    app.config['USER_AUTH_DATA'] = config.get('o_auth_data')
    app.config['USER_AUTH_MOD'] = config.get('o_auth_mod')
    app.config['USER_AUTH_DEBUG'] = config.get('o_auth_debug')

user_auth = auth.user_authentication(app)
user_auth.ua_login_manager.init_app(app)
user_auth.ua_login_manager.login_view = 'login'


@app.route("/index.html")
@app.route("/")
@user_auth.flask_login_required
def index():
    return render_template("index.html", director=director,
                           stats=director.get_director_stats())


@user_auth.ua_login_manager.user_loader
def load_user(id):
    return user_auth.user_loader(id)


@app.route('/_callback', methods=['GET'])
def login_callback():
    auth_type = user_auth.ua_lib.auth_type
    if auth_type != 'oidc':
        return Response('not oidc enabled', 401)
    code = request.args.get("code")
    token_endpoint = user_auth.ua_lib.oidc_config['token_endpoint']
    token_url, headers, body = user_auth.ua_lib.client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code)
    token_r = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(user_auth.ua_lib.google_client_id,
              user_auth.ua_lib.google_client_secret))
    # parse tokens
    user_auth.ua_lib.client.parse_request_body_response(json.dumps(token_r.json()))
    # set up user as logged in
    userinfo_url = user_auth.ua_lib.oidc_config['userinfo_endpoint']
    uri, headers, body = user_auth.ua_lib.client.add_token(userinfo_url)
    userinfo_r = requests.get(uri, headers=headers, data=body)
    userinfo_data = userinfo_r.json()
    # print("userinfo_data: {}".format(json.dumps(userinfo_data, indent=2)))
    user_auth.login_user(userinfo_data['email'], userinfo_data['given_name'])
    # now that we've completed the user login, redirect back to "next"
    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    next = request.args.get('next')
    if not next and not next.startswith('http'):
        next = url_for('index')
    ua_type = user_auth.ua_lib.auth_type
    ua_debug = app.config['USER_AUTH_DEBUG']
    if ua_debug:
        print("ua_type={}".format(ua_type))
    if request.method == 'POST':
        if ua_type == 'userpass':
            username = request.form['username']
            password = request.form['password']
            user_auth.login_user(username, password)
            return redirect(next)
        elif ua_type == 'oidc':
            request_uri = user_auth.ua_lib.client.prepare_request_uri(
                user_auth.ua_lib.oidc_config['authorization_endpoint'],
                redirect_url="/_callback",
                scope=["openid", "email", "profile"])
            if ua_debug:
                print("POST oidc render brand={} request_uri={}".format(
                    user_auth.ua_lib.auth_brand,
                    user_auth.ua_lib.request_uri))
            render_template("login_oidc.html",
                            ua_brand=user_auth.ua_lib.auth_brand,
                            ua_action=user_auth.ua_lib.request_uri)
        return render_template("login_csv.html")
    else:
        # GET assumes we want to login, redirect to form based on ua_type
        if ua_type == 'userpass':
            return render_template('login_csv.html')
        elif ua_type == 'oidc':
            if ua_debug:
                print("GET oidc render brand={} request_uri={}".format(
                    user_auth.ua_lib.auth_brand,
                    user_auth.ua_lib.request_uri))
            return render_template('login_oidc.html',
                                   ua_brand=user_auth.ua_lib.auth_brand,
                                   ua_action=user_auth.ua_lib.request_uri)
        else:
            return render_template('login_csv.html')


@app.route('/login_redirect', methods=['GET', 'POST'])
def login_redirect():
    if request.method == 'POST':
        print("request POST args: {}".format(request.form))
    elif request.method == 'GET':
        print("request GET args: {}".format(request.args))
    return Response('isallright', 200)


@app.route('/logout')
def logout():
    user_auth.logout_user()
    return redirect(url_for('index'))


@app.route("/bosh", methods=['GET', 'POST'])
@user_auth.flask_login_required
def bosh_logs():
    if request.method == 'POST':
        form = boshforms.BoshLogsForm(request.form)
        if form.validate_on_submit():
            director.submit_logs_job(form.deployment.data, form.jobs.data)
        else:
            sys.stderr.write("form.errors:{}\n".format(form.errors))
        return render_template('bosh.html',
                               form=boshforms.BoshLogsForm(),
                               deployments=director.deployments,
                               jobs=director.get_deployment_jobs(director.deployments[0]),
                               tasks=director.pending_tasks)
    elif request.method == 'GET':
        return render_template('bosh.html',
                               form=boshforms.BoshLogsForm(),
                               deployments=director.deployments,
                               jobs=director.get_deployment_jobs(director.deployments[0]),
                               tasks=director.pending_tasks)
    return render_template('index.html')


# add jinja template for converting "Epoch" dates to time strings
@app.template_filter('datetime')
def format_datetime(value):
    return time.ctime(value)


@app.route("/bosh/tasks", methods=['GET'])
@user_auth.flask_login_required
def get_tasks():
    limit = request.args.get('limit', default=0, type=int)
    # return Response(director.get_job_history(limit),
    #                 content_type='application/json')
    return render_template('bosh_history.html',
                           tasks=director.get_job_history(limit))


@app.route("/bosh/tasks/<taskid>", methods=['GET'])
@user_auth.flask_login_required
def download_logs(taskid):
    t = None
    for t in director.pending_tasks:
        if "/tasks/{}".format(taskid) == t.t_url:
            break
    if t is None:
        return Response('Could not find task', 404)
    filename = t.t_query.replace('/', '_').replace(' ', '_') + ".tgz"
    # director.pending_tasks.remove(t)
    download_url = director.get_logs_job("/tasks/{}".format(taskid))
    r = director.session.get(director.bosh_url + download_url,
                             verify=director.verify_tls,
                             stream=True)
    return Response(stream_with_context(r.iter_content(chunk_size=512 * 1024)),
                    content_type='application/gzip',
                    headers={'Content-Disposition': "attachment; filename={}".format(filename)})


@app.route("/bosh/tasks/<taskid>/output", methods=['GET'])
@user_auth.flask_login_required
def get_task_output(taskid):
    output_type = request.args.get('type')
    if output_type == '':
        output_type = 'result'
    task_url = '/tasks/{}/output'.format(taskid)
    r = director.session.get(director.bosh_url + task_url,
                             params={'type': output_type},
                             verify=director.verify_tls)
    if r.ok:
        return Response(r.text, content_type='text/plain')
    else:
        return Response("error fetching task {} output".format(
            taskid) + r.text, content_type='text/plain')


@app.route("/bosh/tasks/<taskid>/cancel", methods=['GET'])
@user_auth.flask_login_required
def cancel_task(taskid):
    task_url = '/task/{}'.format(taskid)
    r = director.session.delete(director.bosh_url + task_url)
    if r.ok:
        return Response("{}", status_code=r.status)
    else:
        return Response(r.text, status_code=r.status)


@app.route("/bosh/deployment/vitals", methods=['GET'])
@user_auth.flask_login_required
def get_deployment_vitals_default():
    deployment = request.args.get('deployment')
    if deployment is None:
        deployment = director.deployments[0]
    vitals = director.get_deployment_vitals(deployment)
    return render_template('bosh_vitals.html',
                           deployment_name=deployment,
                           deployments=director.deployments,
                           deployment_vitals=vitals)


@app.route("/bosh/deployment/<deployment>/jobs", methods=['GET'])
@user_auth.flask_login_required
def get_deployment_jobs(deployment):
    return Response(json.dumps(director.get_deployment_jobs(deployment)),
                    content_type='application/json')


@app.route('/vm_control', methods=['GET'])
@user_auth.flask_login_required
def vm_control():   # (deployment, vmi, action):
    deployment = request.args.get('deployment')
    vmi = request.args.get('vmi')
    action = request.args.get('action')
    skip_drain = request.args.get('skip_drain')
    inst_group, inst = vmi.split('/')
    if deployment is None or vmi is None or inst_group is None or inst is None:
        return Response("{'error': 'deployment, vm required (vm as vm/guid or vm/index)'}",
                        status_code=400,
                        content_type='application/json')
    if action not in ['restart', 'recreate', 'stop', 'start']:
        return Response("{'error': 'action is required: restart,recreate,stop,start'}",
                        status_code=400,
                        content_type='application/json')
    if skip_drain is None:
        skip_drain = False
    action_url = '{}/deployments/{}/instance_groups/{}/{}/actions/{}'.format(
        director.bosh_url, deployment, inst_group, inst, action)
    a_r = director.session.post(action_url,
                                params={'skip_drain': skip_drain},
                                verify=director.verify_tls)
    if director.debug:
        print("URL {} returns {}".format(action_url, a_r.text))
    if a_r.ok:
        return Response(status=a_r.status_code,
                        content_type='application/json',
                        response=a_r.json())
    else:
        error_msg = {'error': a_r.text}
        return Response(error_msg,
                        status=a_r.status_code,
                        content_type='application/json')


director = director.Director(config.get('o_director_url'),
                             config.get('o_bosh_user'),
                             config.get('o_bosh_pass'),
                             debug=config.get('o_debug'),
                             verify_tls=config.get('o_verify_tls'))
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
