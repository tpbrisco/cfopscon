
import configparser
from optparse import OptionParser
from opcon.modules import director
from opcon.modules import boshforms
from flask import Flask, render_template, request, Response, stream_with_context
from flask_apscheduler import APScheduler
from flask_bootstrap import Bootstrap
import uuid

# set up primary objects
app = Flask(__name__)
Bootstrap(app)
app.config['JSON_AS_ASCII'] = True
app.config['SECRET_KEY'] = uuid.uuid4().hex
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


@app.route("/index.html")
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/bosh", methods=['GET', 'POST'])
def bosh_logs():
    if request.method == 'POST':
        form = boshforms.BoshLogsForm(request.form)
        if form.validate_on_submit():
            director.submit_logs_job(form.deployment.data, form.jobs.data)
        return render_template('bosh.html',
                               form=boshforms.BoshLogsForm(),
                               deployments=director.deployments,
                               tasks=director.pending_tasks)
    elif request.method == 'GET':
        return render_template('bosh.html',
                               form=boshforms.BoshLogsForm(),
                               deployments=director.deployments,
                               tasks=director.pending_tasks)
    return render_template('index.html')


@app.route("/bosh/tasks/<taskid>", methods=['GET'])
def download_logs(taskid):
    for t in director.pending_tasks:
        if "/tasks/{}".format(taskid) == t.t_url:
            break
    if t is None:
        return Response('Could not find task', 404)
    filename = t.t_query.replace('/', '_').replace(' ', '_') + ".tgz"
    del t  # remove it from the pending jobs
    download_url = director.get_logs_job("/tasks/{}".format(taskid))
    r = director.session.get(director.bosh_url + download_url,
                             verify=director.verify_tls,
                             stream=True)
    return Response(stream_with_context(r.iter_content(chunk_size=512 * 1024)),
                    content_type='application/gzip',
                    headers={'Content-Disposition': "attachment; filename={}".format(filename)})


@app.route("/bosh/deployment/<deployment>/jobs", methods=['GET'])
def get_deployment_jobs(deployment):
    return Response(director.get_deployment_jobs(deployment),
                    content_type='application/json')


# main configuration dictionary
config = dict()

# parse base configuration file
configini = configparser.ConfigParser()
configini.read('opcon.ini')
if 'global' in configini:
    g = configini['global']
    config['o_debug'] = g.getboolean('debug', fallback=False)
    config['o_director_url'] = g.get('director_url')
    config['o_verify_tls'] = g.getboolean('verify_tls', fallback=True)
    config['o_bosh_user'] = g.get('user')
    config['o_bosh_pass'] = g.get('pass')


# cli options override ini file
parser = OptionParser()
parser.add_option('-d', '--debug', dest='debug',
                  default=config['o_debug'], action='store_true',
                  help='enable debugging mode')
parser.add_option('-b', '--bosh-url', dest='bosh_url', default='',
                  help='indicate https://<ip>:<port> for bosh director')
parser.add_option('--skip-tls-verification', dest='verify_tls',
                  default=config['o_verify_tls'], action='store_false',
                  help='skip TLS/SSL certificate validation')
parser.add_option('-u', '--user', dest='bosh_user', default='',
                  help='bosh username')
parser.add_option('-p', '--pass', '--password', dest='bosh_pass', default='',
                  help='bosh password')
(options, args) = parser.parse_args()

config['o_debug'] = options.debug
config['o_verify_tls'] = options.verify_tls
if options.bosh_url:
    config['o_director_url'] = options.bosh_url
if options.bosh_user:
    config['o_bosh_user'] = options.bosh_user
if options.bosh_pass:
    config['o_bosh_pass'] = options.bosh_pass

if config['o_debug']:
    print("Configuration:")
for k in config:
    print(f'\t{k}: {config[k]}')

director = director.Director(config['o_director_url'],
                             config['o_bosh_user'], config['o_bosh_pass'],
                             debug=config['o_debug'],
                             verify_tls=config['o_verify_tls'])
print("scheduled oauth update in %d seconds" % (
    director.oauth_token_expires() - 30))
scheduler.add_job(id='oauth-refresh',
                  func=director.refresh_token,
                  trigger='interval',
                  seconds=director.oauth_token_expires() - 30)

if __name__ == '__main__':
    app.run(debug=True)
