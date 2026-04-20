from flask import Blueprint

# We give it a unique name 'module4_audit' to avoid the error you saw in the terminal
module4 = Blueprint('module4_audit', __name__)

from . import routes