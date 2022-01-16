import sys
import json
from opcon.modules import accesslog
import flask_login
from flask import current_app, request
from flask import Response, stream_with_context
from flask import Blueprint, render_template

api_bp = Blueprint('api_bp', __name__,
                   template_folder='templates',
                   static_folder='static', static_url_path='assets')


# v1/ -- return usage
@api_bp.route('/v1', methods=['GET', 'POST'])
# @flask_login.login_required
# @accesslog.log_access
def v1_usage():
    return Response(
        json.dumps({"status": "ok", "message": "usage"}),
        status=200,
        mimetype='application/json')


# v1/tasks - return list of previous tasks
@api_bp.route('/v1/tasks')
def v1_tasks():
    director = current_app.config['DIRECTOR']
    limit = request.args.get('limit', default=100, type=int)
    return Response(
        json.dumps({"status": "ok", "limit": limit, "results": director.get_job_history(limit)}),
        status=200, mimetype='application/json')


# v1/tasks/<taskid>/<action>
# Perform result/debug/event/cancel on the task
@api_bp.route('/v1/tasks/<taskid>/<out_type>')
def v1_tasks_id_action(taskid, out_type):
    director = current_app.config['DIRECTOR']
    if out_type not in ["result", "debug", "event", "cancel"]:
        return Response(
            json.dumps({"status": "error", "message": "result, debug, event, cancel"}),
            status=404)
    task_url = '/tasks/{}/output'.format(taskid)
    r = director.session.get(director.bosh_url + task_url,
                             params={'type': out_type},
                             verify=director.verify_tls)
    if r.ok:
        return Response(stream_with_context(r.iter_content(chunk_size=512*1024)),
                        content_type='text/plain', status=r.status_code)
    return Response(
        json.dumps({"status": "error", "message": r.content}),
        status=r.status_code)


# v1/blobstore/<guid> - return arbitrary blobstore file
# Primarily, this is to allow errand output to be gathered.  There's
# not an easy way of doing this - an errand starts a task which
# returns a *series* of JSON blobs (not an array) - one for each
# job/vm instance.  Each JSON blob contains the blobstore cache name
# for the output gathered by the errand for that job/vm.
#
# This is _not_ the same as a "bosh logs", which is neatly gathered up
# by the task into a single blobstore file - see
# director.get_logs_job() and the output of an errand.
@api_bp.route('v1/blobstore/<bs_guid>')
def v1_blobstore_guid(bs_guid):
    director = current_app.config['DIRECTOR']
    r = director.session.get(director.bosh_url + "/resources/{}".format(bs_guid))
    return Response(stream_with_context(r.iter_content(chunk_size=512 * 1024)),
                    content_type='application/gzip',
                    headers={'Content-Disposition': "attachment; filename={}.tgz".format(bs_guid)})


# v1/deployments - return list of deployments
@api_bp.route('/v1/deployments')
def v1_deployments():
    director = current_app.config['DIRECTOR']
    return Response(json.dumps({"status": "ok", "data": director.deployments}))


# v1/deployment/<deployment>/jobs -- return list of jobs under deployment
@api_bp.route('/v1/deployment/<deployment>/jobs')
def v1_deployment_jobs(deployment):
    director = current_app.config['DIRECTOR']
    return Response(json.dumps(director.get_deployment_jobs(deployment)),
                    content_type='application/json')


# v1/deployment/<deployment>/job/<job>/<instance>/<action>
@api_bp.route('/v1/deployment/<deployment>/job/<job>/<instance>/<action>')
def v1_deployment_job_actions(deployment, job, instance, action):
    director = current_app.config['DIRECTOR']
    if action not in ["restart", "stop", "start", "recreate"]:
        return Response(
            json.dumps({"status": "error", "message": "action from restart, stop, start, recreate"}),
            status=404)
    skip_drain = request.args.get('skip_drain', default=False)
    action_url = '{}/deployments/{}/instance_groups/{}/{}/actions/{}'.format(
        director.bosh_url, deployment, job, instance, action)
    r = director.session.post(action_url,
                              params={'skip_drain': skip_drain},
                              verify=director.verify_tls)
    if r.ok:
        return Response(status=r.status_code,
                        content_type='application/json',
                        response=json.dumps(r.json()))
    else:
        error = {'status': 'error', 'message': r.content}
        return Response(response=json.dumps(error),
                        status=r.status_code,
                        content_type='application/json')


# v1/logs - return list of logs from previous "bosh logs" statements
@api_bp.route('/v1/logs', methods=['GET'])
def v1_list_task_logs():
    director = current_app.config['DIRECTOR']
    message_d = {
        'status': 'ok',
        'data': list()
    }
    for pt in director.pending_tasks:
        message_d['data'].append(pt.__dict__)
    return Response(json.dumps(message_d))


# v1/logs/<taskid> - stream the logs for this task
@api_bp.route('/v1/logs/<taskid>', methods=['GET'])
def v1_stream_task_log(taskid):
    director = current_app.config['DIRECTOR']
    download_url = director.get_logs_job("/tasks/{}".format(taskid))
    r = director.session.get(director.bosh_url + download_url,
                             verify=director.verify_tls,
                             stream=True)
    return Response(stream_with_context(r.iter_content(chunk_size=512 * 1024)),
                    content_type='application/gzip')


# v1/logs/<deployment>/<job>/<instance> - run "bosh -d depl logs jobs/instance"
# note that this form gets logfiles from a specific job instance.
# This submits a task to fetch those jobs
@api_bp.route('/v1/logs/<deployment>/<job>/<instance>', methods=['GET'])
def v1_submit_logs_job(deployment, job, instance):
    director = current_app.config['DIRECTOR']
    if director.submit_logs_job(deployment, "{}/{}".format(job, instance)):
        return Response(json.dumps({"status": "ok", "message": "submitted"}))
    else:
        return Response(json.dumps({"status": "error"}), status=404)


# v1/deployment/<deployment>/errands
# Return available errands for deployment <deployment>
@api_bp.route('/v1/deployment/<deployment>/errands')
def v1_deployment_errands(deployment):
    director = current_app.config['DIRECTOR']
    errands = director.get_deployment_errands(deployment)
    return Response(json.dumps(errands), mimetype='application/json')


# v1/deployment/<deployment>/errand/<errand>/run
# Start the errand running
@api_bp.route('/v1/deployment/<deployment>/errand/<errand>/run')
def v1_deployment_errands_run(deployment, errand):
    director = current_app.config['DIRECTOR']
    running, link = director.run_deployment_errand(deployment, errand)
    if running:
        rcode = 200
        status = 'ok'
    else:
        rcode = 400
        status = 'permission denied'
    return Response(json.dumps({"status": status, "link": link}), status=rcode)

