#!/bin/bash

export YGG_DEBUG="INFO"
export YGG_NAMESPACE="rpc_lesson3b"

yaml1= 
yaml2= 

# ----------------Your Commands------------------- #
case $1 in
    "" | -p | --python )
	echo "Running Python"
	yaml1='server_python.yml'
	yaml2='client_c.yml'
	;;
    -m | --matlab )
	echo "Running Matlab"
	yaml1='server_python.yml'
	yaml2='client_c.yml'
	;;
    -c | --gcc )
	echo "Running C"
	yaml1='server_c.yml'
	yaml2='client_c.yml'
	;;
    --cpp | --g++)
	echo "Running C++"
	yaml1='server_cpp.yml'
	yaml2='client_cpp.yml'
	;;
    -R | -r | --R | --r )
	echo "Running R"
	yaml1='server_r.yml'
	yaml2='client_c.yml'
	;;
    -f | --fortran )
	echo "Running Fortran"
	yaml1='server_fortran.yml'
	yaml2='client_fortran.yml'
	;;
esac

yggrun $yaml1 $yaml2

outfile="${TMPDIR}client_output.txt"
cat $outfile
