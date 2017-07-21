Name: treadmill-pid1
Version: 1.0
Release: 3
Summary: Dependency for treadmill
Source0: treadmill-pid1-1.0.tar.gz
License: Apache 2
Group: TW
BuildRoot: %{_tmppath}/%{name}-buildroot
%description
Treadmill treadmill-pid1 utility
%prep
%setup -q
%build
make
%install
install -m 755 -d $RPM_BUILD_ROOT/opt/treadmill-pid1/bin
install -m 755 pid1 $RPM_BUILD_ROOT/opt/treadmill-pid1/bin/pid1
%post
%files
/opt/treadmill-pid1/bin/pid1
