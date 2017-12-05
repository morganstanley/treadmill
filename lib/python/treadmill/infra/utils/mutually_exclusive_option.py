import click
import yaml

_OPTIONS_FILE = 'manifest'


class MutuallyExclusiveOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        help = kwargs.get('help', '')
        if self.mutually_exclusive:
            ex_str = ', '.join(self.mutually_exclusive)
            kwargs['help'] = help + (
                ' NOTE: This argument is mutually exclusive with'
                ' arguments: [' + ex_str + '].'
            )
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.mutually_exclusive.intersection(opts) and \
           self.name in opts:
            raise click.UsageError(
                "Illegal usage: `{}` is mutually exclusive with "
                "arguments `{}`.".format(
                    self.name,
                    ', '.join(self.mutually_exclusive)
                )
            )
        if self.name == _OPTIONS_FILE and self.name in opts:
            _file = opts.pop(_OPTIONS_FILE)
            for _param in ctx.command.params:
                opts[_param.name] = _param.default or \
                    _param.value_from_envvar(ctx) or ''
            with open(_file, 'r') as stream:
                data = yaml.load(stream)

            _command_name = ctx.command.name
            if data.get(_command_name, None):
                opts.update(data[_command_name])
            else:
                raise click.BadParameter(
                    'Manifest file should have %s scope' % _command_name
                )
            opts['vpc_id'] = opts.pop('vpc_name')
            ctx.params = opts

        return super().handle_parse_result(ctx, opts, args)
