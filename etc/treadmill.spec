Name: treadmill
Version: 0.1
Release: 0
Summary: Treadmill
Source0: treadmill-0.1.0.tar.gz
Requires: python34
License: Apache License Version 2.0
BuildArch: noarch
BuildRoot: %{_tmppath}/%{name}-buildroot
%description
lightweight, container-based compute fabric
%prep
%setup -q
%build
%install
install -m 0755 -d $RPM_BUILD_ROOT/bin
install -m 0755 treadmill $RPM_BUILD_ROOT/bin/treadmill
%clean
%post
%files
/bin/treadmill
