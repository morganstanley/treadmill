% Unit test for LAF authorization policy.
%
% vim: set filetype=prolog:
%

:- begin_tests(ssh_pam_policy).

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% Define pam_sshd specific mock directives
:- multifile(treadmill_dcache_init/0).
:- multifile(treadmill_init_env/0).
:- multifile(treadmill_init_krb/0).
treadmill_dcache_init.
treadmill_init_env.
treadmill_init_krb.

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
:- working_directory(_Old, 'etc/policy/pam').
:- consult('pam_sshd.pro').

% Load mock predicates.
:- load_files('../lib/prolog/mock/annotate_tam.pro',
              [redefine_module(true), imports([])]).
:- load_files('../lib/prolog/mock/dcache.pro',
              [redefine_module(true), imports([])]).
:- load_files('../lib/prolog/mock/fwd.pro',
              [redefine_module(true), imports([])]).
:- load_files('../lib/prolog/mock/proid.pro',
              [redefine_module(true), imports([])]).
:- load_files('../lib/prolog/mock/tam.pro',
              [redefine_module(true), imports([])]).
:- load_files('../lib/prolog/mock/yaml.pro',
              [redefine_module(true), imports([])]).

% Tests mock manifest load and subsequent authorization.
test(auth_by_manifest_tam, [nondet]) :-
    recorda(tam_activity,
            mock(user1, proid(proid1), 'login'),
            MockTamActivity),
    recorda(yaml_loadfile,
            mock('/app.yml', [name(foo), proid(proid1)]),
            MockAppYaml),
    recorda(proid,
            mock('proid1', 'is1.morgan',
                 [environment(dev), type('appsec-ctx')]),
            MockProid),
    authorize_by_manifest(user1, '/app.yml'),
    \+ authorize_by_manifest(user2, '/app.yml'),

    erase(MockAppYaml),
    erase(MockProid),
    erase(MockTamActivity).

:- end_tests(ssh_pam_policy).
