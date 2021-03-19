
from flask_wtf import FlaskForm
import wtforms


class BoshLogsForm(FlaskForm):
    deployment = wtforms.StringField('deployment',
                                     validators=[wtforms.validators.DataRequired()])
    jobs = wtforms.StringField('jobs',
                               validators=[wtforms.validators.DataRequired()])
