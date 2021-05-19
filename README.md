# cfopscon
The Cloud Foundry Operator's Console
![image of console](assets/console.png)

The CF Operator's Console is intended to reduce toil for many common
cloud foundry operator tasks (e.g. obtaining and downloading logs).  It
operates as a cloud foundry application, but has some specific
requirements outlined below (in order to obtain appropriate access).

This repository contains the source code for the Operator's Console;
it is intended to be implemented via "cf push" on the targetted
foundation.  It provides links to common areas - BOSH is the first of
these.

The Operators Console leverages the APIs of BOSH and CF API to achieve
it's goals; as such, it must contain privileged information (see opcon.ini)
(e.g. username/password) to bootstrap OAuth2 credentials necessary to
access the appropriate APIs.

## Current Status
Common BOSH operations are supported
* retrieving logs from VMs ("bosh logs")
* VM "vitals" ("bosh vms --vitals") with restart/stop/start/recreate operations, 
* Task results and controls - task cancelling, and results/debug/events logs

Whle current bosh-centric, plans include extending the model for
common cloud foundry operational tasks.  See "TO DO' for planned work.

## Deployment
The _CF Operator's Console_ is a Flask application that can be ran
from the desktop via Flask commands (assuming BOSH director access), 
as well as under gunicorn to support the cf-push model of deployment.

To run from the desktop:
 ```bash
% OAUTHLIB_INSECURE_TRANSPORT=1 FLASK_APP='opcon.app:app' flask run
```
should result in a running system, accessible from localhost:5000.

Or, for more production use-cases
```bash
% gunicorn -c gunicorn.py 'opcon.app:app'
```

Or, for cloud foundry foundations
```bash
% cf push -f manifestlyml
```

## TO DO
- Implement authentication for access to the system; 
  Should support "fake_auth" (~~local CSV?~~), ~~UAA auth~~, and maybe
  3rd-party OAuth2 endpoints.
- user activity tracking - log who-did-what
- ~~cancel tasks~~
- home page statistics -- include "interesting" stats about BOSH, CF
- Investigate and support bosh-cli-like syntax "bosh logs compute" for
  logs from all "compute" jobs.
- "flash" updates on the status of things in wait;  E.g. waiting on a
  job to complete for logs download - put a status update.
  Presumably jQuery, and use the /deployments/:deployment/instances API~~
- restart CF brokers
- ~~recreate specific VMs~~
- ~~show VM health state (bosh vms --vitals)~~
- ~~Implement auto-fill for BOSH deployment jobs~~
