=================================================
Build Treadmill Binary
=================================================
::

   pip install git+https://github.com/thoughtworksinc/pex#egg=pex
   pex . -o treadmill -e treadmill.console:run -v
