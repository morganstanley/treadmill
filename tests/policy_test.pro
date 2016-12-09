% Unit test for LAF authorization policy.
%
% vim: set filetype=prolog:
%

:- begin_tests(policy).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Define policy specific mock directives
:- multifile(treadmill_dcache_init/0).
treadmill_dcache_init.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
:- working_directory(_Old, 'etc/policy').
:- consult('policy.pro').

% Load mock predicates.
:- load_files('../lib/prolog/mock/annotate_tam.pro',
              [redefine_module(true), imports([])]).
:- load_files('../lib/prolog/mock/dcache.pro',
              [redefine_module(true), imports([])]).
:- load_files('../lib/prolog/mock/ldap.pro',
              [redefine_module(true), imports([])]).
:- load_files('../lib/prolog/mock/proid.pro',
              [redefine_module(true), imports([])]).
:- load_files('../lib/prolog/mock/tam.pro',
              [redefine_module(true), imports([])]).

mock_proid(Proid, Env, Type, Mode, MockProid) :-
    recorda(tam_proid_data,
            mock(proid(Proid, 'is1.morgan'),
                 data([environment(Env), proidtype(Type), tammode(Mode)])),
            MockProid).

mock_proid(Proid, Env, Type, Mode) :-
    recorda(tam_proid_data,
            mock(proid(Proid, 'is1.morgan'),
                 data([environment(Env), proidtype(Type), tammode(Mode)]))).

% Test treadmill_admin predicate based on treadmill-core group membership.
test(treadmill_admin, [nondet]) :-
    mock_proid('proid1', 'dev', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
            mock(xxx, eonid('43626'), 'write-data', 'dev')),
    setenv('USER', 'proid1'),

    treadmill_admin(xxx),

    unsetenv('proid1'),
    foreach(recorded(_, _, Mock), erase(Mock)).

test(treadmill_admin, [nondet]) :-
    mock_proid('proid1', 'qa', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
            mock(xxx, eonid('43626'), 'write-data', 'dev')),
    setenv('USER', 'proid1'),

    \+ treadmill_admin(xxx),

    unsetenv('proid1'),
    foreach(recorded(_, _, Mock), erase(Mock)).

test(treadmill_admin, [nondet]) :-
    mock_proid('proid1', 'dev', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
            mock(xxx, eonid('12345'), 'write-data', 'dev')),
    setenv('USER', 'proid1'),

    \+ treadmill_admin(xxx),

    unsetenv('proid1'),
    foreach(recorded(_, _, Mock), erase(Mock)).

% Test app creation payload predicate based on explicit krb owner.
test(app_payload, [nondet]) :-
    mock_proid('proid1', 'dev', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
            mock(xxx, eonid(12345), 'deploy-resource-configuration', 'dev')),
    recorda(tam_activity,
            mock(xxx, proid(proid1), 'deploy-application-configuration')),
    recorda(tam_host_data,
           mock(host(bar), data([eonid(12345), environment('dev')]))),

    authorize(xxx, create, app('proid1.foo.1', '--- {}')),
    \+ authorize(xxx, create, app('proid1.foo.1',
                                  '--- { passthrough: [foo] }')),
    authorize(xxx, create, app('proid1.foo.1',
                               '--- { passthrough: [bar] }')),
    \+ authorize(xxx, create, app('proid1.foo.1',
                                  '--- { shared_network: True }')),
    authorize(xxx, create, app('proid1.foo.1',
                               '--- { affinity: proid1.foo }')),
    \+ authorize(xxx, create, app('proid1.foo.1',
                                  '--- { affinity: proid_XXX.foo }')),
    authorize(xxx, create, app('proid1.foo.1',
                                  '--- { affinity: self }')),
    authorize(xxx, delete, app('proid1.foo.1', whatever)),
    authorize(xxx, gc, app('proid1.*', whatever)),
    \+ authorize(xxx, create, app('proid1.foo.1',
                                  '--- { tickets: [proid_XXX] }')),
    authorize(xxx, create, app('proid1.foo.1',
                                  '--- { tickets: [proid1] }')),
    authorize(xxx, create, app('proid1.foo.1',
                                  '--- { identity_group: proid1.foo }')),
    \+ authorize(xxx, create, app('proid1.foo.1',
                                  '--- { identity_group: proid_XXX.foo }')),

    foreach(recorded(_, _, Mock), erase(Mock)).

% test app authorization predicate based on TAM activity.
test(app_activities_tam, [nondet]) :-
    mock_proid('proid1', 'dev', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
            mock(xxx, proid(proid1), 'deploy-application-configuration')),

    authorize(xxx, delete, app('proid1.foo.1', '--- {}')),
    authorize(xxx, create, app('proid1.foo.1', '--- {}')),

    foreach(recorded(_, _, Mock), erase(Mock)),

    mock_proid('proid1', 'dev', 'appsec-ctx', 'mixed'),

    \+ authorize(xxx, delete, app('proid1.foo.1', '--- {}')),
    \+ authorize(xxx, gc, app('proid1.*', '--- {}')),
    \+ authorize(xxx, create, app('proid1.foo.1', '--- {}')),

    foreach(recorded(_, _, Mock), erase(Mock)).

test(app_personal, [nondet]) :-
    authorize(usera, create,
        app('usera@groupb.foo', '--- {}')),
    authorize(usera, create,
        app('usera@groupb.foo', '--- { tickets: [\'usera@is1.morgan\'] }')),
    authorize(usera, create,
        app('usera@groupb.foo', '--- { tickets: [\'usera@MSAD.MS.COM\'] }')),
    \+ authorize(usera, create,
        app('usera@groupb.foo', '--- { tickets: [\'xxx@MSAD.MS.COM\'] }')),
    \+ authorize(usera, create,
        app('usera@groupb.foo',
            '--- { affinity: someother.foo }')).

% test lbendpoint authorization predicate based on TAM activity.
test(lbendpoint_activities_tam, [nondet]) :-
    mock_proid('proid1', 'env-doesnotmatter', 'appsec-ctx', 'mixed'),
    \+ authorize(xxx, delete, lbendpoint('proid1.foo.1', '--- {}')),
    \+ authorize(xxx, create, lbendpoint('proid1.foo.1', '--- {}')),

    recorda(tam_activity,
            mock(xxx, proid(proid1), 'deploy-resource-configuration')),

    authorize(xxx, delete, lbendpoint('proid1.foo.1', '--- {}')),
    authorize(xxx, create, lbendpoint('proid1.foo.1', '--- {}')),
    \+ authorize(xxx, create, lbendpoint('proid1.foo.1', '--- {port: 80}')),
    \+ authorize(xxx, update, lbendpoint('proid1.foo.1', '--- {port: 80}')),

    foreach(recorded(_, _, Mock), erase(Mock)).

% test identity_group authorization predicate based on TAM activity.
test(identity_group_activities_tam, [nondet]) :-
    mock_proid('proid1', 'env-doesnotmatter', 'appsec-ctx', 'mixed'),
    \+ authorize(xxx, delete, identity_group('proid1.foo.1', '--- {}')),
    \+ authorize(xxx, create, identity_group('proid1.foo.1', '--- {}')),

    recorda(tam_activity,
            mock(xxx, proid(proid1), 'deploy-resource-configuration')),

    authorize(xxx, delete, identity_group('proid1.foo.1', '--- {}')),
    authorize(xxx, create, identity_group('proid1.foo.1', '--- {}')),

    foreach(recorded(_, _, Mock), erase(Mock)).

% test app authorization predicate based on TAM activity.
test(archive_activities_tam, [nondet]) :-
    mock_proid('proid1', 'dev', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
            mock(jdoe, proid(proid1), 'read-data'),
            MockReadDataActivity),

    authorize(jdoe, fetch, archive('cell/proid1.foo.1/archive_id', '--- {}')),

    erase(MockReadDataActivity),

    % fetch verb
    \+ authorize(jdoe, fetch, archive('cell/proid1.foo.1/archive_id',
                                      '--- {}')),
    authorize('proid1', fetch, archive('cell/proid1.foo.1/archive_id',
                                       '--- {}')),

    % files verb
    \+ authorize(jdoe, files, archive('cell/proid1.foo.1/archive_id',
                                      '--- {}')),
    authorize('proid1', files, archive('cell/proid1.foo.1/archive_id',
                                       '--- {}')),

    % file verb
    \+ authorize(jdoe, file, archive('cell/proid1.foo.1/archive_id',
                                      '--- {name: foo}')),
    authorize('proid1', file, archive('cell/proid1.foo.1/archive_id',
                                       '--- {name: foo}')),

    foreach(recorded(_, _, Mock), erase(Mock)).

%% TAM resource ownership
test(resource_owner_tam, [nondet]) :-
    mock_proid('proid1', 'envdoesnotmatter', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
            mock(xxx, proid(proid1), 'deploy-application-configuration')),

    resource_owner(xxx, 'proid1', 'deploy-application-configuration'),
    foreach(recorded(_, _, Mock), erase(Mock)).

test(treadmill_admin_actions, [nondet]) :-
    mock_proid('proid1', 'prod', 'appsec-ctx', 'tam'),
    recorda(tam_activity,
            mock(xxx, eonid('43626'), 'write-data', 'prod')),
    setenv('USER', 'proid1'),

    authorize(xxx, create, app('someproid.foo.1', whatever)),
    authorize(xxx, create, app('someproid.foo.1',
                               '--- { passthrough: [foo] }')),
    authorize(xxx, create, app('someproid.foo.1',
                               '--- { shared_network: foo } ')),
    authorize(xxx, delete, app('someproid.foo.1', whatever)),
    authorize(xxx, update, app('someproid.foo.1', whatever)),
    authorize(xxx, create, cell(somekey, whatever)),
    authorize(xxx, delete, cell(somekey, whatever)),
    authorize(xxx, update, cell(somekey, whatever)),
    authorize(xxx, create, cell_master(somekey, whatever)),
    authorize(xxx, delete, cell_master(somekey, whatever)),
    authorize(xxx, update, cell_master(somekey, whatever)),
    authorize(xxx, create, lbvip(somekey, whatever)),
    authorize(xxx, delete, lbvip(somekey, whatever)),
    authorize(xxx, update, lbvip(somekey, whatever)),
    authorize(xxx, fetch, archive(somekey, whatever)),
    authorize(xxx, create, instance('proid1.somekey', whatever)),
    authorize(xxx, delete, instance('proid1.somekey', whatever)),
    authorize(xxx, update, instance('cproid1.somekey', whatever)),
    authorize(xxx, insert, blackout(somekey, whatever)),
    authorize(xxx, remove, blackout(somekey, whatever)),
    unsetenv('proid1'),
    foreach(recorded(_, _, Mock), erase(Mock)).

% Test app factory actions. Proid X can control app X if it is appsec-ctx
% type.
test(app_factory_actions, [nondet]) :-
    mock_proid('proid1', 'prod', 'appsec-ctx', 'mixed'),
    mock_proid('proidftp', 'prod', 'ftp', 'mixed'),

    authorize('proid1', create, app('proid1.foo', '{}')),
    \+ authorize('user1', create, app('user1.foo', '{}')),
    \+ authorize('proidftp', create, app('proidftp.foo', '{}')),
    authorize('proid1', fetch, archive('cell/proid1.foo', '{}')),
    authorize('user1', fetch, archive('cell/user1.foo', '{}')),

    foreach(recorded(_, _, Mock), erase(Mock)).

% Test anonymous get/list.
test(resource_get_list, [nondet]) :-
    authorize(xxx, list, app(somekey, whatever)),
    authorize(xxx, get, app(somekey, whatever)),
    authorize(xxx, list, cell(somekey, whatever)),
    authorize(xxx, get, cell(somekey, whatever)),
    authorize(xxx, list, lbvip(somekey, whatever)),
    authorize(xxx, get, lbvip(somekey, whatever)),
    authorize(xxx, list, archive(somekey, whatever)),
    authorize(xxx, get, archive(somekey, whatever)).

% Test instance actions.
test(instance_actions, [nondet]) :-
    mock_proid('proid1', 'prod', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
        mock(xxx, proid(proid1), 'control-runtime-application')),
    recorda(tam_activity,
        mock(xxx, proid(proid1), 'deploy-application-configuration')),

    authorize(xxx, create, instance('proid1.xxx#1234', '--- {}')),
    authorize(xxx, delete, instance('proid1.xxx#1234', '--- {}')),
    authorize(xxx, update, instance('proid1.xxx#1234', '--- {}')),
    authorize(proid1, create, instance('proid1.xxx#1234', '--- {}')),
    authorize(proid1, delete, instance('proid1.xxx#1234', '--- {}')),
    authorize(proid1, update, instance('proid1.xxx#1234', '--- {}')),

    foreach(recorded(_, _, Mock), erase(Mock)).

% Test instance actions.
test(appmonitor_actions, [nondet]) :-
    mock_proid('proid1', 'prod', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
        mock(xxx, proid(proid1), 'control-runtime-application')),
    %recorda(tam_activity,
    %    mock(xxx, proid(proid1), 'deploy-application-configuration')),

    authorize(xxx, create, app_monitor('proid1.xxx:cell1', '--- {}')),
    authorize(xxx, delete, app_monitor('proid1.xxx:cell1', '--- {}')),
    authorize(xxx, update, app_monitor('proid1.xxx:cell1', '--- {}')),
    authorize(proid1, create, app_monitor('proid1.xxx:cell1', '--- {}')),
    authorize(proid1, delete, app_monitor('proid1.xxx:cell1', '--- {}')),
    authorize(proid1, update, app_monitor('proid1.xxx:cell1', '--- {}')),

    foreach(recorded(_, _, Mock), erase(Mock)).

test(authorize_root, [nondet]) :-
    mock_proid('proid1', 'envdoesnotmatter', 'appsec-ctx', 'mixed'),
    recorda(tam_activity,
            mock(xxx, proid(proid1), 'deploy-application-configuration')),

    authorize(xxx, create, app('proid1.xxx',
                               '--- { services: [{name: xxx, cmd: yyy}] }')),

    \+ authorize(xxx, create, app('proid1.xxx',
                               '--- { services: [{name: xxx, root: True}] }')),
    foreach(recorded(_, _, Mock), erase(Mock)).

test(authorize_tenant, [nondet]) :-
    recorda(
        tam_activity,
        mock(xxx, eonid('1111'), 'deploy-resource-configuration', 'prod')
    ),
    recorda(
        tam_activity,
        mock(xxx, eonid('2222'), 'deploy-resource-configuration', 'prod')
    ),
    recorda(
        tam_activity,
        mock(yyy, eonid('1111'), 'deploy-resource-configuration', 'dev')
    ),
    authorize(xxx, create, tenant('x:y', '--- {systems: [1111]}')),
    \+ authorize(yyy, create, tenant('x:y', '--- {systems: [1111]}')),
    \+ authorize(xxx, create, tenant('x:y', '--- {systems: [1111, 2]}')),
    recorda(
        ldap_search_attrs,
        mock('tenant=y,tenant=x,ou=allocations,ou=treadmill,dc=ms,dc=com',
             'base',
             '(objectclass=tmTenant)', [system('1111')])
    ),
    authorize(xxx, update, tenant('x:y', '--- {systems: [2222]}')),
    \+ authorize(xxx, update, tenant('x:y', '--- {systems: [99]}')),
    authorize(xxx, delete, tenant('x:y', '--- {}')),
    \+ authorize(yyy, create, tenant('x:y', '--- {}')),

    foreach(recorded(_, _, Mock), erase(Mock)).

test(allocation_activities_tam, [nondet]) :-
    allocation_tenant('foo:bar/baz', 'foo:bar'),
    allocation_tenant('foo/baz', 'foo'),
    reservation_alloc('foo:bar/baz/reservation/prod', 'foo:bar/baz'),
    assignment_alloc(
        'foo:bar/baz/assignment/somecell/someproid.*',
        'foo:bar/baz',
        'someproid'
    ),
    recorda(
        tam_activity,
        mock(xxx, eonid('1111'), 'deploy-resource-configuration', 'prod')
    ),
    recorda(
        tam_activity,
        mock(yyy, eonid('1111'), 'deploy-resource-configuration', 'dev')
    ),
    recorda(
        tam_activity,
        mock(yyy, proid(proida), 'deploy-application-configuration')
    ),
    recorda(
        ldap_search_attrs,
        mock('tenant=y,tenant=x,ou=allocations,ou=treadmill,dc=ms,dc=com',
             'base',
             '(objectclass=tmTenant)', [system('1111')])
    ),
    recorda(
        ldap_search_attrs,
        mock(
    'allocation=a,tenant=y,tenant=x,ou=allocations,ou=treadmill,dc=ms,dc=com',
            'base',
            '(objectclass=tmAllocation)', [environment('dev')]
        )
    ),
    allocation_system('x:y/a', '1111'),
    allocation_environment('x:y/a', 'dev'),
    authorize(xxx, create, allocation('x:y/a', '--- {environment: dev}')),
    authorize(xxx, delete, allocation('x:y/a', '--- {environment: dev}')),
    \+ authorize(xxx, update, allocation('x:y/a', '--- {environment: dev}')),
    % Creating allocation is prod action, regardless of allocation
    % environment.
    \+ authorize(yyy, create, allocation('x:y/a', '--- {environment: dev}')),
    \+ authorize(yyy, delete, allocation('x:y/a', '--- {environment: dev}')),
    \+ authorize(yyy, update, allocation('x:y/a', '--- {environment: dev}')),
    % Creating reservation is prod action regardless of environment.
    authorize(xxx, create, reservation(
        'x:y/a/reservation/somecell', '--- {}')),
    authorize(xxx, update, reservation(
        'x:y/a/reservation/somecell', '--- {}')),
    authorize(xxx, delete, reservation(
        'x:y/a/reservation/somecell', '--- {}')),
    \+ authorize(yyy, create, reservation(
        'x:y/a/reservation/somecell', '--- {}')),
    \+ authorize(yyy, update, reservation(
        'x:y/a/reservation/somecell', '--- {}')),
    \+ authorize(yyy, delete, reservation(
        'x:y/a/reservation/somecell', '--- {}')),
    % Creating assingment is aligned with allocation environment.
    recorda(
        tam_proid_data,
        mock(
            proid(proida, 'is1.morgan'),
            data([eonid('1111'), environment('dev')]))
    ),
    /*
    \+ authorize(xxx, create, assignment(
        'x:y/a/assignment/somecell/proida.*', '--- {}')),
    \+ authorize(xxx, update, assignment(
        'x:y/a/assignment/somecell/proida.*', '--- {}')),
    \+ authorize(xxx, delete, assignment(
        'x:y/a/assignment/somecell/proida.*', '--- {}')),
    */
    authorize(yyy, create, assignment(
        'x:y/a/assignment/somecell/proida.*', '--- {}')),
    authorize(yyy, update, assignment(
        'x:y/a/assignment/somecell/proida.*', '--- {}')),
    authorize(yyy, delete, assignment(
        'x:y/a/assignment/somecell/proida.*', '--- {}')),
    foreach(recorded(_, _, Mock), erase(Mock)).

:- end_tests(policy).
