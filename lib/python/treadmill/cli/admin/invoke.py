"""Implementation of treadmill admin CLI API invocation.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import inspect
import io

import click
import decorator
import jsonschema

from treadmill import authz as authz_mod
from treadmill import cli
from treadmill import context
from treadmill import plugin_manager
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import api as api_mod


def make_command(parent, name, func):
    """Make a command using reflection on the function."""
    # Disable "Too many branches" warning.
    #
    # pylint: disable=R0912
    argspec = decorator.getargspec(func)
    args = list(argspec.args)
    defaults = argspec.defaults
    if defaults is None:
        defaults = []
    else:
        defaults = list(defaults)

    @parent.command(name=name, help=func.__doc__)
    def command(*args, **kwargs):
        """Constructs a command handler."""
        try:
            if 'rsrc' in kwargs:
                with io.open(kwargs['rsrc'], 'rb') as fd:
                    kwargs['rsrc'] = yaml.load(stream=fd)

            formatter = cli.make_formatter(None)
            cli.out(formatter(func(*args, **kwargs)))

        except jsonschema.exceptions.ValidationError as input_err:
            click.echo(input_err, err=True)
        except jsonschema.exceptions.RefResolutionError as res_error:
            click.echo(res_error, err=True)
        except authz_mod.AuthorizationError as auth_err:
            click.echo('Not authorized.', err=True)
            click.echo(auth_err, err=True)
        except TypeError as type_err:
            click.echo(type_err, err=True)

    while defaults:
        arg = args.pop()
        defarg = defaults.pop()
        if defarg is not None:
            argtype = type(defarg)
        else:
            argtype = str

        if defarg == ():
            # redefinition of the type from tuple to list.
            argtype = cli.LIST
            defarg = None

        click.option('--' + arg, default=defarg, type=argtype)(command)

    if not args:
        return

    arg = args.pop(0)
    click.argument(arg)(command)

    while args:
        if len(args) == 1:
            arg = args.pop(0)
            click.argument(
                arg,
                type=click.Path(exists=True, readable=True)
            )(command)
        else:
            arg = args.pop(0)
            click.argument(arg)(command)

    if args:
        raise click.UsageError('Non-standard API: %s, %r' % (name, argspec))


def make_resource_group(ctx, parent, resource_type, api=None):
    """Make click group for a resource type."""

    if api is None:
        mod = plugin_manager.load('treadmill.api', resource_type)
        if not mod:
            return

        try:
            api_cls = getattr(mod, 'API')
            api = ctx.build_api(api_cls)
        except AttributeError:
            return

    @parent.group(name=resource_type, help=api.__doc__)
    def _rsrc_group():
        """Creates a CLI group for the given resource type.
        """

    for verb in dir(api):
        if verb.startswith('__'):
            continue

        func = getattr(api, verb)

        if inspect.isclass(func):
            make_resource_group(ctx, _rsrc_group, verb, func)
        elif inspect.isfunction(func):
            make_command(_rsrc_group, verb, func)
        else:
            pass


def init():
    """Constructs parent level CLI group."""

    ctx = api_mod.Context()

    @click.group(name='invoke')
    @click.option('--authz', required=False)
    @click.option('--cell', required=True,
                  envvar='TREADMILL_CELL',
                  callback=cli.handle_context_opt,
                  expose_value=False)
    def invoke_grp(authz):
        """Directly invoke Treadmill API without REST."""
        if authz is not None:
            ctx.authorizer = authz_mod.ClientAuthorizer(
                utils.get_current_username, authz
            )
        else:
            ctx.authorizer = authz_mod.NullAuthorizer()

        if cli.OUTPUT_FORMAT is None:
            raise click.BadParameter('must use --outfmt [json|yaml]')

    for resource in sorted(plugin_manager.names('treadmill.api')):
        # TODO: for now, catch the ContextError as endpoint.py and state.py are
        # calling context.GLOBAL.zk.conn, which fails, as cell is not set yet
        try:
            make_resource_group(ctx, invoke_grp, resource)
        except context.ContextError:
            pass

    return invoke_grp
