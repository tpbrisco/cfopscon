# cfopscon
The Cloud Foundry Operator's Console

The CF Operator's Console is intended to reduce toil for many common
cloud operator tasks (e.g. obtaining and downloading logs).  It
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
Currently a single "bosh logs" is possible, however work is in
progress to see the BOSH director task backlog.  Addtiional "to do"
items include database health checks, VM status information, and so
forth.

## Deployment
At the moment, it''s currently a simple Flask application that can be
ran from the desktop (assuming access to the BOSH director is
possible), however it does run under gunicorn to support the cf-push
model of deployment.  For the moment, a simple
```bash
% FLASK_APP='opcon.app:app' flask run
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
  Should support "fake_auth" (local CSV?), UAA auth, and maybe
  3rd-party OAuth2 endpoints.
- Implement auto-fill for BOSH deployment jobs;
  Presumably jQuery, and use the /deployments/:deployment/instances API
- Investigate and support bosh-cli-like syntax "bosh logs compute" for
  logs from all "compute" jobs.
- "flash" updates on the status of things in wait;  E.g. waiting on a
  job to complete for logs download - put a status update.
