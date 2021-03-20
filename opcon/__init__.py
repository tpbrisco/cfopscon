
# for gunicorn
from . import app


def application():
    app.run()


if __name__ == '__main__':
    app.run(debug=True)
