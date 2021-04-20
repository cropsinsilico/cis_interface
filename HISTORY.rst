=======
History
=======

X.X.X (XXXX-XX-XX)
------------------

* Updated client/server comms & drivers to reuse response comms.
* Added C, C++, Fortran, Matlab, R versions of server in rpc_lesson1 example
* Added C, C++, Fortran, Matlab, R versions of server in rpc_lesson2 example
* Added C, C++, Fortran, Matlab, R versions of server in rpc_lesson2b example
* Added C, C++, Fortran, Matlab, R versions of server in rpc_lesson3 example
* Added C, C++, Fortran, Matlab, R versions of server in rpc_lesson3b example (still need R, Python, Matlab versions of the threaded client)
* Added C versions of rpc_lesson3b example
* Fix bug in yggdevup CLI

1.6.0 (2021-04-14) Single connection, async refactor, threading, & model copies
------------------

* Made the asynchronous comm class more generic so it can be used to wrap any comm type and is more robust
* Changed the communication pattern so that a single connection driver is used by default to limit unnecessary message passing
* Changed the connection to use ‘inputs’/‘outputs’ instead of ‘icomm_kws’/‘ocomm_kws’ to provide simpler mapping form the yaml to inputs
* Migrated away from use of ‘comm’ to ‘commtype’/‘comm_list’ keyword in comms for clarity
* Migrated away from use of comm_class to using commtype
* Added specialized error classes for catching specific issues during communication (timeouts, no message waiting, etc)
* Specialized comm registration on the comm classes
* Generalized the RPC client/server drivers in name
* Added support for importing models as functions
* Modified the RPC pattern so that client/server one-to-many send operation occurs at the interface between the connection and the server
* Added model information to message headers
* Added a ValueComm communication object for returning a constant value set in the yaml via the 'default_value' option
* Added C method for checking if a key exists in a generic wrapped map object
* Added a definition to the default compilation flags to indicate that yggdrasil is being compiled against which can be checked by the pre-compiler (e.g. #ifdef WITH_YGGDRASIL)
* Added an iteration transformation that can be used to expand an iteratable object (currently lists, dicts, and arrays) into its elements
* Added a transform class for filtering so that filters can be nested with transforms
* Added new tests for transformations as part of comms and fixed bugs that those tests showed in how empty messages are transformed
* Modify comm class such that the type is updated based on the transformed datatype when receiving *and* sending
* Added a dedicated CommMessage class for wrapping messages with information about the message (e.g. header, work comms, status) and update comm & connection methods to expect this type
* Fixed a bug that caused segfault when calling yggdrasil interface from inside a threaded model by introducing an 'allow_threading' parameter for models which sets a new parameter 'allow_multiple_comms' for comms associated with the model and causes the comm to be initialized such that multiple connections to the same address can be made (this is really just important for ZMQ comms and should only be invoked when using a server/client communication pattern)
* Allow multiple models to be run from a single YAML entry via the 'copies' model parameter.
* Added DuplicatedModelDriver to handle model duplication via 'copies'
* Added comm parameter 'dont_copy' to prevent duplication of comms (sharing) when a model is duplicated.
* Updated ZMQProxy class so that server comms 'sign on' to the proxy by responding to a sign-on message that is sent continuously until a server signs on. Requests from clients received before the sign-on exchange are backlogged and sent after sign-on.
* Updated ZMQComm to allow multiple connections during threading or when a model is duplicated.
* Added rpc_lesson2b to demonstrate use of 'copies' parameter.
* Updated the classes in the C interface to use bit flags
* Updated documentation with information on using threads with yggdrasil and more advanced RPC features.
* Refactored CommBase so that there are two components to send and receive calls and use the refactoring to cut down on repeat serialization in async comms and connection drivers.
* Change fmt input parameter to YggAsciiArrayOutput Python interface to optional
* Allow delimiter in YAML to override format_str provided via the interface for output serialization
* Refactor CommBase so that there are two components to send and receive calls and use the refactoring to cut down on repeat serialization in async comms and connection drivers.

  When sending...

  1) prepare_message, which does all of the steps from filtering, transforming, creating headers & work comms, to serializing and
  2) send_message which does sends messages including iterator messages and work comms.

  When receiving...

  1) recv_message, which receives the message and deserializes it, and
  2) finalize_message, which filters and transforms messages and performs actions associated with specific message types.


1.5.0 (2021-02-10) Migrate to GHA, refactor CLI, & fix bugs
------------------

* Move continuous integration for testing and deployment to Github actions
* Refactor the command line interface and add the `yggdrasil [subcommand]` CLI with subcommands for other command line actions so that the CLI can be called with a specific version of Python via `python -m yggdrasil [subcommand]`
* Fix bug where colons cause environment variables to be invalid for R models run in Conda environments on Ubuntu
* Update the conda recipe so that the yggdrasil configuration file and R package are removed on uninstall


1.4.0 (2020-12-09) Support for OpenSimRoot models, wrapped functions as clients/servers, & misc. features/bug fixes
------------------

General
~~~~~~~

* Added driver for running OpenSimRoot models
* Added a new  'demo' directory to contain submodules linking to external materials that can be used in demos, but tested with the repo as part of the CI
* Added FSPM demo materials as a submodule
* Added support for “global” comms that can be reused between calls on the same process (and different threads, though there needs to be additional work to make non-client/server comms fully thread safe)
* Added support for auto-wrapping functions for use as servers/clients and that contain yggdrasil calls
* Added rpc example demonstrating use of the “global” comms feature to support wrapping of functions for client/server call patterns
* Created config context for handling runtime options as controlled by combinations of CLI arguments and configuration files
* Removed use of “last_header” attribute on comms to eliminate ambiguity when messages are received asynchronously in the background
* Streamlined how RMQ import is tested so that RMQComm is the basis instead of RMQAsyncComm
* Added interface regex to model drivers for locating & replacing existing yggdrasil imports/calls in wrapped code when ‘global’ version should be used in the case of R
* Change interface behavior for all Python-based languages (R & Matlab) to no longer assume format_str values of ‘%s’ for client/server comms (this prevents defaulting to arrays)
* Added support for use of trimesh objects with ply/obj messages
* Added tools for displaying code w/ syntax highlighting
* Improved error handling in yaml processing including checking for duplicates

Command Line Interface
~~~~~~~~~~~~~~~~~~~~~~

* Added CLI utilities for updating after pulling development updates (yggdefup) and compiling the interface libraries (yggcompile)
* Improved the CLI utilities for getting compilation flags to allow language/os specific options

Testing
~~~~~~~

* Cleaned up test output to limit log (after reaching log limit on Travis CI)
* Added test fixtures for demos
* Created test context for handling configuration and environment variables that control which tests will be skipped
* Added coverage pragmas for handling specific cases
* Updated how tests are identified to eliminate unnecessary languages from test discovery (avoid superfluous skips)
* Removed explicit version of sbml test required by differences in release on different os (this has been resolved)
* Added additional flags for improving the performance of tests
* Generalized CI setup script to consolidate dependencies and streamline installation

General bug fixes
~~~~~~~~~~~~~~~~~

* Stopped duplicate logging output
* Compile internal dependencies on demand when compilation/linking flags are requested
* Avoid infinite loop when auto wrapping functions without any inputs
* Fixed a bug in the WOFOST serializer for null units
* Fixed bug in the method used to extract units from versions used by other languages (including unicode characters for degree) where calling the method twice resulted in an incomplete unit string
* Fixed bug in handling of dimensionless quantities when checking for units
  
Fortran Interface
~~~~~~~~~~~~~~~~~

* Added support for passing references to relocatable types in function wrappers
* Don’t split lines that include macros
* Added support for wrapping functions in modules
* Fixed bug following updates to the gfortran compiler on conda-forge that removed support for mapping to character arrays (rather than arrays of characters)
* Added optional arguments to client/server interfaces (for the format strings)
* Added versions of client/server interfaces in that allow direct type specification

R Interface
~~~~~~~~~~~

* Fixed bugs in the handling of conversions for units and null objects
* Added support for named arguments in the R interface

C/C++ Interface
~~~~~~~~~~~~~~~

* Fixed a bug where arguments were not being correctly skipped (now they are explicitly skipped based on the expected type)
* Added support for std::string typed names as input to the C++ interface
* Fix bug in C++ function regex when reference/pointer operators are included in the types
* Added versions of client/server interfaces in that allow direct type specification

Matlab Interface
~~~~~~~~~~~~~~~~

* Fixed a bug in the Matlab to Python object transformation
* Added support for keyword arguments to the Matlab interface


1.3.0 (2020-07-08) Support for Fortran Models
------------------

* Fortran interface which uses the Fortran 2003 standard (f70, f90 will be added at a later date)
* Fortran versions of all examples
* Tests for use of GNU and LLVM compilers on Windows


1.2.0 (2020-06-11) Support for WOFOST parameter files, NetCDF files, SBML models, & automated timestep synchronization
------------------

* Add support for reading/writing WOFOST parameter files.
* Add support for reading/writing NetCDF files.
* Update tests for serialization/comms/filters/transforms so that tests are generated automatically.
* Add support for running SBML models.
* Add dedicated base class for domain specific languages.
* Allow connections to be run in processes as well as threads.
* New submodule for handling threading/multiprocessing uniformly and interchangeably.
* Add dedicated driver for handling synchronization of scalar variables between time based models at each timestep that can be invoked via a yaml parameter.


1.1.1 (2020-03-20) Matlab bug fix
------------------

* Fixes a bug where on some operating systems, the environment variables in the process used to launch Matlab are not inherited by the Matlab script.
* Minor changes to CI setup


1.1.0 (2020-03-16) Drop Python 2 + Misc.
------------------

* Droped support for Python 2
* Added schema for generating model form
* Move configuration out of model driver classes to speed up and simplify import
* Various bug fixes for installation (search directory for Matlab, default python include/libraries, etc.)
* Allow for matlab <r2019a call signature which doesn’t include -batch option
* Various fixes for pandas compatibility across languages including reading as string vs. bytes.
* Added option for including other yamls files
* Fixed bug in CLI for getting C/C++ compiler/linker flags
* Move doutside_loop to comm (not valid on file)
* Added tests for transforms and fixed various bugs in transformations
* Added buffer comm which stores messages in-memory
