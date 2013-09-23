# vim: set fileencoding=utf-8 :
from __future__ import division, print_function, unicode_literals
from subprocess import Popen, PIPE
from collections import namedtuple
import sys
import os
import subprocess
import json
import time


Script = namedtuple('Script', ['name', 'file'])


class Roac(object):
    """The Roac object implements the execution of scripts in a timed loop,
    reading said scripts and executing callbacks when necessary. It manages
    the life cycle of a Roäc application
    """

    default_config = {
        'script_dir': 'scripts',
        'interval': 30
    }

    def __init__(self, **kwargs):
        self.config = self.default_config
        self.config.update(kwargs)
        self.script_handlers = []

    def find_scripts(self):
        """Lists all :class:`Script`s to be executed each step. Their file
        attribute needs to be especified as a correct path, either absolute,
        or relative to the current working directory. Implemented as a
        generator function.
        """

        for root, dirs, files in os.walk(self.config['script_dir']):
            for name in files:
                yield Script(name=name, file=os.path.join(root, name))

    def execute_scripts(self):
        """Runs and reads the result of scripts. """

        for script in self.find_scripts():
            try:
                # Run script
                print('Executing {}'.format(script.name))
                process = Popen(script.file, stdout=PIPE)
                # regression: python2's subprocess doesn't support timeout
                # deal with it manually later.
                # see http://stackoverflow.com/questions/1191374
                out, errs = process.communicate()
                out = out.decode()
                print(out)
                data = json.loads(out)
            except (OSError, ValueError) as e:
                print('\terror: {}'.format(e))
            else:
                #Call functions binded to this script
                self.last_output[script.name] = data

    def script_handler(self, script_name):
        """A decorator that is used to register a view function for a given
        script::

            @app.script_handler('users.sh')
            def handle_users(output):
                print('output')

        :param script_name: the name of the script that triggers the call.
        """
        def decorator(f):
            self.script_handlers.append(
                (script_name, f))
            return f
        return decorator

    def run(self):
        """Runs the application's main loop, responsible for executing and
        listening to the scripts
        """
        from .timer import RepeatingTimer
        timer = RepeatingTimer(self.config['interval'])
        timer.register(self.step)
        timer.run()

    def handle_scripts(self):
        """Calls the handler callbacks for each entry in last_output.
        """
        for script_name, data in self.last_output.iteritems():
            functions = [
                h[1] for h in self.script_handlers if h[0] == script_name]
            for f in functions:
                try:
                    f(output=data)
                except Exception as e:
                    print('\t error at function: {}'.format(e))


    def step(self):
        """Controls what happens in a iteration.. If the application using
        this library implements its own main loop, you can either run this
        method periodically, or use :method:`run` in its own thread/process.
        """

        self.last_output = {}
        self.execute_scripts()
        self.handle_scripts()