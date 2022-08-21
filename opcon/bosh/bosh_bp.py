import sys
import json
from opcon.modules import boshforms
from opcon.modules import accesslog
import flask_login
from flask import current_app, request, jsonify
from flask import Response, stream_with_context
from flask import Blueprint, render_template


bosh_bp = Blueprint('bosh_bp',  __name__,
                    template_folder='templates',
                    static_folder='static', static_url_path='assets')


@bosh_bp.route('/', methods=['GET', 'POST'])
@flask_login.login_required
@accesslog.log_access
def bosh_logs():
    director = current_app.config['DIRECTOR']
    if len(director.deployments) == 0:
        return render_template('index.html', director=director)
    form = boshforms.BoshLogsForm(request.form)
    if request.method == 'POST':
        if form.validate_on_submit():
            director.submit_logs_job(form.deployment.data, form.jobs.data)
        else:
            print('form.errors:{}'.format(form.errors), file=sys.stderr)
    deployment = form.deployment.data
    if deployment == '' or deployment is None:
        deployment = director.deployments[0]
    best_response = request.accept_mimetypes.best_match(["application/json",
                                                         "text/html"])
    if best_response == 'text/html':
        return render_template('bosh.html',
                               form=boshforms.BoshLogsForm(),
                               deployment_name=deployment,
                               deployments=director.deployments,
                               jobs=director.get_deployment_jobs(deployment),
                               tasks=director.pending_tasks)
    return jsonify(director.pending_tasks)


@bosh_bp.route('/tasks', methods=['GET'])
@flask_login.login_required
@accesslog.log_access
def get_tasks():
    director = current_app.config['DIRECTOR']
    limit = request.args.get('limit', default=100, type=int)
    # return Response(director.get_job_history(limit),
    #                 content_type='application/json')
    return render_template('bosh_history.html',
                           tasks=director.get_job_history(limit))


@bosh_bp.route('/tasks/<taskid>', methods=['GET'])
@flask_login.login_required
@accesslog.log_access
def download_logs(taskid):
    director = current_app.config['DIRECTOR']
    t = None
    for task in director.pending_tasks:
        if "/tasks/{}".format(taskid) == task.t_url:
            t = task
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


@bosh_bp.route('/tasks/<taskid>/output', methods=['GET'])
@flask_login.login_required
@accesslog.log_access
def get_task_output(taskid):
    director = current_app.config['DIRECTOR']
    output_type = request.args.get('type')
    if output_type == '':
        output_type = 'result'
    task_url = '/tasks/{}/output'.format(taskid)
    r = director.session.get(director.bosh_url + task_url,
                             params={'type': output_type},
                             verify=director.verify_tls)
    if r.ok:
        return Response(stream_with_context(r.iter_content(chunk_size=512 * 1024)),
                        content_type='text/plain')
    else:
        return Response("error fetching task {} output".format(
            taskid) + r.text, content_type='text/plain')


@bosh_bp.route('/tasks/<taskid>/cancel', methods=['GET'])
@flask_login.login_required
@accesslog.log_access
def cancel_task(taskid):
    director = current_app.config['DIRECTOR']
    task_url = '/task/{}'.format(taskid)
    if director.readonly:
        return Response(status=403, content_type='application/json',
                        response=json.dumps({'error': 'administratively denied'}))
    r = director.session.delete(director.bosh_url + task_url)
    if r.ok:
        return Response(status=r.status_code,
                        response=r.text,
                        content_type='text/plain')
    else:
        return Response(status=r.status_code,
                        response=r.content,
                        content_type='text/plain')


@bosh_bp.route('/deployment/errands', methods=['GET'])
@flask_login.login_required
@accesslog.log_access
def get_deployment_errands():
    director = current_app.config['DIRECTOR']
    deployment = request.args.get('deployment')
    if len(director.deployments) == 0:
        return render_template('index.html', director=director)
    if deployment is None:
        deployment = director.deployments[0]
    errands = director.get_deployment_errands(deployment)
    return render_template('bosh_errands.html',
                           deployment_name=deployment,
                           deployments=director.deployments,
                           deployment_errands=errands)


@bosh_bp.route('/deployment/<deployment>/errand/<errand>/run')
@flask_login.login_required
@accesslog.log_access
def run_deployment_errand(deployment, errand):
    director = current_app.config['DIRECTOR']
    running, link = director.run_deployment_errand(deployment, errand)
    if running:
        rcode = 200
    else:
        rcode = 400
    return Response("{'running': '%s'}" % (running), status=rcode)


@bosh_bp.route('/deployment/vitals', methods=['GET'])
@flask_login.login_required
@accesslog.log_access
def get_deployment_vitals_default():
    director = current_app.config['DIRECTOR']
    deployment = request.args.get('deployment')
    if len(director.deployments) == 0:
        return render_template('index.html', director=director)
    if deployment is None:
        deployment = director.deployments[0]
    vitals = director.get_deployment_vitals(deployment)
    # sort by job_name/id
    sorted_vitals = sorted(vitals, key=lambda d: d['job_name'] + "/" + d['id'])
    return render_template('bosh_vitals.html',
                           deployment_name=deployment,
                           deployments=director.deployments,
                           readonly=director.readonly,
                           deployment_vitals=sorted_vitals)


@bosh_bp.route('/deployment/<deployment>/jobs', methods=['GET'])
@flask_login.login_required
@accesslog.log_access
def get_deployment_jobs(deployment):
    director = current_app.config['DIRECTOR']
    return Response(json.dumps(director.get_deployment_jobs(deployment)),
                    content_type='application/json')


@bosh_bp.route('/vm_control', methods=['GET'])
@flask_login.login_required
@accesslog.log_access
def vm_control():
    director = current_app.config['DIRECTOR']
    deployment = request.args.get('deployment')
    vmi = request.args.get('vmi')
    action = request.args.get('action')
    skip_drain = request.args.get('skip_drain', default=False)
    inst_group, inst = vmi.split('/')
    if director.readonly:
        return Response(status=403, content_type='application/json',
                        response={'error': 'administratively denied'})
    if deployment is None or vmi is None or inst_group is None or inst is None:
        return Response("{'error': 'deployment, vm required (vm as vm/guid or vm/index)'}",
                        status=400,
                        content_type='application/json')
    if action not in ['restart', 'recreate', 'stop', 'start']:
        return Response("{'error': 'action is required: restart,recreate,stop,start'}",
                        status=400,
                        content_type='application/json')
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
                        response=json.dumps(a_r.json()))
    else:
        error_msg = {'error': a_r.text}
        return Response(error_msg,
                        status=a_r.status_code,
                        content_type='application/json')
