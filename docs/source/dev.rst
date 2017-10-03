=================================================
Treadmill Binary
=================================================

**Install PEX (Python EXecutable):**

::

   pip install git+https://github.com/thoughtworksinc/pex#egg=pex

**Build:**


Make sure you have cloned the treadmill source to build the binary. Then, to  build treadmill pex binary and RPM -


::

   treadmill build_binary -s <treadmill_source_path> -t <release_tag> -m <release_message>
