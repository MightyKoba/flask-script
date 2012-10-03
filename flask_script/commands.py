# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import with_statement

import os
import code
import warnings

import argparse

from flask import _request_ctx_stack

from .cli import prompt, prompt_bool, prompt_pass, prompt_choices


class InvalidCommand(Exception):
    pass


class Option(object):
    """
    Stores positional and optional arguments for `ArgumentParser.add_argument
    <http://argparse.googlecode.com/svn/trunk/doc/add_argument.html>`_.

    :param name_or_flags: Either a name or a list of option strings,
                          e.g. foo or -f, --foo
    :param action: The basic type of action to be taken when this argument
                   is encountered at the command-line.
    :param nargs: The number of command-line arguments that should be consumed.
    :param const: A constant value required by some action and nargs selections.
    :param default: The value produced if the argument is absent from
                    the command-line.
    :param type: The type to which the command-line arg should be converted.
    :param choices: A container of the allowable values for the argument.
    :param required: Whether or not the command-line option may be omitted
                     (optionals only).
    :param help: A brief description of what the argument does.
    :param metavar: A name for the argument in usage messages.
    :param dest: The name of the attribute to be added to the object
                 returned by parse_args().
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Command(object):
    """
    Base class for creating commands.
    """

    option_list = []

    @property
    def description(self):
        description = self.__doc__ or ''
        return description.strip()

    def add_option(self, option):
        """
        Adds Option to option list.
        """
        self.option_list.append(option)

    def get_options(self):
        """
        By default, returns self.option_list.Override if you
        need to do instance-specific configuration.
        """
        return self.option_list

    def create_parser(self, prog):
        parser = argparse.ArgumentParser(prog=prog,
                                         description=self.description)

        for option in self.get_options():
            parser.add_argument(*option.args, **option.kwargs)

        return parser

    def handle(self, app, *args, **kwargs):
        """
        Handles the command with given app. Default behaviour is to call within
        a test request context.
        """
        with app.test_request_context():
            return self.run(*args, **kwargs)

    def run(self):
        """
        Runs a command. This must be implemented by the subclass. Should take
        arguments as configured by the Command options.
        """
        raise NotImplementedError

    def prompt(self, name, default=None):
        warnings.warn_explicit(
            "Command.prompt is deprecated, use prompt() function instead")

        prompt(name, default)

    def prompt_pass(self, name, default=None):
        warnings.warn_explicit(
            "Command.prompt_pass is deprecated, use prompt_pass() function "
            "instead")

        prompt_pass(name, default)

    def prompt_bool(self, name, default=False):
        warnings.warn_explicit(
            "Command.prompt_bool is deprecated, use prompt_bool() function "
            "instead")

        prompt_bool(name, default)

    def prompt_choices(self, name, choices, default=None):
        warnings.warn_explicit(
            "Command.choices is deprecated, use prompt_choices() function "
            "instead")

        prompt_choices(name, choices, default)


class Shell(Command):
    """
    Runs a Python shell inside Flask application context.

    :param banner: banner appearing at top of shell when started
    :param make_context: a callable returning a dict of variables
                         used in the shell namespace. By default
                         returns a dict consisting of just the app.
    :param use_bpython: use BPython shell if available, ignore if not.
                        The BPython shell can be turned on in command
                        line by passing the **--bpython** flag.
    :param use_ipython: use IPython shell if available, ignore if not.
                        The IPython shell can be turned off in command
                        line by passing the **--no-ipython** flag.
    """

    banner = ''

    description = 'Runs a Python shell inside Flask application context.'

    def __init__(self, banner=None, make_context=None, use_ipython=True,
                use_bpython=False):

        self.banner = banner or self.banner
        self.use_ipython = use_ipython
        self.use_bpython = use_bpython

        if make_context is None:
            make_context = lambda: dict(app=_request_ctx_stack.top.app)

        self.make_context = make_context

    def get_options(self):
        return (
            Option('--no-ipython',
                action="store_true",
                dest='no_ipython',
                default=not(self.use_ipython)),
            Option('--bpython',
                action="store_true",
                dest='bpython',
                default=not(self.use_bpython))
        )

    def get_context(self):
        """
        Returns a dict of context variables added to the shell namespace.
        """
        return self.make_context()

    def run(self, no_ipython, bpython):
        """
        Runs the shell.  If bpython is True or use_bpython is True, then
        a BPython shell is run (if installed).  If no_ipython is False or
        use_python is True then a IPython shell is run (if installed).
        """

        context = self.get_context()
        if bpython:
            try:
                from bpython import embed
                embed(banner=self.banner, locals_=self.get_context())
            except ImportError:
                pass
        elif not no_ipython:
            try:
                import IPython
                try:
                    sh = IPython.Shell.IPShellEmbed(banner=self.banner)
                except AttributeError:
                    sh = IPython.frontend.terminal.embed.InteractiveShellEmbed(banner1=self.banner)
                sh(global_ns=dict(), local_ns=context)
                return
            except ImportError:
                pass

        code.interact(self.banner, local=context)


class Server(Command):
    """
    Runs the Flask development server i.e. app.run()

    :param host: server host
    :param port: server port
    :param use_debugger: if False, will no longer use Werkzeug debugger.
                         This can be overriden in the command line
                         by passing the **-d** flag.
    :param use_reloader: if False, will no longer use auto-reloader.
                         This can be overriden in the command line by
                         passing the **-r** flag.
    :param threaded: should the process handle each request in a separate
                     thread?
    :param processes: number of processes to spawn
    :param passthrough_errors: disable the error catching. This means that the server will die on errors but it can be useful to hook debuggers in (pdb etc.)
    :param options: :func:`werkzeug.run_simple` options.
    """

    description = 'Runs the Flask development server i.e. app.run()'

    def __init__(self, host='127.0.0.1', port=5000, use_debugger=True,
                 use_reloader=True, threaded=False, processes=1,
                 passthrough_errors=False, **options):

        self.port = port
        self.host = host
        self.use_debugger = use_debugger
        self.use_reloader = use_reloader
        self.server_options = options
        self.threaded = threaded
        self.processes = processes
        self.passthrough_errors = passthrough_errors

    def get_options(self):

        options = (
            Option('-t', '--host',
                   dest='host',
                   default=self.host),

            Option('-p', '--port',
                   dest='port',
                   type=int,
                   default=self.port),

            Option('--threaded',
                   dest='threaded',
                   action='store_true',
                   default=self.threaded),

            Option('--processes',
                   dest='processes',
                   type=int,
                   default=self.processes),

            Option('--passthrough-errors',
                   action='store_true',
                   dest='passthrough_errors',
                   default=self.passthrough_errors),
        )

        if self.use_debugger:
            options += (Option('-d', '--no-debug',
                               action='store_false',
                               dest='use_debugger',
                               default=self.use_debugger),)

        else:
            options += (Option('-d', '--debug',
                               action='store_true',
                               dest='use_debugger',
                               default=self.use_debugger),)

        if self.use_reloader:
            options += (Option('-r', '--no-reload',
                               action='store_false',
                               dest='use_reloader',
                               default=self.use_reloader),)

        else:
            options += (Option('-r', '--reload',
                               action='store_true',
                               dest='use_reloader',
                               default=self.use_reloader),)

        return options

    def handle(self, app, host, port, use_debugger, use_reloader,
               threaded, processes, passthrough_errors):
        # we don't need to run the server in request context
        # so just run it directly

        app.run(host=host,
                port=port,
                debug=app.config.get('DEBUG', use_debugger),
                use_debugger=use_debugger,
                use_reloader=use_reloader,
                threaded=threaded,
                processes=processes,
                passthrough_errors=passthrough_errors,
                **self.server_options)


class Clean(Command):
    "Remove *.pyc files recursively starting at current directory"
    def run(self):
        for dirpath, dirnames, filenames in os.walk('.'):
            for filename in filenames:
                if '.pyc' in filename:
                    full_pathname = os.path.join(dirpath, filename)
                    print 'Removing %s' % full_pathname
                    os.remove(full_pathname)


class ShowUrls(Command):
    """
        Displays all of the url matching routes for the project.
    """
    def __init__(self, order='rule'):
        self.order = order

    def get_options(self):
        options = super(ShowUrls, self).get_options()
        options += Option('--order',
                          dest='order',
                          default=self.order,
                          help='Property on Rule to order by (default: %s)' % self.order,
                          ),

        return options

    def run(self, order):
        from flask import current_app

        print "%-30s" % 'Rule', 'Endpoint'
        print '-' * 80

        rules = sorted(current_app.url_map.iter_rules(), key=lambda rule: getattr(rule, order))
        for rule in rules:
            print "%-30s" % rule, rule.endpoint
