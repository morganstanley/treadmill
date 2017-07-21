Name: skalibs
Version: 2.4.0.2
Release: 14
Summary: Dependency for treadmill
Source0: skalibs-2.4.0.2.tar.gz
License: ISC
Group: TW
BuildRoot: %{_tmppath}/%{name}-buildroot
%description
Dependency for treadmill
%prep
%setup -q
%build
./configure --prefix=/opt/s6
make
%install
make install
install -m 755 -d $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps
install -m 755 -d $RPM_BUILD_ROOT/opt/s6/include/skalibs
install -m 755 -d $RPM_BUILD_ROOT/lib
install -m 755 sysdeps.cfg/tainnow.lib $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps/tainnow.lib
install -m 755 sysdeps.cfg/sysclock.lib $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps/sysclock.lib
install -m 755 sysdeps.cfg/spawn.lib $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps/spawn.lib
install -m 755 sysdeps.cfg/util.lib $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps/util.lib
install -m 755 sysdeps.cfg/sysdeps $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps/sysdeps
install -m 755 sysdeps.cfg/sysdeps.h $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps/sysdeps.h
install -m 755 sysdeps.cfg/timer.lib $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps/timer.lib
install -m 755 sysdeps.cfg/socket.lib $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps/socket.lib
install -m 755 sysdeps.cfg/target $RPM_BUILD_ROOT/opt/s6/lib/skalibs/sysdeps/target
install -m 755 libskarnet.so.xyzzy $RPM_BUILD_ROOT/lib/libskarnet.so.2.4.0.2
install -m 755 libskarnet.a.xyzzy $RPM_BUILD_ROOT/opt/s6/lib/skalibs/libskarnet.a
install -m 755 src/include/skalibs/config.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/config.h
install -m 755 src/include/skalibs/error.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/error.h
install -m 755 src/include/skalibs/gidstuff.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/gidstuff.h
install -m 755 src/include/skalibs/ip46.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/ip46.h
install -m 755 src/include/skalibs/setgroups.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/setgroups.h
install -m 755 src/include/skalibs/sysdeps.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/sysdeps.h
install -m 755 src/include/skalibs/uint.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/uint.h
install -m 755 src/include/skalibs/uint16.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/uint16.h
install -m 755 src/include/skalibs/uint32.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/uint32.h
install -m 755 src/include/skalibs/uint64.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/uint64.h
install -m 755 src/include/skalibs/ulong.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/ulong.h
install -m 755 src/include/skalibs/ushort.h $RPM_BUILD_ROOT/opt/s6/include/skalibs/ushort.h
%post
%files
/opt/s6/lib/skalibs/sysdeps/tainnow.lib
/opt/s6/lib/skalibs/sysdeps/sysclock.lib
/opt/s6/lib/skalibs/sysdeps/spawn.lib
/opt/s6/lib/skalibs/sysdeps/util.lib
/opt/s6/lib/skalibs/sysdeps/sysdeps
/opt/s6/lib/skalibs/sysdeps/sysdeps.h
/opt/s6/lib/skalibs/sysdeps/timer.lib
/opt/s6/lib/skalibs/sysdeps/socket.lib
/opt/s6/lib/skalibs/sysdeps/target
/opt/s6/lib/skalibs/libskarnet.a
/opt/s6/include/skalibs/config.h
/opt/s6/include/skalibs/error.h
/opt/s6/include/skalibs/gidstuff.h
/opt/s6/include/skalibs/ip46.h
/opt/s6/include/skalibs/setgroups.h
/opt/s6/include/skalibs/sysdeps.h
/opt/s6/include/skalibs/uint.h
/opt/s6/include/skalibs/uint16.h
/opt/s6/include/skalibs/uint32.h
/opt/s6/include/skalibs/uint64.h
/opt/s6/include/skalibs/ulong.h
/opt/s6/include/skalibs/ushort.h
/lib/libskarnet.so.2.4.0.2
