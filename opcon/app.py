
import configparser
from opcon.modules import director
from opcon.modules import boshforms
from opcon.modules import auth
from opcon.modules import config
from flask import Flask, render_template, request, Response, stream_with_context, redirect, session, flash
from flask_apscheduler import APScheduler
from flask_bootstrap import Bootstrap
import uuid
import os
import time
import json

# see "is_gunicorn" comments below for confusion with gunicorn
is_gunicorn = "gunicorn" in os.getenv('SERVER_SOFTWARE', '')
if not is_gunicorn:
    from optparse import OptionParser

# set up primary objects
app = Flask(__name__)
Bootstrap(app)
app.config['JSON_AS_ASCII'] = True
app.config['SECRET_KEY'] = uuid.uuid4().hex
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
app.config['USER_AUTH_TYPE'] = 'CSV'
app.config['USER_AUTH'] = auth.user_authentication(app)
user_auth = auth.user_authentication(app)
user_auth.ua_login_manager.init_app(app)
user_auth.ua_login_manager.login_view = 'login'


@app.route("/index.html")
@app.route("/")
@user_auth.flask_login_required
def index():
    return render_template("index.html", director=director)


@user_auth.ua_login_manager.user_loader
def load_user(id):
    return user_auth.user_loader(id)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if user_auth.flask_current_user.is_authenticated:
        return redirect('/index.html')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_auth.login_user(username, password)
        return redirect('/index.html')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session['logged_in'] = False
    user_auth.logout_user()
    return redirect('/index.html')


@app.route("/bosh", methods=['GET', 'POST'])
@user_auth.flask_login_required
def bosh_logs():
    if request.method == 'POST':
        form = boshforms.BoshLogsForm(request.form)
        if form.validate_on_submit():
            director.submit_logs_job(form.deployment.data, form.jobs.data)
        else:
            print("form.errors:", form.errors)
        return render_template('bosh.html',
                               form=boshforms.BoshLogsForm(),
                               deployments=director.deployments,
                               jobs=json.loads(director.get_deployment_jobs(director.deployments[0])),
                               tasks=director.pending_tasks)
    elif request.method == 'GET':
        return render_template('bosh.html',
                               form=boshforms.BoshLogsForm(),
                               deployments=director.deployments,
                               jobs=json.loads(director.get_deployment_jobs(director.deployments[0])),
                               tasks=director.pending_tasks)
    return render_template('index.html')


@app.template_filter('datetime')
def format_datetime(value):
    return time.ctime(value)


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


@app.route("/bosh/deployment/<deployment>/jobs", methods=['GET'])
@user_auth.flask_login_required
def get_deployment_jobs(deployment):
    return Response(director.get_deployment_jobs(deployment),
                    content_type='application/json')


@app.route("/bosh/tasks", methods=['GET'])
@user_auth.flask_login_required
def get_tasks():
    limit = request.args.get('limit', default=0, type=int)
    # return Response(director.get_job_history(limit),
    #                 content_type='application/json')
    return render_template('bosh_history.html',
                           tasks=director.get_job_history(limit))


# main configuration dictionary
config = config.config(command_line=not is_gunicorn, config_file='opcon.ini')

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

if __name__ == '__main__':
    app.run(debug=config['o_debug'])
