Name: s6
Version: 2.4.0.0
Release: 14
Summary: Dependency for treadmill
Source0: s6-2.4.0.0.tar.gz
License: ISC
Group: TW
BuildRoot: %{_tmppath}/%{name}-buildroot
%description
Dependency for treadmill
%prep
%setup -q
%build
./configure --prefix=/opt/s6 --with-include=/opt/s6/include --with-lib=/opt/s6/lib/skalibs --with-lib=/opt/s6/lib/execline
make
%install
make install
install -m 755 -d $RPM_BUILD_ROOT/opt/s6/libexec
install -m 755 -d $RPM_BUILD_ROOT/opt/s6/bin
install -m 755 -d $RPM_BUILD_ROOT/opt/s6/lib/s6
install -m 755 -d $RPM_BUILD_ROOT/opt/s6/include/s6
install -m 755 s6lockd-helper $RPM_BUILD_ROOT/opt/s6/libexec/s6lockd-helper
install -m 755 ucspilogd $RPM_BUILD_ROOT/opt/s6/bin/ucspilogd
install -m 755 s6-ftrigrd $RPM_BUILD_ROOT/opt/s6/bin/s6-ftrigrd
install -m 755 s6-ftrig-listen1 $RPM_BUILD_ROOT/opt/s6/bin/s6-ftrig-listen1
install -m 755 s6-ftrig-listen $RPM_BUILD_ROOT/opt/s6/bin/s6-ftrig-listen
install -m 755 s6-ftrig-notify $RPM_BUILD_ROOT/opt/s6/bin/s6-ftrig-notify
install -m 755 s6-ftrig-wait $RPM_BUILD_ROOT/opt/s6/bin/s6-ftrig-wait
install -m 755 s6lockd $RPM_BUILD_ROOT/opt/s6/bin/s6lockd
install -m 755 s6-cleanfifodir $RPM_BUILD_ROOT/opt/s6/bin/s6-cleanfifodir
install -m 755 s6-mkfifodir $RPM_BUILD_ROOT/opt/s6/bin/s6-mkfifodir
install -m 755 s6-svscan $RPM_BUILD_ROOT/opt/s6/bin/s6-svscan
install -m 755 s6-supervise $RPM_BUILD_ROOT/opt/s6/bin/s6-supervise
install -m 755 s6-svc $RPM_BUILD_ROOT/opt/s6/bin/s6-svc
install -m 755 s6-svscanctl $RPM_BUILD_ROOT/opt/s6/bin/s6-svscanctl
install -m 755 s6-svok $RPM_BUILD_ROOT/opt/s6/bin/s6-svok
install -m 755 s6-svstat $RPM_BUILD_ROOT/opt/s6/bin/s6-svstat
install -m 755 s6-svwait $RPM_BUILD_ROOT/opt/s6/bin/s6-svwait
install -m 755 s6-svlisten1 $RPM_BUILD_ROOT/opt/s6/bin/s6-svlisten1
install -m 755 s6-svlisten $RPM_BUILD_ROOT/opt/s6/bin/s6-svlisten
install -m 755 s6-envdir $RPM_BUILD_ROOT/opt/s6/bin/s6-envdir
install -m 755 s6-envuidgid $RPM_BUILD_ROOT/opt/s6/bin/s6-envuidgid
install -m 755 s6-fghack $RPM_BUILD_ROOT/opt/s6/bin/s6-fghack
install -m 755 s6-log $RPM_BUILD_ROOT/opt/s6/bin/s6-log
install -m 755 s6-setlock $RPM_BUILD_ROOT/opt/s6/bin/s6-setlock
install -m 755 s6-setsid $RPM_BUILD_ROOT/opt/s6/bin/s6-setsid
install -m 755 s6-softlimit $RPM_BUILD_ROOT/opt/s6/bin/s6-softlimit
install -m 755 s6-tai64n $RPM_BUILD_ROOT/opt/s6/bin/s6-tai64n
install -m 755 s6-tai64nlocal $RPM_BUILD_ROOT/opt/s6/bin/s6-tai64nlocal
install -m 755 s6-accessrules-cdb-from-fs $RPM_BUILD_ROOT/opt/s6/bin/s6-accessrules-cdb-from-fs
install -m 755 s6-accessrules-fs-from-cdb $RPM_BUILD_ROOT/opt/s6/bin/s6-accessrules-fs-from-cdb
install -m 755 s6-connlimit $RPM_BUILD_ROOT/opt/s6/bin/s6-connlimit
install -m 755 s6-ioconnect $RPM_BUILD_ROOT/opt/s6/bin/s6-ioconnect
install -m 755 s6-ipcclient $RPM_BUILD_ROOT/opt/s6/bin/s6-ipcclient
install -m 755 s6-ipcserver-access $RPM_BUILD_ROOT/opt/s6/bin/s6-ipcserver-access
install -m 755 s6-ipcserver-socketbinder $RPM_BUILD_ROOT/opt/s6/bin/s6-ipcserver-socketbinder
install -m 755 s6-ipcserver $RPM_BUILD_ROOT/opt/s6/bin/s6-ipcserver
install -m 755 s6-ipcserverd $RPM_BUILD_ROOT/opt/s6/bin/s6-ipcserverd
install -m 755 s6-sudo $RPM_BUILD_ROOT/opt/s6/bin/s6-sudo
install -m 755 s6-sudoc $RPM_BUILD_ROOT/opt/s6/bin/s6-sudoc
install -m 755 s6-sudod $RPM_BUILD_ROOT/opt/s6/bin/s6-sudod
install -m 755 s6-fdholder-daemon $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-daemon
install -m 755 s6-fdholderd $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholderd
install -m 755 s6-fdholder-delete $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-delete
install -m 755 s6-fdholder-deletec $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-deletec
install -m 755 s6-fdholder-store $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-store
install -m 755 s6-fdholder-storec $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-storec
install -m 755 s6-fdholder-retrieve $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-retrieve
install -m 755 s6-fdholder-retrievec $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-retrievec
install -m 755 s6-fdholder-list $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-list
install -m 755 s6-fdholder-listc $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-listc
install -m 755 s6-fdholder-getdump $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-getdump
install -m 755 s6-fdholder-getdumpc $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-getdumpc
install -m 755 s6-fdholder-setdump $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-setdump
install -m 755 s6-fdholder-setdumpc $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-setdumpc
install -m 755 s6-fdholder-transferdump $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-transferdump
install -m 755 s6-fdholder-transferdumpc $RPM_BUILD_ROOT/opt/s6/bin/s6-fdholder-transferdumpc
install -m 755 s6-applyuidgid $RPM_BUILD_ROOT/opt/s6/bin/s6-applyuidgid
install -m 755 s6-setuidgid $RPM_BUILD_ROOT/opt/s6/bin/s6-setuidgid
install -m 755 libs6.a.xyzzy $RPM_BUILD_ROOT/opt/s6/lib/s6/libs6.a
install -m 755 src/include/s6/config.h $RPM_BUILD_ROOT/opt/s6/include/s6/config.h
install -m 755 src/include/s6/accessrules.h $RPM_BUILD_ROOT/opt/s6/include/s6/accessrules.h
install -m 755 src/include/s6/ftrigr.h $RPM_BUILD_ROOT/opt/s6/include/s6/ftrigr.h
install -m 755 src/include/s6/s6.h $RPM_BUILD_ROOT/opt/s6/include/s6/s6.h
install -m 755 src/include/s6/s6-supervise.h $RPM_BUILD_ROOT/opt/s6/include/s6/s6-supervise.h
install -m 755 src/include/s6/s6lock.h $RPM_BUILD_ROOT/opt/s6/include/s6/s6lock.h
install -m 755 src/include/s6/s6-fdholder.h $RPM_BUILD_ROOT/opt/s6/include/s6/s6-fdholder.h
install -m 755 src/include/s6/ftrigw.h $RPM_BUILD_ROOT/opt/s6/include/s6/ftrigw.h
%post
%files
/opt/s6/libexec/s6lockd-helper
/opt/s6/bin/ucspilogd
/opt/s6/bin/s6-ftrigrd
/opt/s6/bin/s6-ftrig-listen1
/opt/s6/bin/s6-ftrig-listen
/opt/s6/bin/s6-ftrig-notify
/opt/s6/bin/s6-ftrig-wait
/opt/s6/bin/s6lockd
/opt/s6/bin/s6-cleanfifodir
/opt/s6/bin/s6-mkfifodir
/opt/s6/bin/s6-svscan
/opt/s6/bin/s6-supervise
/opt/s6/bin/s6-svc
/opt/s6/bin/s6-svscanctl
/opt/s6/bin/s6-svok
/opt/s6/bin/s6-svstat
/opt/s6/bin/s6-svwait
/opt/s6/bin/s6-svlisten1
/opt/s6/bin/s6-svlisten
/opt/s6/bin/s6-envdir
/opt/s6/bin/s6-envuidgid
/opt/s6/bin/s6-fghack
/opt/s6/bin/s6-log
/opt/s6/bin/s6-setlock
/opt/s6/bin/s6-setsid
/opt/s6/bin/s6-softlimit
/opt/s6/bin/s6-tai64n
/opt/s6/bin/s6-tai64nlocal
/opt/s6/bin/s6-accessrules-cdb-from-fs
/opt/s6/bin/s6-accessrules-fs-from-cdb
/opt/s6/bin/s6-connlimit
/opt/s6/bin/s6-ioconnect
/opt/s6/bin/s6-ipcclient
/opt/s6/bin/s6-ipcserver-access
/opt/s6/bin/s6-ipcserver-socketbinder
/opt/s6/bin/s6-ipcserver
/opt/s6/bin/s6-ipcserverd
/opt/s6/bin/s6-sudo
/opt/s6/bin/s6-sudoc
/opt/s6/bin/s6-sudod
/opt/s6/bin/s6-fdholder-daemon
/opt/s6/bin/s6-fdholder-store
/opt/s6/bin/s6-fdholder-storec
/opt/s6/bin/s6-fdholder-retrieve
/opt/s6/bin/s6-fdholder-retrievec
/opt/s6/bin/s6-fdholder-list
/opt/s6/bin/s6-fdholder-listc
/opt/s6/bin/s6-fdholder-getdump
/opt/s6/bin/s6-fdholder-getdumpc
/opt/s6/bin/s6-fdholder-setdump
/opt/s6/bin/s6-fdholder-setdumpc
/opt/s6/bin/s6-fdholder-transferdump
/opt/s6/bin/s6-fdholder-transferdumpc
/opt/s6/bin/s6-applyuidgid
/opt/s6/bin/s6-setuidgid
/opt/s6/lib/s6/libs6.a
/opt/s6/include/s6/config.h
/opt/s6/include/s6/accessrules.h
/opt/s6/include/s6/ftrigr.h
/opt/s6/include/s6/s6.h
/opt/s6/include/s6/s6-supervise.h
/opt/s6/include/s6/s6lock.h
/opt/s6/include/s6/s6-fdholder.h
/opt/s6/include/s6/ftrigw.h
/opt/s6/bin/s6-fdholderd
/opt/s6/bin/s6-fdholder-delete
/opt/s6/bin/s6-fdholder-deletec
