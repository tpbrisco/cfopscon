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
(i.e. username/password) to bootstrap OAuth2 credentials necessary to
access the appropriate APIs.

## Current Status
Common BOSH operations are supported
* retrieving logs from VMs ("bosh logs")
* VM "vitals" ("bosh vms --vitals") with restart/stop/start/recreate operations,
* Task results and controls - task cancelling, and results/debug/events logs
* Run deployment errands

While currently bosh-centric, plans include extending the model for
common cloud foundry operational tasks.  See "TO DO' for planned work.

## Deployment
The _CF Operator's Console_ is a Flask application that can be ran
from the desktop via Flask commands (assuming BOSH director access),
as well as under gunicorn to support the cf-push model of deployment.

To run from the desktop:
 ```bash
% CONFIG_FILE=opcon.ini OAUTHLIB_INSECURE_TRANSPORT=1 FLASK_APP='opcon.app:app' flask run
```
should result in a running system, accessible from localhost:5000.

Or, for more production use-cases
```bash
% gunicorn -c gunicorn.py 'opcon.app:app'
```

Or, for cloud foundry foundations
```bash
% cf push -f manifest.yml
```

## Options
Options and configuration are contained in the "opcon.ini" file (or
file specified by the CONFIG_FILE environment variable).  It is broken
into 4 sections - "bosh", "auth", "audit" and deployment errand ACLs.

Options are specified below, with any default value indicated first.
### bosh options
- director\_url=_https:/10.100.10.10:25555_ - - the full URL for the bosh director
- verify_tls=[False, True] -- disable/enable TLS validation (meant for debugging)
- user=[_admin_, $BOSH_USERNAME] -- username for the BOSH login
- pass=[_magic_, $BOSH_PASSWORD] -- password for the BOSH login
- debug=[False, True] -- disable/enable debugging for the director code
- readonly=[False, True] -- disable certain BOSH operations

The _readonly_ flag disables start/stop/recreate operations on BOSH
VMs.  Note that this does not disable errands (see below).

### auth options
  - type=MOD -- required, indicates loadable module
  - module=_module.py_ - module located in modules/ area
  - data=_mod\_specific_ - module-specific comma-seperated list
  - brand=_string_ - branding name for redirect pages
  - debug=_False_ - module-specific debugging

### audit
- enable=["False", "True"]
- data=app_name,log_type,username,password,url
- extra_fields=<json dict>

"App_name" is how the application will identify itself, the log type
may be "audit" or something similar, the audit logging assumes basic
auth (username, password) or no authentication to the indicated URL
which will be used for POST operations.

The data logged is a JSON object indicating person logged in
(username), the IP address from which they are connecting (origin),
the time that the request was received (receive_time), and the URL
(path), HTTP operation (http_method), and parameters (query).  The
application name and log class (from the parameters) are included as
well.  This object is merged with the dict from 'extra_fields' if it is provided.

### errands\__deployment-prefix_ options
- allow=["regexp", "regexp"]

Sections named "errands\_deployment-prefix" contain an "allow" ACL of errands
that can be run for the matching deployment.  If a deployment name
starts with "deployment-prefix", then the list of errand regular expressions
will be applied as an ACL indicating which errands can be run.  If there is
no section for a deployment and no entry for "\*" exists, the default is to allow all errands.

The _deployment-prefix_ can be "errands_\*" to match any deployments
without a specific configuration (that is; it matches any deployment
not otherwise specified).
The _allow=_ configuration may be missing, indicating that nothing is
allowed.

Avoid surprises when allowing "status", when what you really mean is
"^status$".

A good way to allow "status.\*" errands for zookeeper, and no other
errands would be:
```
[errand_zookeep]
allow=["status.*"]
[errand_*]
```


## Limitations
- running multiple instances of the process doesn't work as expected
>  The user database is an in-RAM database, so of course moving across
>  CF instances doesn't work.  An alternatives involve external K/V
>  stores, and it's not clear if usage will be such that that is worth
>  the work.

## Tests
cfopscon uses the nose2 for unittest running.  From the top-level
directory
```bash
% nose2 --with-coverage --coverage=opcon -v tests
% coverage html
```
should yield predictable results.

## TO DO
- add the "force" flag to the VM recreate in bosh_vitals
- improve bosh tasks/errands output collection - auto-refresh events/debug output?
- allow errand flags (e.g. specify the instance)
- remove passwords from INI file
- Investigate and support bosh-cli-like syntax "bosh logs compute" for
  logs from all "compute" jobs.
- "flash" updates on the status of things in wait;  E.g. waiting on a
  job to complete for logs download - put a status update.
  Presumably jQuery, and use the /deployments/:deployment/instances API~~
- restart CF brokers
