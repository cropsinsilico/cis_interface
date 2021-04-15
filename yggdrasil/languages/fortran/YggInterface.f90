module fygg

  ! TODO: Ensure that dynamically allocated C/C++ variables are freed.
  use iso_c_binding
  implicit none

  integer, parameter :: LINE_SIZE_MAX = 2048
  integer, parameter :: YGG_MSG_BUF = 2048
  integer, parameter :: ascii = selected_char_kind ("ascii")
#ifdef _WIN32
  integer, parameter :: ucs4  = 1
#else
  integer, parameter :: ucs4  = selected_char_kind ('ISO_10646')
#endif
  integer(kind=c_int), bind(c, name="YGG_MSG_MAX_F") :: YGG_MSG_MAX
  real(8),  parameter :: PI_8  = 4 * atan (1.0_8)
  real(16), parameter :: PI_16 = 4 * atan (1.0_16)

  interface yggarg
     module procedure yggarg_scalar_unsigned1
     module procedure yggarg_scalar_unsigned2
     module procedure yggarg_scalar_unsigned4
     module procedure yggarg_scalar_unsigned8
     module procedure yggarg_scalar_integer2
     module procedure yggarg_scalar_integer4
     module procedure yggarg_scalar_integer8
     module procedure yggarg_scalar_real4
     module procedure yggarg_scalar_real8
#ifndef _WIN32
     module procedure yggarg_scalar_real16
#endif
     module procedure yggarg_scalar_complex4
     module procedure yggarg_scalar_complex8
#ifndef _WIN32
     module procedure yggarg_scalar_complex16
#endif
     module procedure yggarg_scalar_logical1
     module procedure yggarg_scalar_logical2
     module procedure yggarg_scalar_logical4
     module procedure yggarg_scalar_logical8
     module procedure yggarg_scalar_character
#ifndef _WIN32
     module procedure yggarg_scalar_unicode
#endif
     module procedure yggarg_scalar_yggchar_r
     module procedure yggarg_scalar_ply
     module procedure yggarg_scalar_obj
     module procedure yggarg_scalar_null
     module procedure yggarg_scalar_generic
     module procedure yggarg_scalar_yggarr
     module procedure yggarg_scalar_yggmap
     module procedure yggarg_scalar_yggschema
     module procedure yggarg_scalar_yggpython
     module procedure yggarg_scalar_yggpyinst
     module procedure yggarg_scalar_yggpyfunc
     module procedure yggarg_scalar_yggptr
     ! module procedure yggarg_scalar_yggptr_arr
     ! module procedure yggarg_scalar_yggptr_map
     module procedure yggarg_realloc_1darray_unsigned1
     module procedure yggarg_realloc_1darray_unsigned2
     module procedure yggarg_realloc_1darray_unsigned4
     module procedure yggarg_realloc_1darray_unsigned8
     module procedure yggarg_realloc_1darray_c_long
     module procedure yggarg_realloc_1darray_integer
     module procedure yggarg_realloc_1darray_integer2
     module procedure yggarg_realloc_1darray_integer4
     module procedure yggarg_realloc_1darray_integer8
     module procedure yggarg_realloc_1darray_real
     module procedure yggarg_realloc_1darray_real4
     module procedure yggarg_realloc_1darray_real8
     module procedure yggarg_realloc_1darray_real16
     module procedure yggarg_realloc_1darray_complex
     module procedure yggarg_realloc_1darray_complex4
     module procedure yggarg_realloc_1darray_complex8
     module procedure yggarg_realloc_1darray_complex16
     module procedure yggarg_realloc_1darray_logical
     module procedure yggarg_realloc_1darray_logical1
     module procedure yggarg_realloc_1darray_logical2
     module procedure yggarg_realloc_1darray_logical4
     module procedure yggarg_realloc_1darray_logical8
     module procedure yggarg_realloc_1darray_character
     module procedure yggarg_1darray_unsigned1
     module procedure yggarg_1darray_unsigned2
     module procedure yggarg_1darray_unsigned4
     module procedure yggarg_1darray_unsigned8
     module procedure yggarg_1darray_integer2
     module procedure yggarg_1darray_integer4
     module procedure yggarg_1darray_integer8
     module procedure yggarg_1darray_real4
     module procedure yggarg_1darray_real8
#ifndef _WIN32
     module procedure yggarg_1darray_real16
#endif
     module procedure yggarg_1darray_complex4
     module procedure yggarg_1darray_complex8
#ifndef _WIN32
     module procedure yggarg_1darray_complex16
#endif
     module procedure yggarg_1darray_logical1
     module procedure yggarg_1darray_logical2
     module procedure yggarg_1darray_logical4
     module procedure yggarg_1darray_logical8
     module procedure yggarg_1darray_character
#ifndef _WIN32
     module procedure yggarg_1darray_unicode
#endif
     module procedure yggarg_1darray_yggchar_r
     module procedure yggarg_realloc_ndarray_unsigned1
     module procedure yggarg_realloc_ndarray_unsigned2
     module procedure yggarg_realloc_ndarray_unsigned4
     module procedure yggarg_realloc_ndarray_unsigned8
     module procedure yggarg_realloc_ndarray_c_long
     module procedure yggarg_realloc_ndarray_integer
     module procedure yggarg_realloc_ndarray_integer2
     module procedure yggarg_realloc_ndarray_integer4
     module procedure yggarg_realloc_ndarray_integer8
     module procedure yggarg_realloc_ndarray_real
     module procedure yggarg_realloc_ndarray_real4
     module procedure yggarg_realloc_ndarray_real8
     module procedure yggarg_realloc_ndarray_real16
     module procedure yggarg_realloc_ndarray_complex
     module procedure yggarg_realloc_ndarray_complex4
     module procedure yggarg_realloc_ndarray_complex8
     module procedure yggarg_realloc_ndarray_complex16
     module procedure yggarg_realloc_ndarray_logical
     module procedure yggarg_realloc_ndarray_logical1
     module procedure yggarg_realloc_ndarray_logical2
     module procedure yggarg_realloc_ndarray_logical4
     module procedure yggarg_realloc_ndarray_logical8
     module procedure yggarg_realloc_ndarray_character
     module procedure yggarg_2darray_unsigned1
     module procedure yggarg_2darray_unsigned2
     module procedure yggarg_2darray_unsigned4
     module procedure yggarg_2darray_unsigned8
     module procedure yggarg_2darray_integer2
     module procedure yggarg_2darray_integer4
     module procedure yggarg_2darray_integer8
     module procedure yggarg_2darray_real4
     module procedure yggarg_2darray_real8
#ifndef _WIN32
     module procedure yggarg_2darray_real16
#endif
     module procedure yggarg_2darray_complex4
     module procedure yggarg_2darray_complex8
#ifndef _WIN32
     module procedure yggarg_2darray_complex16
#endif
     module procedure yggarg_2darray_logical1
     module procedure yggarg_2darray_logical2
     module procedure yggarg_2darray_logical4
     module procedure yggarg_2darray_logical8
     module procedure yggarg_2darray_character
     module procedure yggarg_2darray_yggchar_r
  end interface yggarg
  interface generic_array_set
     module procedure generic_array_set_generic
     module procedure generic_array_set_boolean
     ! module procedure generic_array_set_integer
     module procedure generic_array_set_null
     ! module procedure generic_array_set_number
     module procedure generic_array_set_array
     module procedure generic_array_set_map
     module procedure generic_array_set_ply
     module procedure generic_array_set_obj
     module procedure generic_array_set_python_class
     ! module procedure generic_array_set_python_function
     module procedure generic_array_set_schema
     ! module procedure generic_array_set_any
     module procedure generic_array_set_integer2
     module procedure generic_array_set_integer4
     module procedure generic_array_set_integer8
     module procedure generic_array_set_unsigned1
     module procedure generic_array_set_unsigned2
     module procedure generic_array_set_unsigned4
     module procedure generic_array_set_unsigned8
     module procedure generic_array_set_real4
     module procedure generic_array_set_real8
     module procedure generic_array_set_complex4
     module procedure generic_array_set_complex8
     module procedure generic_array_set_bytes
     module procedure generic_array_set_unicode
     module procedure generic_array_set_1darray_integer2
     module procedure generic_array_set_1darray_integer4
     module procedure generic_array_set_1darray_integer8
     module procedure generic_array_set_1darray_unsigned1
     module procedure generic_array_set_1darray_unsigned2
     module procedure generic_array_set_1darray_unsigned4
     module procedure generic_array_set_1darray_unsigned8
     module procedure generic_array_set_1darray_real4
     module procedure generic_array_set_1darray_real8
     module procedure generic_array_set_1darray_complex4
     module procedure generic_array_set_1darray_complex8
     module procedure generic_array_set_1darray_bytes
     module procedure generic_array_set_1darray_unicode
     module procedure generic_array_set_ndarray_integer2
     module procedure generic_array_set_ndarray_integer4
     module procedure generic_array_set_ndarray_integer8
     module procedure generic_array_set_ndarray_unsigned1
     module procedure generic_array_set_ndarray_unsigned2
     module procedure generic_array_set_ndarray_unsigned4
     module procedure generic_array_set_ndarray_unsigned8
     module procedure generic_array_set_ndarray_real4
     module procedure generic_array_set_ndarray_real8
     module procedure generic_array_set_ndarray_complex4
     module procedure generic_array_set_ndarray_complex8
     module procedure generic_array_set_ndarray_character
     module procedure generic_array_set_ndarray_bytes
     module procedure generic_array_set_ndarray_unicode
  end interface generic_array_set
  interface generic_map_set
     module procedure generic_map_get_generic
     module procedure generic_map_set_boolean
     ! module procedure generic_map_set_integer
     module procedure generic_map_set_null
     ! module procedure generic_map_set_number
     module procedure generic_map_set_array
     module procedure generic_map_set_map
     module procedure generic_map_set_ply
     module procedure generic_map_set_obj
     module procedure generic_map_set_python_class
     ! module procedure generic_map_set_python_function
     module procedure generic_map_set_schema
     ! module procedure generic_map_set_any
     module procedure generic_map_set_integer2
     module procedure generic_map_set_integer4
     module procedure generic_map_set_integer8
     module procedure generic_map_set_unsigned1
     module procedure generic_map_set_unsigned2
     module procedure generic_map_set_unsigned4
     module procedure generic_map_set_unsigned8
     module procedure generic_map_set_real4
     module procedure generic_map_set_real8
     module procedure generic_map_set_complex4
     module procedure generic_map_set_complex8
     module procedure generic_map_set_bytes
     module procedure generic_map_set_unicode
     module procedure generic_map_set_1darray_integer2
     module procedure generic_map_set_1darray_integer4
     module procedure generic_map_set_1darray_integer8
     module procedure generic_map_set_1darray_unsigned1
     module procedure generic_map_set_1darray_unsigned2
     module procedure generic_map_set_1darray_unsigned4
     module procedure generic_map_set_1darray_unsigned8
     module procedure generic_map_set_1darray_real4
     module procedure generic_map_set_1darray_real8
     module procedure generic_map_set_1darray_complex4
     module procedure generic_map_set_1darray_complex8
     module procedure generic_map_set_1darray_bytes
     module procedure generic_map_set_1darray_unicode
     module procedure generic_map_set_ndarray_integer2
     module procedure generic_map_set_ndarray_integer4
     module procedure generic_map_set_ndarray_integer8
     module procedure generic_map_set_ndarray_unsigned1
     module procedure generic_map_set_ndarray_unsigned2
     module procedure generic_map_set_ndarray_unsigned4
     module procedure generic_map_set_ndarray_unsigned8
     module procedure generic_map_set_ndarray_real4
     module procedure generic_map_set_ndarray_real8
     module procedure generic_map_set_ndarray_complex4
     module procedure generic_map_set_ndarray_complex8
     module procedure generic_map_set_ndarray_character
     module procedure generic_map_set_ndarray_bytes
     module procedure generic_map_set_ndarray_unicode
  end interface generic_map_set
  interface generic_array_get
     module procedure generic_array_get_generic
     module procedure generic_array_get_boolean
     ! module procedure generic_array_get_integer
     module procedure generic_array_get_null
     ! module procedure generic_array_get_number
     module procedure generic_array_get_array
     module procedure generic_array_get_map
     module procedure generic_array_get_ply
     module procedure generic_array_get_obj
     module procedure generic_array_get_python_class
     ! module procedure generic_array_get_python_function
     module procedure generic_array_get_schema
     ! module procedure generic_array_get_any
     module procedure generic_array_get_integer2
     module procedure generic_array_get_integer4
     module procedure generic_array_get_integer8
     module procedure generic_array_get_unsigned1
     module procedure generic_array_get_unsigned2
     module procedure generic_array_get_unsigned4
     module procedure generic_array_get_unsigned8
     module procedure generic_array_get_real4
     module procedure generic_array_get_real8
     module procedure generic_array_get_complex4
     module procedure generic_array_get_complex8
     module procedure generic_array_get_bytes
     module procedure generic_array_get_unicode
     module procedure generic_array_get_1darray_integer2
     module procedure generic_array_get_1darray_integer4
     module procedure generic_array_get_1darray_integer8
     module procedure generic_array_get_1darray_unsigned1
     module procedure generic_array_get_1darray_unsigned2
     module procedure generic_array_get_1darray_unsigned4
     module procedure generic_array_get_1darray_unsigned8
     module procedure generic_array_get_1darray_real4
     module procedure generic_array_get_1darray_real8
     module procedure generic_array_get_1darray_complex4
     module procedure generic_array_get_1darray_complex8
     module procedure generic_array_get_1darray_bytes
     module procedure generic_array_get_1darray_unicode
     module procedure generic_array_get_ndarray_integer2
     module procedure generic_array_get_ndarray_integer4
     module procedure generic_array_get_ndarray_integer8
     module procedure generic_array_get_ndarray_unsigned1
     module procedure generic_array_get_ndarray_unsigned2
     module procedure generic_array_get_ndarray_unsigned4
     module procedure generic_array_get_ndarray_unsigned8
     module procedure generic_array_get_ndarray_real4
     module procedure generic_array_get_ndarray_real8
     module procedure generic_array_get_ndarray_complex4
     module procedure generic_array_get_ndarray_complex8
     module procedure generic_array_get_ndarray_character
     module procedure generic_array_get_ndarray_bytes
     module procedure generic_array_get_ndarray_unicode
  end interface generic_array_get
  interface generic_map_get
     module procedure generic_map_get_generic
     module procedure generic_map_get_boolean
     ! module procedure generic_map_get_integer
     module procedure generic_map_get_null
     ! module procedure generic_map_get_number
     module procedure generic_map_get_array
     module procedure generic_map_get_map
     module procedure generic_map_get_ply
     module procedure generic_map_get_obj
     module procedure generic_map_get_python_class
     ! module procedure generic_map_get_python_function
     module procedure generic_map_get_schema
     ! module procedure generic_map_get_any
     module procedure generic_map_get_integer2
     module procedure generic_map_get_integer4
     module procedure generic_map_get_integer8
     module procedure generic_map_get_unsigned1
     module procedure generic_map_get_unsigned2
     module procedure generic_map_get_unsigned4
     module procedure generic_map_get_unsigned8
     module procedure generic_map_get_real4
     module procedure generic_map_get_real8
     module procedure generic_map_get_complex4
     module procedure generic_map_get_complex8
     module procedure generic_map_get_bytes
     module procedure generic_map_get_unicode
     module procedure generic_map_get_1darray_integer2
     module procedure generic_map_get_1darray_integer4
     module procedure generic_map_get_1darray_integer8
     module procedure generic_map_get_1darray_unsigned1
     module procedure generic_map_get_1darray_unsigned2
     module procedure generic_map_get_1darray_unsigned4
     module procedure generic_map_get_1darray_unsigned8
     module procedure generic_map_get_1darray_real4
     module procedure generic_map_get_1darray_real8
     module procedure generic_map_get_1darray_complex4
     module procedure generic_map_get_1darray_complex8
     module procedure generic_map_get_1darray_bytes
     module procedure generic_map_get_1darray_unicode
     module procedure generic_map_get_ndarray_integer2
     module procedure generic_map_get_ndarray_integer4
     module procedure generic_map_get_ndarray_integer8
     module procedure generic_map_get_ndarray_unsigned1
     module procedure generic_map_get_ndarray_unsigned2
     module procedure generic_map_get_ndarray_unsigned4
     module procedure generic_map_get_ndarray_unsigned8
     module procedure generic_map_get_ndarray_real4
     module procedure generic_map_get_ndarray_real8
     module procedure generic_map_get_ndarray_complex4
     module procedure generic_map_get_ndarray_complex8
     module procedure generic_map_get_ndarray_character
     module procedure generic_map_get_ndarray_bytes
     module procedure generic_map_get_ndarray_unicode
  end interface generic_map_get
  interface yggassign
     module procedure yggassign_yggchar2character
     ! module procedure yggassign_character2yggchar
     module procedure yggassign_integer_1d_to_array
     module procedure yggassign_integer_1d_from_array
     module procedure yggassign_integer2_1d_to_array
     module procedure yggassign_integer2_1d_from_array
     module procedure yggassign_integer4_1d_to_array
     module procedure yggassign_integer4_1d_from_array
     module procedure yggassign_integer8_1d_to_array
     module procedure yggassign_integer8_1d_from_array
     ! module procedure yggassign_unsigned_1d_to_array
     ! module procedure yggassign_unsigned_1d_from_array
     module procedure yggassign_unsigned2_1d_to_array
     module procedure yggassign_unsigned2_1d_from_array
     module procedure yggassign_unsigned4_1d_to_array
     module procedure yggassign_unsigned4_1d_from_array
     module procedure yggassign_unsigned8_1d_to_array
     module procedure yggassign_unsigned8_1d_from_array
     module procedure yggassign_real_1d_to_array
     module procedure yggassign_real_1d_from_array
     module procedure yggassign_real4_1d_to_array
     module procedure yggassign_real4_1d_from_array
     module procedure yggassign_real8_1d_to_array
     module procedure yggassign_real8_1d_from_array
     module procedure yggassign_real16_1d_to_array
     module procedure yggassign_real16_1d_from_array
     module procedure yggassign_complex_1d_to_array
     module procedure yggassign_complex_1d_from_array
     module procedure yggassign_complex4_1d_to_array
     module procedure yggassign_complex4_1d_from_array
     module procedure yggassign_complex8_1d_to_array
     module procedure yggassign_complex8_1d_from_array
     module procedure yggassign_complex16_1d_to_array
     module procedure yggassign_complex16_1d_from_array
     module procedure yggassign_logical_1d_to_array
     module procedure yggassign_logical_1d_from_array
     module procedure yggassign_logical1_1d_to_array
     module procedure yggassign_logical1_1d_from_array
     module procedure yggassign_logical2_1d_to_array
     module procedure yggassign_logical2_1d_from_array
     module procedure yggassign_logical4_1d_to_array
     module procedure yggassign_logical4_1d_from_array
     module procedure yggassign_logical8_1d_to_array
     module procedure yggassign_logical8_1d_from_array
     ! TODO: ND array
  end interface yggassign
  interface yggarr
     module procedure ygggeneric2yggarr
  end interface yggarr
  interface yggmap
     module procedure ygggeneric2yggmap
  end interface yggmap
  interface yggschema
     module procedure ygggeneric2yggschema
  end interface yggschema
  interface yggpyinst
     module procedure ygggeneric2yggpyinst
  end interface yggpyinst
  interface ygggeneric
     module procedure yggarr2ygggeneric
     module procedure yggmap2ygggeneric
     module procedure yggschema2ygggeneric
     module procedure yggpyinst2ygggeneric
  end interface ygggeneric
  interface yggpyfunc
     module procedure yggpython2yggpyfunc
  end interface yggpyfunc
  interface yggpython
     module procedure yggpython2yggpython
     module procedure yggpyfunc2yggpython
  end interface yggpython
  interface ygg_send_var
     module procedure ygg_send_var_sing
     module procedure ygg_send_var_mult
  end interface ygg_send_var
  interface ygg_recv_var
     module procedure ygg_recv_var_sing
     module procedure ygg_recv_var_mult
  end interface ygg_recv_var
  interface ygg_recv_var_realloc
     module procedure ygg_recv_var_realloc_sing
     module procedure ygg_recv_var_realloc_mult
  end interface ygg_recv_var_realloc
  interface ygg_rpc_call
     module procedure ygg_rpc_call_1v1
     module procedure ygg_rpc_call_1vm
     module procedure ygg_rpc_call_mv1
     module procedure ygg_rpc_call_mult
  end interface ygg_rpc_call
  interface ygg_rpc_call_realloc
     module procedure ygg_rpc_call_realloc_1v1
     module procedure ygg_rpc_call_realloc_1vm
     module procedure ygg_rpc_call_realloc_mv1
     module procedure ygg_rpc_call_realloc_mult
  end interface ygg_rpc_call_realloc
  interface ygguint
     module procedure init_ygguint1
     module procedure init_ygguint2
     module procedure init_ygguint4
     module procedure init_ygguint8
  end interface ygguint
  type :: yggcomm
     type(c_ptr) :: comm
  end type yggcomm
  type :: yggdtype
     type(c_ptr) :: ptr
  end type yggdtype
  type :: yggchar_r
     character, dimension(:), pointer :: x => null()
  end type yggchar_r
  type :: c_long_1d
     integer(kind=c_long), dimension(:), pointer :: x => null()
  end type c_long_1d
  type :: unsigned1_1d
     integer(kind=1), dimension(:), pointer :: x => null()
  end type unsigned1_1d
  type :: unsigned2_1d
     integer(kind=2), dimension(:), pointer :: x => null()
  end type unsigned2_1d
  type :: unsigned4_1d
     integer(kind=4), dimension(:), pointer :: x => null()
  end type unsigned4_1d
  type :: unsigned8_1d
     integer(kind=8), dimension(:), pointer :: x => null()
  end type unsigned8_1d
  type :: integer_1d
     integer, dimension(:), pointer :: x => null()
  end type integer_1d
  type :: integer2_1d
     integer(kind=2), dimension(:), pointer :: x => null()
  end type integer2_1d
  type :: integer4_1d
     integer(kind=4), dimension(:), pointer :: x => null()
  end type integer4_1d
  type :: integer8_1d
     integer(kind=8), dimension(:), pointer :: x => null()
  end type integer8_1d
  type :: real_1d
     real, dimension(:), pointer :: x => null()
  end type real_1d
  type :: real4_1d
     real(kind=4), dimension(:), pointer :: x => null()
  end type real4_1d
  type :: real8_1d
     real(kind=8), dimension(:), pointer :: x => null()
  end type real8_1d
#ifdef _WIN32
  type :: real16_1d
     real(kind=8), dimension(:), pointer :: x => null()
  end type real16_1d
#else
  type :: real16_1d
     real(kind=16), dimension(:), pointer :: x => null()
  end type real16_1d
#endif
  type :: complex_1d
     complex, dimension(:), pointer :: x => null()
  end type complex_1d
  type :: complex4_1d
     complex(kind=4), dimension(:), pointer :: x => null()
  end type complex4_1d
  type :: complex8_1d
     complex(kind=8), dimension(:), pointer :: x => null()
  end type complex8_1d
#ifdef _WIN32
  type :: complex16_1d
     complex(kind=8), dimension(:), pointer :: x => null()
  end type complex16_1d
#else
  type :: complex16_1d
     complex(kind=16), dimension(:), pointer :: x => null()
  end type complex16_1d
#endif
  type :: logical_1d
     logical, dimension(:), pointer :: x => null()
  end type logical_1d
  type :: logical1_1d
     logical(kind=1), dimension(:), pointer :: x => null()
  end type logical1_1d
  type :: logical2_1d
     logical(kind=2), dimension(:), pointer :: x => null()
  end type logical2_1d
  type :: logical4_1d
     logical(kind=4), dimension(:), pointer :: x => null()
  end type logical4_1d
  type :: logical8_1d
     logical(kind=8), dimension(:), pointer :: x => null()
  end type logical8_1d
  type :: character_1d
     type(yggchar_r), dimension(:), pointer :: x => null()
  end type character_1d
  type :: unsigned1_nd
     integer(kind=1), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type unsigned1_nd
  type :: unsigned2_nd
     integer(kind=2), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type unsigned2_nd
  type :: unsigned4_nd
     integer(kind=4), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type unsigned4_nd
  type :: unsigned8_nd
     integer(kind=8), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type unsigned8_nd
  type :: c_long_nd
     integer(kind=c_long), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type c_long_nd
  type :: integer_nd
     integer, dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type integer_nd
  type :: integer2_nd
     integer(kind=2), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type integer2_nd
  type :: integer4_nd
     integer(kind=4), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type integer4_nd
  type :: integer8_nd
     integer(kind=8), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type integer8_nd
  type :: real_nd
     real, dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real_nd
  type :: real4_nd
     real(kind=4), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real4_nd
  type :: real8_nd
     real(kind=8), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real8_nd
#ifdef _WIN32
  type :: real16_nd
     real(kind=8), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real16_nd
#else
  type :: real16_nd
     real(kind=16), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real16_nd
#endif
  type :: complex_nd
     complex, dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex_nd
  type :: complex4_nd
     complex(kind=4), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex4_nd
  type :: complex8_nd
     complex(kind=8), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex8_nd
#ifdef _WIN32
  type :: complex16_nd
     complex(kind=8), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex16_nd
#else
  type :: complex16_nd
     complex(kind=16), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex16_nd
#endif
  type :: logical_nd
     logical, dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical_nd
  type :: logical1_nd
     logical(kind=1), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical1_nd
  type :: logical2_nd
     logical(kind=2), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical2_nd
  type :: logical4_nd
     logical(kind=4), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical4_nd
  type :: logical8_nd
     logical(kind=8), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical8_nd
  type :: bytes_nd
     character(len=:), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type bytes_nd
  type :: unicode_nd
     character(kind=ucs4, len=:), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type unicode_nd
  type :: character_nd
     type(yggchar_r), dimension(:), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type character_nd
  type :: unsigned1_2d
     integer(kind=1), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type unsigned1_2d
  type :: unsigned2_2d
     integer(kind=2), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type unsigned2_2d
  type :: unsigned4_2d
     integer(kind=4), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type unsigned4_2d
  type :: unsigned8_2d
     integer(kind=8), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type unsigned8_2d
  type :: c_long_2d
     integer(kind=c_long), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type c_long_2d
  type :: integer_2d
     integer, dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type integer_2d
  type :: integer2_2d
     integer(kind=2), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type integer2_2d
  type :: integer4_2d
     integer(kind=4), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type integer4_2d
  type :: integer8_2d
     integer(kind=8), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type integer8_2d
  type :: real_2d
     real, dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real_2d
  type :: real4_2d
     real(kind=4), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real4_2d
  type :: real8_2d
     real(kind=8), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real8_2d
#ifdef _WIN32
  type :: real16_2d
     real(kind=8), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real16_2d
#else
  type :: real16_2d
     real(kind=16), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type real16_2d
#endif
  type :: complex_2d
     complex, dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex_2d
  type :: complex4_2d
     complex(kind=4), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex4_2d
  type :: complex8_2d
     complex(kind=8), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex8_2d
#ifdef _WIN32
  type :: complex16_2d
     complex(kind=8), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex16_2d
#else
  type :: complex16_2d
     complex(kind=16), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type complex16_2d
#endif
  type :: logical_2d
     logical, dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical_2d
  type :: logical1_2d
     logical(kind=1), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical1_2d
  type :: logical2_2d
     logical(kind=2), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical2_2d
  type :: logical4_2d
     logical(kind=4), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical4_2d
  type :: logical8_2d
     logical(kind=8), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type logical8_2d
  type :: character_2d
     type(yggchar_r), dimension(:, :), pointer :: x => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape => null()
  end type character_2d
  type :: yggptr
     character(len=15) :: type = "none"
     logical :: ndarray = .false.
     logical :: array = .false.
     logical :: alloc = .false.
     integer(kind=8) :: len = 0
     integer(kind=8) :: prec = 0
     integer(kind=8) :: ndim = 0
     integer(kind=8) :: nbytes = 0
     integer(kind=8), dimension(:), pointer :: shape => null()
     type(c_ptr) :: ptr = c_null_ptr
     class(*), pointer :: item => null()
     class(*), dimension(:), pointer :: item_array => null()
     class(*), dimension(:, :), pointer :: item_array_2d => null()
     class(*), dimension(:, :, :), pointer :: item_array_3d => null()
     character, dimension(:), pointer :: data_character_unit => null()
     character(kind=ucs4), dimension(:), &
          pointer :: data_unicode_unit => null()
     integer(kind=c_size_t), pointer :: len_c => null()
     integer(kind=c_size_t), pointer :: prec_c => null()
     integer(kind=c_size_t), pointer :: ndim_c => null()
     integer(kind=c_size_t), dimension(:), pointer :: shape_c => null()
     type(c_ptr) :: len_ptr = c_null_ptr
     type(c_ptr) :: prec_ptr = c_null_ptr
     type(c_ptr) :: ndim_ptr = c_null_ptr
     type(c_ptr) :: shape_ptr = c_null_ptr
  end type yggptr
  type :: yggptr_arr
     type(yggptr), dimension(:), pointer :: vals => null()
  end type yggptr_arr
  type :: yggptr_map
     character(len=20), dimension(:), pointer :: keys => null()
     type(yggptr), dimension(:), pointer :: vals => null()
  end type yggptr_map
  type, bind(c) :: ygggeneric
     character(kind=c_char) :: prefix
     type(c_ptr) :: obj
  end type ygggeneric
  type :: yggnull
     type(c_ptr) :: ptr = c_null_ptr
   ! contains
   !   procedure :: write_null
   !   generic :: write(formatted) => write_null
  end type yggnull
  type, bind(c) :: yggarr
     character(kind=c_char) :: prefix
     type(c_ptr) :: obj
  end type yggarr
  type, bind(c) :: yggmap
     character(kind=c_char) :: prefix
     type(c_ptr) :: obj
  end type yggmap
  type, bind(c) :: yggschema
     character(kind=c_char) :: prefix
     type(c_ptr) :: obj
  end type yggschema
  type, bind(c) :: yggpyinst
     character(kind=c_char) :: prefix
     type(c_ptr) :: obj
  end type yggpyinst
  type, bind(c) :: yggpyfunc
     character(kind=c_char), dimension(1000) :: name = c_null_char
     type(c_ptr) :: args = c_null_ptr
     type(c_ptr) :: kwargs = c_null_ptr
     type(c_ptr) :: obj = c_null_ptr
  end type yggpyfunc
  type, bind(c) :: yggpython
     character(kind=c_char), dimension(1000) :: name = c_null_char
     type(c_ptr) :: args = c_null_ptr
     type(c_ptr) :: kwargs = c_null_ptr
     type(c_ptr) :: obj = c_null_ptr
  end type yggpython
  type, bind(c) :: yggply
     character(kind=c_char), dimension(100) :: material
     integer(kind=c_int) :: nvert
     integer(kind=c_int) :: nface
     integer(kind=c_int) :: nedge
     type(c_ptr) :: c_vertices
     type(c_ptr) :: c_faces
     type(c_ptr) :: c_edges
     type(c_ptr) :: c_vertex_colors
     type(c_ptr) :: c_edge_colors
     type(c_ptr) :: c_nvert_in_face
  end type yggply
  type, bind(c) :: yggobj
     character(kind=c_char), dimension(100) :: material
     integer(kind=c_int) :: nvert
     integer(kind=c_int) :: ntexc
     integer(kind=c_int) :: nnorm
     integer(kind=c_int) :: nparam
     integer(kind=c_int) :: npoint
     integer(kind=c_int) :: nline
     integer(kind=c_int) :: nface
     integer(kind=c_int) :: ncurve
     integer(kind=c_int) :: ncurve2
     integer(kind=c_int) :: nsurf
     type(c_ptr) :: c_vertices
     type(c_ptr) :: c_vertex_colors
     type(c_ptr) :: c_texcoords
     type(c_ptr) :: c_normals
     type(c_ptr) :: c_params
     type(c_ptr) :: c_points
     type(c_ptr) :: c_nvert_in_point
     type(c_ptr) :: c_lines
     type(c_ptr) :: c_nvert_in_line
     type(c_ptr) :: c_line_texcoords
     type(c_ptr) :: c_faces
     type(c_ptr) :: c_nvert_in_face
     type(c_ptr) :: c_face_texcoords
     type(c_ptr) :: c_face_normals
     type(c_ptr) :: c_curves
     type(c_ptr) :: c_curve_params
     type(c_ptr) :: c_nvert_in_curve
     type(c_ptr) :: c_curves2
     type(c_ptr) :: c_nparam_in_curve2
     type(c_ptr) :: c_surfaces
     type(c_ptr) :: c_nvert_in_surface
     type(c_ptr) :: c_surface_params_u
     type(c_ptr) :: c_surface_params_v
     type(c_ptr) :: c_surface_texcoords
     type(c_ptr) :: c_surface_normals
  end type yggobj
  type ygguint1
     integer(kind=1) :: x
  end type ygguint1
  type ygguint2
     integer(kind=2) :: x
  end type ygguint2
  type ygguint4
     integer(kind=4) :: x
  end type ygguint4
  type ygguint8
     integer(kind=8) :: x
  end type ygguint8

  interface assignment(=)
     module procedure ygguint1_assign
     module procedure ygguint2_assign
     module procedure ygguint4_assign
     module procedure ygguint8_assign
  end interface assignment(=)

  public :: yggarg, yggchar_r, yggcomm, ygggeneric, &
       yggptr, yggnull, yggarr, yggmap, &
       yggschema, yggpython, yggply, yggobj, yggpyinst, yggpyfunc, &
       LINE_SIZE_MAX

  include "YggInterface_cdef.f90"

#define WITH_GLOBAL_SCOPE(COMM) call set_global_comm(); COMM; call unset_global_comm()

contains

  ! include "YggInterface_copy.f90"
  include "YggInterface_realloc.f90"
  include "YggInterface_c2f.f90"
  include "YggInterface_arg.f90"
  include "YggInterface_conv.f90"
  include "YggInterface_assign.f90"
  include "YggInterface_array.f90"
  include "YggInterface_map.f90"

  subroutine ygguint1_assign(self, other)
    type(ygguint1), intent(inout) :: self
    integer, intent(in) :: other
    self%x = int(other, kind=1)
  end subroutine ygguint1_assign
  subroutine ygguint2_assign(self, other)
    type(ygguint2), intent(inout) :: self
    integer, intent(in) :: other
    self%x = int(other, kind=2)
  end subroutine ygguint2_assign
  subroutine ygguint4_assign(self, other)
    type(ygguint4), intent(inout) :: self
    integer, intent(in) :: other
    self%x = int(other, kind=4)
  end subroutine ygguint4_assign
  subroutine ygguint8_assign(self, other)
    type(ygguint8), intent(inout) :: self
    integer, intent(in) :: other
    self%x = int(other, kind=8)
  end subroutine ygguint8_assign


#ifndef _WIN32
  function yggarg_scalar_real16(x) result (y)
    type(yggptr) :: y
    real(kind=16), target :: x
    real(kind=16), pointer :: xp
    y = yggarg_scalar_init(x)
    xp => x
    y%type = "real"
    y%ptr = c_loc(xp)
    y%nbytes = 16
  end function yggarg_scalar_real16
  function yggarg_scalar_complex16(x) result (y)
    type(yggptr) :: y
    complex(kind=16), target :: x
    complex(kind=16), pointer :: xp
    y = yggarg_scalar_init(x)
    xp => x
    y%type = "complex"
    y%ptr = c_loc(xp)
    y%nbytes = 16 * 2
  end function yggarg_scalar_complex16
  function yggarg_1darray_real16(x, x_shape) result (y)
    real(kind=16), dimension(:), target :: x
    real(kind=16), dimension(:), pointer :: xp
    integer, dimension(:), optional :: x_shape
    type(yggptr) :: y
    xp => x
    if (present(x_shape)) then
       y = yggarg_ndarray_init(x, x_shape)
    else
       y = yggarg_ndarray_init(x)
    end if
    y%type = "real"
    y%ptr = c_loc(xp(1))
  end function yggarg_1darray_real16
  function yggarg_1darray_complex16(x, x_shape) result (y)
    complex(kind=16), dimension(:), target :: x
    complex(kind=16), dimension(:), pointer :: xp
    integer, dimension(:), optional :: x_shape
    type(yggptr) :: y
    xp => x
    if (present(x_shape)) then
       y = yggarg_ndarray_init(x, x_shape)
    else
       y = yggarg_ndarray_init(x)
    end if
    y%type = "complex"
    y%ptr = c_loc(xp(1))
  end function yggarg_1darray_complex16
  function yggarg_2darray_real16(x) result (y)
    real(kind=16), dimension(:, :), target :: x
    real(kind=16), dimension(:), pointer :: xp
    type(yggptr) :: y
    allocate(xp(size(x)))
    xp = reshape(x, [size(x)])
    y = yggarg(xp, shape(x))
    call yggarg_2darray_init(y, x)
  end function yggarg_2darray_real16
  function yggarg_2darray_complex16(x) result (y)
    complex(kind=16), dimension(:, :), target :: x
    complex(kind=16), dimension(:), pointer :: xp
    type(yggptr) :: y
    allocate(xp(size(x)))
    xp = reshape(x, [size(x)])
    y = yggarg(xp, shape(x))
    call yggarg_2darray_init(y, x)
  end function yggarg_2darray_complex16
#endif
  
  ! Utilities
  function init_ygguint1(x) result(y)
    integer(kind=1) :: x
    type(ygguint1) :: y
    y%x = x
    if (y%x.lt.0) stop "Unsigned int cannot be less than 0."
  end function init_ygguint1
  function init_ygguint2(x) result(y)
    integer(kind=2) :: x
    type(ygguint2) :: y
    y%x = x
    if (y%x.lt.0) stop "Unsigned int cannot be less than 0."
  end function init_ygguint2
  function init_ygguint4(x) result(y)
    integer(kind=4) :: x
    type(ygguint4) :: y
    y%x = x
    if (y%x.lt.0) stop "Unsigned int cannot be less than 0."
  end function init_ygguint4
  function init_ygguint8(x) result(y)
    integer(kind=8) :: x
    type(ygguint8) :: y
    y%x = x
    if (y%x.lt.0) stop "Unsigned int cannot be less than 0."
  end function init_ygguint8
  subroutine display_null(x)
    class(yggnull), intent(in) :: x
    write (*, '("NULL")')
  end subroutine display_null
  ! subroutine write_null(dtv, unit, iotype, v_list, iostat, iomsg)
  !   ! Argument names here from the std, but you can name them differently.
  !   class(yggnull), intent(in) :: dtv   ! Object to write.
  !   integer, intent(in) :: unit         ! Internal unit to write to.
  !   character(*), intent(in) :: iotype  ! LISTDIRECTED or DTxxx
  !   integer, intent(in) :: v_list(:)    ! parameters from fmt spec.
  !   integer, intent(out) :: iostat      ! non zero on error, etc.
  !   character(*), intent(inout) :: iomsg  ! define if iostat non zero.
  !   write (unit, '("NULL")', IOSTAT=iostat, IOMSG=iomsg)
  ! end subroutine write_null
  subroutine fix_format_str(x)
    implicit none
    character(len=*) :: x
    integer :: i, length
    length = len(x)
    i = index(x, "\t")
    do while (i.ne.0)
       x(i:i) = char(9)
       x((i+1):length) = x((i+2):length)
       length = len(x)
       i = index(x, "\t")
    end do
    i = index(x, "\n")
    do while (i.ne.0)
       x(i:i) = NEW_LINE('c')
       x((i+1):length) = x((i+2):length)
       length = len(x)
       i = index(x, "\n")
    end do
  end subroutine fix_format_str

  ! YggInterface

  ! Utilities
  function ygg_init() result(out)
    implicit none
    logical :: out
    integer(kind=c_int) :: c_out
    c_out = ygg_init_c()
    if (c_out.eq.0) then
       out = .true.
    else
       out = .false.
    end if
  end function ygg_init
  subroutine ygglog_info(fmt)
    implicit none
    character(len=*), intent(in) :: fmt
    character(len=len_trim(fmt)+1) :: c_fmt
    c_fmt = trim(fmt)//c_null_char
    call ygglog_info_c(c_fmt)
  end subroutine ygglog_info
  subroutine ygglog_debug(fmt)
    implicit none
    character(len=*), intent(in) :: fmt
    character(len=len_trim(fmt)+1) :: c_fmt
    c_fmt = trim(fmt)//c_null_char
    call ygglog_debug_c(c_fmt)
  end subroutine ygglog_debug
  subroutine ygglog_error(fmt)
    implicit none
    character(len=*), intent(in) :: fmt
    character(len=len_trim(fmt)+1) :: c_fmt
    c_fmt = trim(fmt)//c_null_char
    call ygglog_error_c(c_fmt)
  end subroutine ygglog_error

  ! Methods for initializing channels
  function is_comm_format_array_type(x, args) result(out)
    implicit none
    type(yggcomm), intent(in) :: x
    type(yggptr) :: args(:)
    logical :: out
    integer(c_int) :: c_out
    integer :: i
    c_out = is_comm_format_array_type_c(x%comm)
    if (c_out.eq.0) then
       out = .false.
    else if (c_out.eq.1) then
       out = .true.
    else if (size(args).eq.1) then
       out = .false.
    else
       out = .true.
       do i = 2, size(args)
          if (.not.args(i)%array) then
             out = .false.
             exit
          end if
       end do
       if ((out).and.(.not.((args(1)%array).or.(is_size_t(args(1)))))) then
          out = .false.
       end if
       ! stop "is_comm_format_array_type: Error checking type."
    end if
  end function is_comm_format_array_type
  
  function ygg_output(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_output_c(c_name)
  end function ygg_output
  
  function ygg_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_input_c(c_name)
  end function ygg_input

  function ygg_output_type(name, datatype) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    type(yggdtype) :: datatype
    character(len=len_trim(name)+1) :: c_name
    type(c_ptr) :: c_datatype
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    c_datatype = datatype%ptr
    channel%comm = ygg_output_type_c(c_name, c_datatype)
  end function ygg_output_type
  
  function ygg_input_type(name, datatype) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    type(yggdtype) :: datatype
    character(len=len_trim(name)+1) :: c_name
    type(c_ptr) :: c_datatype
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    c_datatype = datatype%ptr
    channel%comm = ygg_input_type_c(c_name, c_datatype)
  end function ygg_input_type
  
  function ygg_output_fmt(name, fmt) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=*), intent(in) :: fmt
    character(len=len_trim(name)+1) :: c_name
    character(len=len_trim(fmt)+1) :: c_fmt
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    c_fmt = trim(fmt)//c_null_char
    call fix_format_str(c_fmt)
    channel%comm = ygg_output_fmt_c(c_name, c_fmt)
  end function ygg_output_fmt
  
  function ygg_input_fmt(name, fmt) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=*), intent(in) :: fmt
    character(len=len_trim(name)+1) :: c_name
    character(len=len_trim(fmt)+1) :: c_fmt
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    c_fmt = trim(fmt)//c_null_char
    call fix_format_str(c_fmt)
    channel%comm = ygg_input_fmt_c(c_name, c_fmt)
  end function ygg_input_fmt
  
  function ygg_ascii_file_output(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_ascii_file_output_c(c_name)
  end function ygg_ascii_file_output
  
  function ygg_ascii_file_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_ascii_file_input_c(c_name)
  end function ygg_ascii_file_input
  
  function ygg_ascii_table_output(name, format_str) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=*), intent(in) :: format_str
    character(len=len_trim(name)+1) :: c_name
    character(len=len_trim(format_str)+1) :: c_format_str
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    c_format_str = trim(format_str)//c_null_char
    call fix_format_str(c_format_str)
    channel%comm = ygg_ascii_table_output_c(c_name, c_format_str)
  end function ygg_ascii_table_output
  
  function ygg_ascii_table_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_ascii_table_input_c(c_name)
  end function ygg_ascii_table_input
  
  function ygg_ascii_array_output(name, format_str) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=*), intent(in) :: format_str
    character(len=len_trim(name)+1) :: c_name
    character(len=len_trim(format_str)+1) :: c_format_str
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    c_format_str = trim(format_str)//c_null_char
    call fix_format_str(c_format_str)
    channel%comm = ygg_ascii_array_output_c(c_name, c_format_str)
  end function ygg_ascii_array_output
  
  function ygg_ascii_array_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_ascii_array_input_c(c_name)
  end function ygg_ascii_array_input
  
  function ygg_ply_output(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_ply_output_c(c_name)
  end function ygg_ply_output
  
  function ygg_ply_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_ply_input_c(c_name)
  end function ygg_ply_input
  
  function ygg_obj_output(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_obj_output_c(c_name)
  end function ygg_obj_output
  
  function ygg_obj_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_obj_input_c(c_name)
  end function ygg_obj_input

  function ygg_generic_output(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_generic_output_c(c_name)
  end function ygg_generic_output
  
  function ygg_generic_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_generic_input_c(c_name)
  end function ygg_generic_input

  function ygg_any_output(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_any_output_c(c_name)
  end function ygg_any_output
  
  function ygg_any_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_any_input_c(c_name)
  end function ygg_any_input

  function ygg_json_array_output(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_json_array_output_c(c_name)
  end function ygg_json_array_output
  
  function ygg_json_array_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_json_array_input_c(c_name)
  end function ygg_json_array_input

  function ygg_json_object_output(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_json_object_output_c(c_name)
  end function ygg_json_object_output
  
  function ygg_json_object_input(name) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    channel%comm = ygg_json_object_input_c(c_name)
  end function ygg_json_object_input

  function ygg_rpc_client(name, out_fmt_in, in_fmt_in) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=*), intent(in), optional :: out_fmt_in
    character(len=*), intent(in), optional :: in_fmt_in
    character(len=:), allocatable :: out_fmt
    character(len=:), allocatable :: in_fmt
    character(len=len_trim(name)+1) :: c_name
    character(len=:), allocatable :: c_out_fmt
    character(len=:), allocatable :: c_in_fmt
    type(yggcomm) :: channel
    if (present(out_fmt_in)) then
       out_fmt = out_fmt_in
    else
       out_fmt = "%s"
    end if
    if (present(in_fmt_in)) then
       in_fmt = in_fmt_in
    else
       in_fmt = "%s"
    end if
    allocate(character(len=len_trim(in_fmt)+1) :: c_in_fmt)
    allocate(character(len=len_trim(out_fmt)+1) :: c_out_fmt)
    c_name = trim(name)//c_null_char
    c_out_fmt = trim(out_fmt)//c_null_char
    c_in_fmt = trim(in_fmt)//c_null_char
    call fix_format_str(c_out_fmt)
    call fix_format_str(c_in_fmt)
    channel%comm = ygg_rpc_client_c(c_name, c_out_fmt, c_in_fmt)
  end function ygg_rpc_client

  function ygg_rpc_server(name, in_fmt_in, out_fmt_in) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=*), intent(in), optional :: in_fmt_in
    character(len=*), intent(in), optional :: out_fmt_in
    character(len=:), allocatable :: in_fmt
    character(len=:), allocatable :: out_fmt
    character(len=len_trim(name)+1) :: c_name
    character(len=:), allocatable :: c_in_fmt
    character(len=:), allocatable :: c_out_fmt
    type(yggcomm) :: channel
    if (present(in_fmt_in)) then
       in_fmt = in_fmt_in
    else
       in_fmt = "%s"
    end if
    if (present(out_fmt_in)) then
       out_fmt = out_fmt_in
    else
       out_fmt = "%s"
    end if
    allocate(character(len=len_trim(in_fmt)+1) :: c_in_fmt)
    allocate(character(len=len_trim(out_fmt)+1) :: c_out_fmt)
    c_name = trim(name)//c_null_char
    c_in_fmt = trim(in_fmt)//c_null_char
    c_out_fmt = trim(out_fmt)//c_null_char
    call fix_format_str(c_in_fmt)
    call fix_format_str(c_out_fmt)
    channel%comm = ygg_rpc_server_c(c_name, c_in_fmt, c_out_fmt)
  end function ygg_rpc_server

  function ygg_rpc_client_type(name, out_type_in, in_type_in) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    type(yggdtype), optional :: out_type_in
    type(yggdtype), optional :: in_type_in
    type(c_ptr) :: c_out_type
    type(c_ptr) :: c_in_type
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    if (present(out_type_in)) then
       c_out_type = out_type_in%ptr
    else
       c_out_type = c_null_ptr
    end if
    if (present(in_type_in)) then
       c_in_type = in_type_in%ptr
    else
       c_in_type = c_null_ptr
    end if
    c_name = trim(name)//c_null_char
    channel%comm = ygg_rpc_client_type_c(c_name, c_out_type, c_in_type)
  end function ygg_rpc_client_type

  function ygg_rpc_server_type(name, in_type_in, out_type_in) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    type(yggdtype), optional :: in_type_in
    type(yggdtype), optional :: out_type_in
    type(c_ptr) :: c_in_type
    type(c_ptr) :: c_out_type
    character(len=len_trim(name)+1) :: c_name
    type(yggcomm) :: channel
    if (present(in_type_in)) then
       c_in_type = in_type_in%ptr
    else
       c_in_type = c_null_ptr
    end if
    if (present(out_type_in)) then
       c_out_type = out_type_in%ptr
    else
       c_out_type = c_null_ptr
    end if
    c_name = trim(name)//c_null_char
    channel%comm = ygg_rpc_server_type_c(c_name, c_in_type, c_out_type)
  end function ygg_rpc_server_type

  function ygg_timesync(name, units) result(channel)
    implicit none
    character(len=*), intent(in) :: name
    character(len=*), intent(in) :: units
    character(len=len_trim(name)+1) :: c_name
    character(len=len_trim(units)+1) :: c_units
    type(yggcomm) :: channel
    c_name = trim(name)//c_null_char
    c_units = trim(units)//c_null_char
    channel%comm = ygg_timesync_c(c_name, c_units)
  end function ygg_timesync

  ! Method for constructing data types
  function is_dtype_format_array(type_struct) result(out)
    implicit none
    type(yggdtype) :: type_struct
    logical :: out
    integer(kind=c_int) :: c_out
    c_out = is_dtype_format_array_c(type_struct%ptr)
    if (c_out.eq.0) then
       out = .false.
    else if (c_out.eq.1) then
       out = .true.
    else
       stop "is_dtype_format_array: Error checking data type"
    end if
  end function is_dtype_format_array
  
  function create_dtype_empty(use_generic) result(out)
    implicit none
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    out%ptr = create_dtype_empty_c(logical(use_generic, kind=1))
  end function create_dtype_empty

  function create_dtype_python(pyobj, use_generic) result(out)
    implicit none
    type(c_ptr) :: pyobj
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    out%ptr = create_dtype_python_c(pyobj, logical(use_generic, kind=1))
  end function create_dtype_python

  function create_dtype_direct(use_generic) result(out)
    implicit none
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    out%ptr = create_dtype_direct_c(logical(use_generic, kind=1))
  end function create_dtype_direct

  function create_dtype_default(typename, use_generic) result(out)
    implicit none
    character(len=*), intent(in) :: typename
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    character(len=len_trim(typename)+1) :: c_typename
    c_typename = trim(typename)//c_null_char
    out%ptr = create_dtype_default_c(c_typename, logical(use_generic, kind=1))
  end function create_dtype_default

  function create_dtype_scalar(subtype, precision, units, &
       use_generic) result(out)
    implicit none
    character(len=*), intent(in) :: subtype
    integer, intent(in) :: precision
    character(len=*), intent(in) :: units
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    character(len=len_trim(subtype)+1) :: c_subtype
    integer(kind=c_size_t) :: c_precision
    character(len=len_trim(units)+1) :: c_units
    c_subtype = trim(subtype)//c_null_char
    c_precision = precision
    c_units = trim(units)//c_null_char
    out%ptr = create_dtype_scalar_c(c_subtype, c_precision, c_units, &
         logical(use_generic, kind=1))
  end function create_dtype_scalar

  function create_dtype_1darray(subtype, precision, length, &
       units, use_generic) result(out)
    implicit none
    character(len=*), intent(in) :: subtype
    integer, intent(in) :: precision
    integer, intent(in) :: length
    character(len=*), intent(in) :: units
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    character(len=len_trim(subtype)+1) :: c_subtype
    integer(kind=c_size_t) :: c_precision
    integer(kind=c_size_t) :: c_length
    character(len=len_trim(units)+1) :: c_units
    c_subtype = trim(subtype)//c_null_char
    c_precision = precision
    c_length = length
    c_units = trim(units)//c_null_char
    out%ptr = create_dtype_1darray_c(c_subtype, c_precision, c_length, &
         c_units, logical(use_generic, kind=1))
  end function create_dtype_1darray

  function create_dtype_ndarray(subtype, precision, ndim, &
       shape, units, use_generic) result(out)
    implicit none
    character(len=*), intent(in) :: subtype
    integer, intent(in) :: precision
    integer, intent(in) :: ndim
    integer(kind=c_size_t), dimension(:), target, intent(in) :: shape
    character(len=*), intent(in) :: units
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    integer(kind=c_size_t), dimension(:), pointer :: pshape
    character(len=len_trim(subtype)+1) :: c_subtype
    integer(kind=c_size_t) :: c_precision
    integer(kind=c_size_t) :: c_ndim
    type(c_ptr) :: c_shape
    character(len=len_trim(units)+1) :: c_units
    pshape => shape
    c_subtype = trim(subtype)//c_null_char
    c_precision = precision
    c_ndim = ndim
    c_shape = c_loc(shape(1))
    c_units = trim(units)//c_null_char
    out%ptr = create_dtype_ndarray_c(c_subtype, c_precision, c_ndim, &
         c_shape, c_units, logical(use_generic, kind=1))
  end function create_dtype_ndarray

  function create_dtype_json_array(nitems, items, use_generic) &
       result(out)
    implicit none
    integer, intent(in) :: nitems
    type(yggdtype), dimension(:), intent(in) :: items
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    integer(kind=c_size_t) :: c_nitems
    type(c_ptr), target :: c_items(size(items))
    integer :: i
    c_nitems = nitems
    do i = 1, size(items)
       c_items(i) = items(i)%ptr
    end do
    out%ptr = create_dtype_json_array_c(c_nitems, c_loc(c_items(1)), &
         logical(use_generic, kind=1))
  end function create_dtype_json_array

  function create_dtype_json_object(nitems, keys, values, use_generic) &
       result(out)
    implicit none
    integer, intent(in) :: nitems
    character(len=*), dimension(:), intent(in), target :: keys
    type(yggdtype), dimension(:), intent(in) :: values
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    integer(kind=c_size_t) :: c_nitems
    type(c_ptr), target :: c_keys(size(keys))
    type(c_ptr), target :: c_values(size(values))
    character(kind=c_char, len=len(keys(1))), pointer :: ikey
    integer :: i, ikey_len
    c_nitems = nitems
    do i = 1, size(keys)
       ikey => keys(i)
       ikey_len = len_trim(ikey)
       if (ikey_len.lt.len(ikey)) then
          ikey((ikey_len+1):(ikey_len+1)) = c_null_char
       end if
       c_keys(i) = c_loc(ikey(1:1))
    end do
    do i = 1, size(values)
       c_values(i) = values(i)%ptr
    end do
    out%ptr = create_dtype_json_object_c(c_nitems, c_loc(c_keys(1)), &
         c_loc(c_values(1)), logical(use_generic, kind=1))
  end function create_dtype_json_object

  function create_dtype_ply(use_generic) result(out)
    implicit none
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    out%ptr = create_dtype_ply_c(logical(use_generic, kind=1))
  end function create_dtype_ply

  function create_dtype_obj(use_generic) result(out)
    implicit none
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    out%ptr = create_dtype_obj_c(logical(use_generic, kind=1))
  end function create_dtype_obj

  function create_dtype_format(format_str, as_array, use_generic) &
       result(out)
    implicit none
    character(len=*), intent(in) :: format_str
    integer, intent(in) :: as_array
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    character(len=len_trim(format_str)+1) :: c_format_str
    c_format_str = trim(format_str)//c_null_char
    call fix_format_str(c_format_str)
    out%ptr = create_dtype_format_c(c_format_str, as_array, logical(use_generic, kind=1))
  end function create_dtype_format

  function create_dtype_pyobj(typename, use_generic) result(out)
    implicit none
    character(len=*), intent(in) :: typename
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    character(len=len_trim(typename)+1) :: c_typename
    c_typename = trim(typename)//c_null_char
    out%ptr = create_dtype_pyobj_c(c_typename, logical(use_generic, kind=1))
  end function create_dtype_pyobj

  function create_dtype_schema(use_generic) result(out)
    implicit none
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    out%ptr = create_dtype_schema_c(logical(use_generic, kind=1))
  end function create_dtype_schema

  function create_dtype_any(use_generic) result(out)
    implicit none
    logical, intent(in) :: use_generic
    type(yggdtype) :: out
    out%ptr = create_dtype_any_c(logical(use_generic, kind=1))
  end function create_dtype_any

  ! Methods for sending/receiving
  function ygg_send(ygg_q, data, data_len) result (flag)
    implicit none
    type(yggcomm), intent(in) :: ygg_q
    type(c_ptr) :: c_ygg_q
    character(len=*), intent(in) :: data
    character(len=len(data)+1) :: c_data
    integer, intent(in) :: data_len
    integer(kind=c_int) :: c_data_len
    logical :: flag
    integer(kind=c_int) :: c_flag
    c_ygg_q = ygg_q%comm
    c_data = data//c_null_char
    c_data_len = data_len
    c_flag = ygg_send_c(c_ygg_q, c_data, c_data_len)
    if (c_flag.ge.0) then
       flag = .true.
    else
       flag = .false.
    end if
  end function ygg_send
  
  function ygg_recv(ygg_q, data, data_len) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(c_ptr) :: c_ygg_q
    character(len=*) :: data
    character(len=len(data)+1) :: c_data
    integer :: data_len
    integer(kind=c_int) :: c_data_len
    logical :: flag
    integer(kind=c_int) :: c_flag
    c_ygg_q = ygg_q%comm
    c_data = data//c_null_char
    c_data_len = data_len
    c_flag = ygg_recv_c(c_ygg_q, c_data, c_data_len)
    if (c_flag.ge.0) then
       flag = .true.
       data = c_data(:c_flag)
       data_len = c_flag
    else
       flag = .false.
    end if
  end function ygg_recv

  function ygg_send_nolimit(ygg_q, data, data_len) result (flag)
    implicit none
    type(yggcomm), intent(in) :: ygg_q
    type(yggchar_r) :: data
    integer, intent(in) :: data_len
    logical :: flag
    integer(kind=c_size_t) :: len_used
    len_used = data_len
    flag = ygg_send_var(ygg_q, [yggarg(data), yggarg(len_used)])
  end function ygg_send_nolimit
  
  function ygg_recv_nolimit(ygg_q, data, data_len) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(yggchar_r) :: data
    integer :: data_len
    logical :: flag
    integer(kind=c_size_t) :: len_used
    len_used = data_len
    flag = ygg_recv_var_realloc(ygg_q, [yggarg(data), yggarg(len_used)])
    if (flag) then
       data_len = int(len_used)
    end if
  end function ygg_recv_nolimit

  function ygg_send_var_sing(ygg_q, arg) result (flag)
    implicit none
    type(yggcomm), intent(in) :: ygg_q
    type(yggptr) :: arg
    logical :: flag
    flag = ygg_send_var_mult(ygg_q, [arg])
  end function ygg_send_var_sing
  function ygg_send_var_mult(ygg_q, args) result (flag)
    implicit none
    type(yggcomm), intent(in) :: ygg_q
    type(c_ptr) :: c_ygg_q
    type(yggptr) :: args(:)
    type(c_ptr), allocatable, target :: c_args(:)
    integer :: c_nargs
    logical :: flag, is_format
    integer(kind=c_int) :: c_flag
    is_format = is_comm_format_array_type(ygg_q, args)
    c_ygg_q = ygg_q%comm
    c_nargs = pre_send(args, c_args, is_format)
    c_flag = ygg_send_var_c(c_ygg_q, c_nargs, c_loc(c_args(1)))
    if (c_flag.ge.0) then
       flag = .true.
    else
       flag = .false.
    end if
    call post_send(args, c_args, flag)
  end function ygg_send_var_mult

  function is_next_size_t(args, i, req_array) result(flag)
    implicit none
    type(yggptr) :: args(:)
    integer :: i
    logical, intent(in), optional :: req_array
    logical :: flag
    if (i.ge.size(args)) then
       flag = .false.
    else
       if (present(req_array)) then
          flag = is_size_t(args(i+1), req_array)
       else
          flag = is_size_t(args(i+1))
       end if
    end if
  end function is_next_size_t

  function is_size_t(arg, req_array_in) result(flag)
    type(yggptr), intent(in) :: arg
    logical, optional :: req_array_in
    logical :: req_array
    logical :: flag
    if (present(req_array_in)) then
       req_array = req_array_in
    else
       req_array = .false.
    end if
    if (((arg%type.eq."integer").or.(arg%type.eq."size_t")).and. &
         (arg%nbytes.eq.8)) then
       flag = .true.
       if (req_array.and.(.not.arg%array)) then
          flag = .false.
       else if ((.not.req_array).and.arg%array) then
          flag = .false.
       end if
    else
       flag = .false.
    end if
  end function is_size_t

  function pre_send(args, c_args, is_format) result(c_nargs)
    implicit none
    type(yggptr) :: args(:)
    type(c_ptr), allocatable, target :: c_args(:)
    logical :: is_format
    integer(kind=c_int) :: c_nargs
    integer(kind=c_size_t) :: k
    integer :: i, j
    integer :: nargs
    call ygglog_debug("pre_send: begin")
    nargs = size(args)  ! Number of arguments passed
    c_nargs = nargs  ! Number of arguments that C should be aware of
    if (is_format) then
       if (.not.is_size_t(args(1))) then
          nargs = nargs + 1
          c_nargs = c_nargs + 1
       end if
    end if
    do i = 1, size(args)
       allocate(args(i)%len_c)
       allocate(args(i)%prec_c)
       allocate(args(i)%ndim_c)
       allocate(args(i)%shape_c(args(i)%ndim))
       args(i)%len_c = 1
       args(i)%prec_c = 1
       args(i)%ndim_c = 1
       do k = 1, args(i)%ndim
          args(i)%shape_c(k) = args(i)%shape(k)
       end do
       if (args(i)%array) then
          if (args(i)%ndim.gt.1) then
             if (is_next_size_t(args, i).and.is_next_size_t(args, i+1, req_array=.true.)) then
                ! Do nothing, vars already exist
             else if (is_next_size_t(args, i, req_array=.true.)) then
                if (args(i)%alloc) then
                   nargs = nargs + 1  ! For ndim
                   c_nargs = c_nargs + 1
                end if
             else if (args(i)%alloc) then
                nargs = nargs + 2  ! For ndim and shape
                c_nargs = c_nargs + 2
             end if
          else
             if ((.not.is_format).and.(.not.is_next_size_t(args, i))) then
                if (args(i)%alloc) then
                   nargs = nargs + 1  ! For the array size
                   c_nargs = c_nargs + 1
                end if
             end if
          end if
       else if ((args(i)%type.eq."character").or. &
            (args(i)%type.eq."unicode")) then
          if (.not.is_next_size_t(args, i)) then
             nargs = nargs + 1  ! For the string size
             c_nargs = c_nargs + 1
          end if
       end if
    end do
    call ygglog_debug("pre_send: counted variables")
    allocate(c_args(nargs))
    j = 1
    if (is_format) then
       if (.not.is_size_t(args(1))) then
          args(1)%len_c = args(1)%len
          args(1)%len_ptr = c_loc(args(1)%len_c)
          c_args(j) = args(1)%len_ptr
          j = j + 1
       end if
    end if
    do i = 1, size(args)
       c_args(j) = args(i)%ptr
       j = j + 1
       if (args(i)%array) then
          if (args(i)%ndim.gt.1) then
             if (is_next_size_t(args, i).and.is_next_size_t(args, i+1, req_array=.true.)) then
                args(i)%ndim_ptr = args(i+1)%ptr
                args(i)%shape_ptr = args(i+2)%ptr
             else if (is_next_size_t(args, i, req_array=.true.)) then
                args(i)%shape_ptr = args(i+1)%ptr
                if (args(i)%alloc) then
                   args(i)%ndim_c = args(i)%ndim
                   args(i)%ndim_ptr = c_loc(args(i)%ndim_c)
                   c_args(j) = args(i)%ndim_ptr
                   j = j + 1
                end if
             else if (args(i)%alloc) then
                args(i)%ndim_c = args(i)%ndim
                args(i)%ndim_ptr = c_loc(args(i)%ndim_c)
                c_args(j) = args(i)%ndim_ptr
                j = j + 1
                args(i)%shape_ptr = c_loc(args(i)%shape_c(1))
                c_args(j) = args(i)%shape_ptr
                j = j + 1
             end if
          else
             if (is_format) then
                args(i)%len_ptr = c_args(1)
             else if (is_next_size_t(args, i)) then
                args(i)%len_ptr = args(i+1)%ptr
             else if (args(i)%alloc) then
                args(i)%len_c = args(i)%len
                args(i)%len_ptr = c_loc(args(i)%len_c)
                c_args(j) = args(i)%len_ptr
                j = j + 1
             end if
          end if
       else if ((args(i)%type.eq."character").or. &
            (args(i)%type.eq."unicode")) then
          if (is_next_size_t(args, i)) then
             args(i)%prec_ptr = args(i+1)%ptr
          else
             args(i)%prec_c = args(i)%prec
             args(i)%prec_ptr = c_loc(args(i)%prec_c)
             c_args(j) = args(i)%prec_ptr
             j = j + 1
          end if
       end if
    end do
    call ygglog_debug("pre_send: end")
  end function pre_send

  function pre_recv(args, c_args, is_format) result(c_nargs)
    implicit none
    type(yggptr) :: args(:)
    type(c_ptr), allocatable, target :: c_args(:)
    logical :: is_format
    integer(kind=c_int) :: c_nargs
    integer(kind=c_size_t) :: k
    integer :: i, j
    integer :: nargs
    call ygglog_debug("pre_recv: begin")
    nargs = size(args)  ! Number of arguments passed
    c_nargs = nargs  ! Number of arguments that C should be aware of
    if ((is_format).and.(nargs.gt.0)) then
       if (.not.is_size_t(args(1))) then
          nargs = nargs + 1
          c_nargs = c_nargs + 1
       end if
    end if
    do i = 1, size(args)
       allocate(args(i)%len_c)
       allocate(args(i)%prec_c)
       allocate(args(i)%ndim_c)
       args(i)%len_c = 1
       args(i)%prec_c = 1
       args(i)%ndim_c = 1
       if (associated(args(i)%shape)) then
          allocate(args(i)%shape_c(args(i)%ndim))
          do k = 1, args(i)%ndim
             args(i)%shape_c(k) = args(i)%shape(k)
          end do
       end if
       if (args(i)%array) then
          if ((args(i)%ndim.gt.1).or.args(i)%ndarray) then
             if (is_next_size_t(args, i).and.is_next_size_t(args, i+1, req_array=.true.)) then
                ! Do nothing, vars already exist
             else if (is_next_size_t(args, i, req_array=.true.)) then
                nargs = nargs + 1  ! For ndim
                if (args(i)%alloc) then
                   c_nargs = c_nargs + 1
                end if
             else
                nargs = nargs + 2  ! For ndim and shape
                if (args(i)%alloc) then
                   c_nargs = c_nargs + 2
                end if
             end if
          else
             if ((.not.is_format).and.(.not.is_next_size_t(args, i))) then
                nargs = nargs + 1  ! For the array size
                if (args(i)%alloc) then
                   c_nargs = c_nargs + 1
                end if
             end if
          end if
          if ((args(i)%type.eq."character").or. &
               (args(i)%type.eq."unicode")) then
             nargs = nargs + 1  ! For the string length
          end if
       else if ((args(i)%type.eq."character").or. &
            (args(i)%type.eq."unicode")) then
          if (.not.is_next_size_t(args, i)) then
             nargs = nargs + 1  ! For the string size
             c_nargs = c_nargs + 1
          end if
       end if
    end do
    allocate(c_args(nargs))
    call ygglog_debug("pre_recv: counted and allocated for arguments")
    j = 1
    if (is_format) then
       if (.not.is_size_t(args(1))) then
          args(1)%len_c = args(1)%len
          args(1)%len_ptr = c_loc(args(1)%len_c)
          c_args(j) = args(1)%len_ptr
          j = j + 1
       end if
    end if
    do i = 1, size(args)
       c_args(j) = args(i)%ptr
       j = j + 1
       if (args(i)%array) then
          ! TODO: handle case where shape is explicit and ensure
          ! that length of shape variable is not appended
          if ((args(i)%ndim.gt.1).or.args(i)%ndarray) then
             if (is_next_size_t(args, i).and.is_next_size_t(args, i+1, req_array=.true.)) then
                args(i)%ndim_ptr = args(i+1)%ptr
                args(i)%shape_ptr = args(i+2)%ptr
             else if (is_next_size_t(args, i, req_array=.true.)) then
                args(i)%shape_ptr = args(i+1)%ptr
                args(i)%ndim_c = args(i)%ndim
                args(i)%ndim_ptr = c_loc(args(i)%ndim_c)
                c_args(j) = args(i)%ndim_ptr
                j = j + 1
             else
                args(i)%ndim_c = args(i)%ndim
                args(i)%ndim_ptr = c_loc(args(i)%ndim_c)
                c_args(j) = args(i)%ndim_ptr
                j = j + 1
                if (associated(args(i)%shape_c)) then
                   args(i)%shape_ptr = c_loc(args(i)%shape_c(1))
                else
                   args(i)%shape_ptr = c_null_ptr
                end if
                c_args(j) = args(i)%shape_ptr
                j = j + 1
             end if
          else
             if (is_format) then
                args(i)%len_ptr = c_args(1)
             else if (is_next_size_t(args, i)) then
                args(i)%len_ptr = args(i+1)%ptr
             else
                args(i)%len_c = args(i)%len
                args(i)%len_ptr = c_loc(args(i)%len_c)
                c_args(j) = args(i)%len_ptr
                j = j + 1
             end if
          end if
          if ((args(i)%type.eq."character").or. &
               (args(i)%type.eq."unicode")) then
             args(i)%prec_c = args(i)%prec
             args(i)%prec_ptr = c_loc(args(i)%prec_c)
             c_args(j) = args(i)%prec_ptr
             j = j + 1
          end if
       else if ((args(i)%type.eq."character").or. &
            (args(i)%type.eq."unicode")) then
          if (is_next_size_t(args, i)) then
             args(i)%prec_ptr = args(i+1)%ptr
          else
             args(i)%prec_c = args(i)%prec
             args(i)%prec_ptr = c_loc(args(i)%prec_c)
             c_args(j) = args(i)%prec_ptr
             j = j + 1
          end if
       end if
    end do
    call ygglog_debug("pre_recv: end")
  end function pre_recv

  subroutine post_recv(args, c_args, flag, realloc, is_format)
    implicit none
    type(yggptr) :: args(:)
    type(c_ptr), allocatable, target :: c_args(:)
    logical :: flag
    integer :: i, j
    logical :: realloc, is_format
    call ygglog_debug("post_recv: begin")
    if (flag) then
       j = 1
       if (is_format) then
          if (.not.is_size_t(args(1))) then
             j = j + 1
          end if
       end if
       do i = 1, size(args)
          args(i)%ptr = c_args(j)
          if ((args(i)%ndim.gt.1).or.args(i)%ndarray) then
             args(i)%shape_ptr = c_args(j+2)
          end if
          flag = yggptr_c2f(args(i), realloc)
          if (.not.flag) then
             call ygglog_error("Error recovering fortran pointer for variable.")
             exit
          end if
          j = j + 1
          if (args(i)%array) then
             if ((args(i)%ndim.gt.1).or.args(i)%ndarray) then
                if (is_next_size_t(args, i).and.is_next_size_t(args, i+1, req_array=.true.)) then
                   ! Do nothing, process variables as normal
                else if (is_next_size_t(args, i, req_array=.true.)) then
                   j = j + 1
                else
                   j = j + 2
                end if
             else
                if ((.not.is_format).and.(.not.is_next_size_t(args, i))) then
                   j = j + 1
                end if
             end if
             if ((args(i)%type.eq."character").or. &
                  (args(i)%type.eq."unicode")) then
                j = j + 1
             end if
          else if ((args(i)%type.eq."character").or. &
               (args(i)%type.eq."unicode")) then
             if (.not.is_next_size_t(args, i)) then
                j = j + 1
             end if
          end if
       end do
    end if
    if (flag) then
       do i = 1, size(args)
          deallocate(args(i)%len_c)
          deallocate(args(i)%prec_c)
          deallocate(args(i)%ndim_c)
          if (associated(args(i)%shape_c)) then
             deallocate(args(i)%shape_c)
          end if
       end do
    end if
    if (allocated(c_args)) then
       deallocate(c_args)
    end if
    call ygglog_debug("post_recv: end")
  end subroutine post_recv

  subroutine post_send(args, c_args, flag)
    implicit none
    type(yggptr) :: args(:)
    type(c_ptr), allocatable, target :: c_args(:)
    logical :: flag
    integer :: i
    call ygglog_debug("post_send: begin")
    if (flag) then
       do i = 1, size(args)
          deallocate(args(i)%len_c)
          deallocate(args(i)%prec_c)
          deallocate(args(i)%ndim_c)
          deallocate(args(i)%shape_c)
       end do
    end if
    if (allocated(c_args)) then
       deallocate(c_args)
    end if
    call ygglog_debug("post_send: end")
  end subroutine post_send

  function ygg_rpc_call_1v1(ygg_q, oarg, iarg) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(yggptr) :: oarg
    type(yggptr) :: iarg
    logical :: flag
    flag = ygg_rpc_call_mult(ygg_q, [oarg], [iarg])
  end function ygg_rpc_call_1v1
  function ygg_rpc_call_1vm(ygg_q, oarg, iargs) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(yggptr) :: oarg
    type(yggptr) :: iargs(:)
    logical :: flag
    flag = ygg_rpc_call_mult(ygg_q, [oarg], iargs)
  end function ygg_rpc_call_1vm
  function ygg_rpc_call_mv1(ygg_q, oargs, iarg) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(yggptr) :: oargs(:)
    type(yggptr) :: iarg
    logical :: flag
    flag = ygg_rpc_call_mult(ygg_q, oargs, [iarg])
  end function ygg_rpc_call_mv1
  function ygg_rpc_call_mult(ygg_q, oargs, iargs) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(c_ptr) :: c_ygg_q
    type(yggptr) :: oargs(:)
    type(yggptr) :: iargs(:)
    type(c_ptr), allocatable, target :: c_args(:)
    type(c_ptr), allocatable, target :: c_iargs(:)
    type(c_ptr), allocatable, target :: c_oargs(:)
    integer :: c_nargs
    logical :: flag
    integer :: i
    integer(kind=c_int) :: c_flag
    logical :: iis_format, ois_format
    ois_format = is_comm_format_array_type(ygg_q, oargs)
    iis_format = is_comm_format_array_type(ygg_q, iargs)
    c_ygg_q = ygg_q%comm
    c_nargs = 0
    c_nargs = c_nargs + pre_send(oargs, c_oargs, ois_format)
    c_nargs = c_nargs + pre_recv(iargs, c_iargs, iis_format)
    allocate(c_args(size(c_oargs) + size(c_iargs)))
    do i = 1, size(c_oargs)
       c_args(i) = c_oargs(i)
    end do
    do i = 1, size(c_iargs)
       c_args(i + size(c_oargs)) = c_iargs(i)
    end do
    c_flag = ygg_rpc_call_c(c_ygg_q, c_nargs, c_loc(c_args(1)))
    if (c_flag.ge.0) then
       flag = .true.
    else
       flag = .false.
    end if
    do i = 1, size(c_iargs)
       c_iargs(i) = c_args(i + size(c_oargs))
    end do
    call post_send(oargs, c_oargs, flag)
    call post_recv(iargs, c_iargs, flag, .false., iis_format)
    if (allocated(c_args)) then
       deallocate(c_args)
    end if
  end function ygg_rpc_call_mult
  
  function ygg_rpc_call_realloc_1v1(ygg_q, oarg, iarg) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(yggptr) :: oarg
    type(yggptr) :: iarg
    logical :: flag
    flag = ygg_rpc_call_realloc_mult(ygg_q, [oarg], [iarg])
  end function ygg_rpc_call_realloc_1v1
  function ygg_rpc_call_realloc_1vm(ygg_q, oarg, iargs) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(yggptr) :: oarg
    type(yggptr) :: iargs(:)
    logical :: flag
    flag = ygg_rpc_call_realloc_mult(ygg_q, [oarg], iargs)
  end function ygg_rpc_call_realloc_1vm
  function ygg_rpc_call_realloc_mv1(ygg_q, oargs, iarg) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(yggptr) :: oargs(:)
    type(yggptr) :: iarg
    logical :: flag
    flag = ygg_rpc_call_realloc_mult(ygg_q, oargs, [iarg])
  end function ygg_rpc_call_realloc_mv1
  function ygg_rpc_call_realloc_mult(ygg_q, oargs, iargs) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(c_ptr) :: c_ygg_q
    type(yggptr) :: oargs(:)
    type(yggptr) :: iargs(:)
    type(c_ptr), allocatable, target :: c_args(:)
    type(c_ptr), allocatable, target :: c_oargs(:)
    type(c_ptr), allocatable, target :: c_iargs(:)
    integer :: c_nargs
    logical :: flag, iis_format, ois_format
    integer(kind=c_int) :: c_flag
    integer :: i
    c_ygg_q = ygg_q%comm
    ois_format = is_comm_format_array_type(ygg_q, oargs)
    iis_format = is_comm_format_array_type(ygg_q, iargs)
    flag = .true.
    do i = 1, size(iargs)
       if ((iargs(i)%array.or.(iargs(i)%type.eq."character").or. &
            (iargs(i)%type.eq."unicode")).and. &
            (.not.(iargs(i)%alloc))) then
          call ygglog_error("Provided array/string is not allocatable.")
          flag = .false.
       end if
    end do
    if (flag) then
       c_nargs = 0
       c_nargs = c_nargs + pre_send(oargs, c_oargs, ois_format)
       c_nargs = c_nargs + pre_recv(iargs, c_iargs, iis_format)
       allocate(c_args(size(c_oargs) + size(c_iargs)))
       do i = 1, size(c_oargs)
          c_args(i) = c_oargs(i)
       end do
       do i = 1, size(c_iargs)
          c_args(i + size(c_oargs)) = c_iargs(i)
       end do
       c_flag = ygg_rpc_call_realloc_c(c_ygg_q, c_nargs, c_loc(c_args(1)))
       if (c_flag.ge.0) then
          flag = .true.
       else
          flag = .false.
       end if
       do i = 1, size(c_iargs)
          c_iargs(i) = c_args(i + size(c_oargs))
       end do
    end if
    call post_send(oargs, c_oargs, flag)
    call post_recv(iargs, c_iargs, flag, .true., iis_format)
    if (allocated(c_args)) then
       deallocate(c_args)
    end if
  end function ygg_rpc_call_realloc_mult
  
  function ygg_recv_var_sing(ygg_q, arg) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(yggptr) :: arg
    logical :: flag
    flag = ygg_recv_var_mult(ygg_q, [arg])
  end function ygg_recv_var_sing
  function ygg_recv_var_mult(ygg_q, args) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(c_ptr) :: c_ygg_q
    type(yggptr) :: args(:)
    type(c_ptr), allocatable, target :: c_args(:)
    integer :: c_nargs
    logical :: flag, is_format
    integer(kind=c_int) :: c_flag
    is_format = is_comm_format_array_type(ygg_q, args)
    c_ygg_q = ygg_q%comm
    c_nargs = pre_recv(args, c_args, is_format)
    c_flag = ygg_recv_var_c(c_ygg_q, c_nargs, c_loc(c_args(1)))
    if (c_flag.ge.0) then
       flag = .true.
    else
       flag = .false.
    end if
    call post_recv(args, c_args, flag, .false., is_format)
  end function ygg_recv_var_mult

  function ygg_recv_var_realloc_sing(ygg_q, arg) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(yggptr) :: arg
    logical :: flag
    flag = ygg_recv_var_realloc_mult(ygg_q, [arg])
  end function ygg_recv_var_realloc_sing
  function ygg_recv_var_realloc_mult(ygg_q, args) result (flag)
    implicit none
    type(yggcomm) :: ygg_q
    type(c_ptr) :: c_ygg_q
    type(yggptr), target :: args(:)
    type(c_ptr), allocatable, target :: c_args(:)
    integer :: c_nargs
    logical :: flag, is_format
    integer :: i
    integer(kind=c_int) :: c_flag
    call ygglog_debug("ygg_recv_var_realloc: begin")
    is_format = is_comm_format_array_type(ygg_q, args)
    c_ygg_q = ygg_q%comm
    flag = .true.
    do i = 1, size(args)
       if ((args(i)%array.or.(args(i)%type.eq."character").or. &
            (args(i)%type.eq."unicode")).and. &
            (.not.(args(i)%alloc))) then
          call ygglog_error("Provided array/string is not allocatable.")
          flag = .false.
       end if
    end do
    call ygglog_debug("ygg_recv_var_realloc: checked variables")
    if (flag) then
       c_nargs = pre_recv(args, c_args, is_format)
       c_flag = ygg_recv_var_realloc_c(c_ygg_q, c_nargs, c_loc(c_args(1)))
       if (c_flag.ge.0) then
          flag = .true.
       else
          flag = .false.
       end if
    end if
    call post_recv(args, c_args, flag, .true., is_format)
    call ygglog_debug("ygg_recv_var_realloc: end")
  end function ygg_recv_var_realloc_mult

  ! Ply interface
  function init_ply() result (out)
    implicit none
    type(yggply) :: out
    out = init_ply_c()
  end function init_ply
  subroutine free_ply(p)
    implicit none
    type(yggply), target :: p
    type(yggply), pointer :: pp
    type(c_ptr) :: c_p
    pp => p
    c_p = c_loc(pp)
    call free_ply_c(c_p)
    nullify(pp)
  end subroutine free_ply
  function copy_ply(p) result(out)
    implicit none
    type(yggply), intent(in) :: p
    type(yggply) :: out
    out = copy_ply_c(p)
  end function copy_ply
  subroutine display_ply_indent(p, indent)
    implicit none
    type(yggply), intent(in) :: p
    character(len=*), intent(in) :: indent
    character(len=len(indent)+1) :: c_indent
    c_indent = indent//c_null_char
    call display_ply_indent_c(p, c_indent)
  end subroutine display_ply_indent
  subroutine display_ply(p)
    implicit none
    type(yggply), intent(in) :: p
    call display_ply_c(p)
  end subroutine display_ply
  
  ! Obj interface
  function init_obj() result (out)
    implicit none
    type(yggobj) :: out
    out = init_obj_c()
  end function init_obj
  subroutine free_obj(p)
    implicit none
    type(yggobj), target :: p
    type(yggobj), pointer :: pp
    type(c_ptr) :: c_p
    pp => p
    c_p = c_loc(pp)
    call free_obj_c(c_p)
    nullify(pp)
  end subroutine free_obj
  function copy_obj(p) result(out)
    implicit none
    type(yggobj), intent(in) :: p
    type(yggobj) :: out
    out = copy_obj_c(p)
  end function copy_obj
  subroutine display_obj_indent(p, indent)
    implicit none
    type(yggobj), intent(in) :: p
    character(len=*), intent(in) :: indent
    character(len=len(indent)+1) :: c_indent
    c_indent = indent//c_null_char
    call display_obj_indent_c(p, c_indent)
  end subroutine display_obj_indent
  subroutine display_obj(p)
    implicit none
    type(yggobj), intent(in) :: p
    call display_obj_c(p)
  end subroutine display_obj

  ! Generic interface
  function init_generic() result(out)
    implicit none
    type(ygggeneric) :: out
    out = init_generic_c()
  end function init_generic
  function init_generic_array() result(out)
    implicit none
    type(ygggeneric) :: out
    out = init_generic_array_c()
  end function init_generic_array
  function init_generic_map() result(out)
    implicit none
    type(ygggeneric) :: out
    out = init_generic_map_c()
  end function init_generic_map
  function create_generic(type_class, data) result(out)
    implicit none
    type(yggdtype) :: type_class
    type(yggptr) :: data
    integer(kind=c_size_t) :: nbytes
    type(c_ptr) :: c_type_class
    type(c_ptr) :: c_data
    type(ygggeneric) :: out
    c_type_class = type_class%ptr
    c_data = data%ptr
    nbytes = data%nbytes
    out = create_generic_c(c_type_class, c_data, nbytes)
  end function create_generic
  subroutine free_generic(x)
    implicit none
    type(ygggeneric), target :: x
    integer(kind=c_int) :: out
    out = free_generic_c(c_loc(x))
    if (out.ne.0) then
       stop "Error freeing generic object."
    end if
  end subroutine free_generic
  function is_generic_init(x) result(out)
    implicit none
    type(ygggeneric), value, intent(in) :: x
    logical :: out
    integer(kind=c_int) :: c_out
    out = .false.
    c_out = is_generic_init_c(x)
    if (c_out.ne.0) then
       out = .true.
    end if
  end function is_generic_init
  function copy_generic(src) result(out)
    implicit none
    type(ygggeneric), intent(in) :: src
    type(ygggeneric) :: out
    out = copy_generic_c(src)
  end function copy_generic
  subroutine display_generic(x)
    implicit none
    type(ygggeneric), intent(in) :: x
    call display_generic_c(x)
  end subroutine display_generic
  function add_generic_array(arr, x) result(out)
    implicit none
    type(ygggeneric) :: arr
    type(ygggeneric), intent(in) :: x
    integer(kind=c_int) :: out
    out = add_generic_array_c(arr, x)
  end function add_generic_array
  function set_generic_array(arr, i, x) result(out)
    implicit none
    type(ygggeneric) :: arr
    integer(kind=c_size_t), intent(in) :: i
    type(ygggeneric), intent(in) :: x
    integer(kind=c_int) :: out
    out = set_generic_array_c(arr, i-1, x)
  end function set_generic_array
  function get_generic_array(arr, i, x) result(out)
    implicit none
    type(ygggeneric), intent(in) :: arr
    integer(kind=c_size_t), intent(in) :: i
    type(ygggeneric), pointer :: x
    integer(kind=c_int) :: out
    type(c_ptr) :: c_x
    allocate(x);
    c_x = c_loc(x) ! Maybe use first element in type
    out = get_generic_array_c(arr, i-1, c_x)
  end function get_generic_array
  function set_generic_object(arr, k, x) result(out)
    implicit none
    type(ygggeneric) :: arr
    character(len=*), intent(in) :: k
    type(ygggeneric), intent(in) :: x
    integer(kind=c_int) :: out
    character(len=len_trim(k)+1) :: c_k
    c_k = trim(k)//c_null_char
    out = set_generic_object_c(arr, c_k, x)
  end function set_generic_object
  function get_generic_object(arr, k, x) result(out)
    implicit none
    type(ygggeneric), intent(in) :: arr
    character(len=*), intent(in) :: k
    type(ygggeneric), pointer, intent(out) :: x
    integer(kind=c_int) :: out
    character(len=len_trim(k)+1) :: c_k
    type(c_ptr) :: c_x
    allocate(x);
    c_k = trim(k)//c_null_char
    c_x = c_loc(x) ! Maybe use first element in type
    out = get_generic_object_c(arr, c_k, c_x)
  end function get_generic_object

  ! Python interface
  function init_python() result(out)
    implicit none
    type(yggpython) :: out
    out = init_python_c()
  end function init_python
  subroutine free_python(x)
    implicit none
    type(yggpython), target :: x
    type(yggpython), pointer :: xp
    type(c_ptr) :: c_x
    xp => x
    c_x = c_loc(xp)
    call free_python_c(c_x)
    nullify(xp)
  end subroutine free_python
  function copy_python(x) result(out)
    implicit none
    type(yggpython) :: x
    type(yggpython) :: out
    out = copy_python_c(x)
  end function copy_python
  subroutine display_python(x)
    implicit none
    type(yggpython) :: x
    call display_python_c(x)
  end subroutine display_python

  ! Interface for getting/setting generic array elements
  ! Get
  function generic_array_get_size(x) result(out)
    implicit none
    type(ygggeneric) :: x
    integer(kind=c_size_t) :: out
    out = generic_array_get_size_c(x)
  end function generic_array_get_size
  function generic_array_get_item(x, index, typename) result(out)
    implicit none
    type(ygggeneric) :: x
    integer, intent(in) :: index
    character(len=*), intent(in) :: typename
    type(c_ptr) :: out
    character(len=len_trim(typename)+1) :: c_typename
    c_typename = trim(typename)//c_null_char
    out = generic_array_get_item_c(x, int(index-1, c_size_t), c_typename)
  end function generic_array_get_item
  function generic_array_get_item_nbytes(x, index) result(out)
    implicit none
    type(ygggeneric) :: x
    integer, intent(in) :: index
    integer(kind=c_int) :: out
    out = generic_array_get_item_nbytes_c(x, int(index-1, c_size_t))
    if (out.lt.0) then
       stop "Error getting number of bytes in array item."
    end if
  end function generic_array_get_item_nbytes
  function generic_array_get_scalar(x, index, subtype, precision) result(out)
    implicit none
    type(ygggeneric) :: x
    integer, intent(in) :: index
    character(len=*), intent(in) :: subtype
    integer, intent(in) :: precision
    type(c_ptr) :: out
    character(len=len_trim(subtype)+1) :: c_subtype
    c_subtype = trim(subtype)//c_null_char
    out = generic_array_get_scalar_c(x, int(index-1, c_size_t), &
         c_subtype, int(precision, c_size_t))
  end function generic_array_get_scalar
  function generic_array_get_1darray(x, index, subtype, precision, data) &
       result(out)
    implicit none
    type(ygggeneric) :: x
    integer, intent(in) :: index
    character(len=*), intent(in) :: subtype
    integer, intent(in) :: precision
    type(c_ptr), value :: data
    integer(kind=c_size_t) :: out
    character(len=len_trim(subtype)+1) :: c_subtype
    c_subtype = trim(subtype)//c_null_char
    out = generic_array_get_1darray_c(x, int(index-1, c_size_t), &
         c_subtype, int(precision, c_size_t), data)
  end function generic_array_get_1darray
  function generic_array_get_ndarray(x, index, subtype, precision, &
       data) result(shape)
    implicit none
    type(ygggeneric) :: x
    integer, intent(in) :: index
    character(len=*), intent(in) :: subtype
    integer, intent(in) :: precision
    type(c_ptr), value :: data
    integer(kind=c_size_t), dimension(:), pointer :: shape
    integer(kind=c_size_t) :: ndim
    character(len=len_trim(subtype)+1) :: c_subtype
    type(c_ptr), target :: c_shape
    c_subtype = trim(subtype)//c_null_char
    ndim = generic_array_get_ndarray_c(x, int(index-1, c_size_t), &
         subtype, int(precision, c_size_t), data, c_loc(c_shape))
    call c_f_pointer(c_shape, shape, [ndim])
  end function generic_array_get_ndarray
  ! Set
  subroutine generic_array_set_item(x, index, typename, val)
    implicit none
    type(ygggeneric) :: x
    integer, intent(in) :: index
    character(len=*), intent(in) :: typename
    type(c_ptr) :: val
    integer(kind=c_int) :: c_out
    character(len=len_trim(typename)+1) :: c_typename
    c_typename = trim(typename)//c_null_char
    c_out = generic_array_set_item_c(x, int(index-1, c_size_t), &
         c_typename, val)
    if (c_out.lt.0) then
       stop "Error setting element in array."
    end if
  end subroutine generic_array_set_item
  subroutine generic_array_set_scalar(x, index, val, subtype, &
       precision, units_in)
    implicit none
    type(ygggeneric) :: x
    integer, intent(in) :: index
    type(c_ptr) :: val
    character(len=*), intent(in) :: subtype
    integer, intent(in) :: precision
    character(len=*), intent(in), optional, target :: units_in
    character(len=:), pointer :: units
    integer(kind=c_int) :: c_out
    character(len=len_trim(subtype)+1) :: c_subtype
    character(len=:), pointer :: c_units
    if (present(units_in)) then
       units => units_in
    else
       units = ""
    end if
    c_subtype = trim(subtype)//c_null_char
    c_units = trim(units)//c_null_char
    c_out = generic_array_set_scalar_c(x, int(index-1, c_size_t), &
         val, c_subtype, int(precision, c_size_t), c_units)
    if (c_out.lt.0) then
       stop "Error setting scalar element in array."
    end if
  end subroutine generic_array_set_scalar
  subroutine generic_array_set_1darray(x, index, val, subtype, &
       precision, length, units_in)
    implicit none
    type(ygggeneric) :: x
    integer, intent(in) :: index
    type(c_ptr) :: val
    character(len=*), intent(in) :: subtype
    integer, intent(in) :: precision
    integer, intent(in) :: length
    character(len=*), intent(in), optional, target :: units_in
    character(len=:), pointer :: units
    integer(kind=c_int) :: c_out
    character(len=len_trim(subtype)+1) :: c_subtype
    character(len=:), pointer :: c_units
    if (present(units_in)) then
       units => units_in
    else
       units = ""
    end if
    c_subtype = trim(subtype)//c_null_char
    c_units = trim(units)//c_null_char
    c_out = generic_array_set_1darray_c(x, int(index-1, c_size_t), &
         val, c_subtype, int(precision, c_size_t), &
         int(length, c_size_t), c_units)
    if (c_out.lt.0) then
       stop "Error setting 1darray element in array."
    end if
  end subroutine generic_array_set_1darray
  subroutine generic_array_set_ndarray(x, index, data, subtype, &
       precision, shape, units_in)
    implicit none
    type(ygggeneric) :: x
    integer, intent(in) :: index
    type(c_ptr) :: data
    character(len=*), intent(in) :: subtype
    integer, intent(in) :: precision
    integer(kind=c_size_t), dimension(:), intent(in), target :: shape
    character(len=*), intent(in), optional, target :: units_in
    character(len=:), pointer :: units
    integer(kind=c_int) :: c_out
    character(len=len_trim(subtype)+1) :: c_subtype
    character(len=:), pointer :: c_units
    if (present(units_in)) then
       units => units_in
    else
       units = ""
    end if
    c_subtype = trim(subtype)//c_null_char
    c_units = trim(units)//c_null_char
    c_out = generic_array_set_ndarray_c(x, int(index-1, c_size_t), &
         data, c_subtype, int(precision, c_size_t), &
         int(size(shape), c_size_t), c_loc(shape), c_units)
    if (c_out.lt.0) then
       stop "Error setting ndarray element in array."
    end if
  end subroutine generic_array_set_ndarray

  ! Interface for getting/setting generic map elements
  ! Get
  function generic_map_get_size(x) result(out)
    implicit none
    type(ygggeneric) :: x
    integer(kind=c_size_t) :: out
    out = generic_map_get_size_c(x)
  end function generic_map_get_size
  subroutine generic_map_get_keys(x, keys)
    implicit none
    type(ygggeneric) :: x
    character(len=*), dimension(:), pointer, intent(out) :: keys
    integer(kind=c_size_t), target :: n_keys
    integer(kind=c_size_t), target :: key_size
    integer(kind=c_size_t) :: i, j
    type(c_ptr) :: c_keys
    character, dimension(:), pointer :: f_keys
    c_keys = generic_map_get_keys_c(x, c_loc(n_keys), c_loc(key_size))
    if (.not.c_associated(c_keys)) then
      stop "Error getting keys from map."
    endif
    call c_f_pointer(c_keys, f_keys, [n_keys * key_size])
    allocate(keys(n_keys))
    if (key_size.gt.len(keys(1))) then
      stop "Key size is greater than size of provided keys."
    endif
    ! Allocation of character length and array dimension in gfortran
    ! has a bug which is fixed in gfortran 9.1 and the version on
    ! conda-forge as m2w64-gcc-fortran is only 5.3 as of 2020/6/18
    ! so for now the keys pointer needs to have a defined character
    ! length.
    ! allocate(character(len=key_size) :: keys(n_keys))
    do i = 1, n_keys
       do j = 1, key_size
          keys(i)(j:j) = f_keys(((i-1)*key_size)+j)
       end do
       do j = key_size+1, len(keys(1))
          keys(i)(j:j) = ' '
       end do
    end do
    deallocate(f_keys)
  end subroutine generic_map_get_keys
  function generic_map_get_item(x, key, typename) result(out)
    implicit none
    type(ygggeneric) :: x
    character(len=*) :: key
    character(len=*) :: typename
    type(c_ptr) :: out
    character(len=len_trim(key)+1) :: c_key
    character(len=len_trim(typename)+1) :: c_typename
    c_key = trim(key)//c_null_char
    c_typename = trim(typename)//c_null_char
    out = generic_map_get_item_c(x, c_key, c_typename)
  end function generic_map_get_item
  function generic_map_get_item_nbytes(x, key) result(out)
    implicit none
    type(ygggeneric) :: x
    character(len=*) :: key
    integer(kind=c_int) :: out
    character(len=len_trim(key)+1) :: c_key
    c_key = trim(key)//c_null_char
    out = generic_map_get_item_nbytes_c(x, c_key)
    if (out.lt.0) then
       stop "Error getting number of bytes in map item."
    end if
  end function generic_map_get_item_nbytes
  function generic_map_get_scalar(x, key, subtype, precision) result(out)
    implicit none
    type(ygggeneric) :: x
    character(len=*) :: key
    character(len=*) :: subtype
    integer, intent(in) :: precision
    type(c_ptr) :: out
    character(len=len_trim(key)+1) :: c_key
    character(len=len_trim(subtype)+1) :: c_subtype
    c_key = trim(key)//c_null_char
    c_subtype = trim(subtype)//c_null_char
    out = generic_map_get_scalar_c(x, c_key, c_subtype, &
         int(precision, c_size_t))
  end function generic_map_get_scalar
  function generic_map_get_1darray(x, key, subtype, precision, data) &
       result(out)
    implicit none
    type(ygggeneric) :: x
    character(len=*) :: key
    character(len=*) :: subtype
    integer, intent(in) :: precision
    type(c_ptr) :: data
    integer(kind=c_size_t) :: out
    character(len=len_trim(key)+1) :: c_key
    character(len=len_trim(subtype)+1) :: c_subtype
    c_key = trim(key)//c_null_char
    c_subtype = trim(subtype)//c_null_char
    out = generic_map_get_1darray_c(x, c_key, c_subtype, &
         int(precision, c_size_t), data)
  end function generic_map_get_1darray
  function generic_map_get_ndarray(x, key, subtype, precision, data) &
       result(shape)
    implicit none
    type(ygggeneric) :: x
    character(len=*) :: key
    character(len=*) :: subtype
    integer, intent(in) :: precision
    type(c_ptr) :: data
    integer(kind=c_size_t), dimension(:), pointer :: shape
    integer(kind=c_size_t) :: ndim
    character(len=len_trim(key)+1) :: c_key
    character(len=len_trim(subtype)+1) :: c_subtype
    type(c_ptr), target :: c_shape
    c_key = trim(key)//c_null_char
    c_subtype = trim(subtype)//c_null_char
    ndim = generic_map_get_ndarray_c(x, c_key, c_subtype, &
         int(precision, c_size_t), data, c_loc(c_shape))
    call c_f_pointer(c_shape, shape, [ndim])
  end function generic_map_get_ndarray
  ! Set
  subroutine generic_map_set_item(x, key, typename, val)
    implicit none
    type(ygggeneric) :: x
    character(len=*) :: key
    character(len=*) :: typename
    type(c_ptr) :: val
    integer(kind=c_int) :: c_out
    character(len=len_trim(key)+1) :: c_key
    character(len=len_trim(typename)+1) :: c_typename
    c_key = trim(key)//c_null_char
    c_typename = trim(typename)//c_null_char
    c_out = generic_map_set_item_c(x, c_key, c_typename, val)
    if (c_out.lt.0) then
       stop "Error setting element in map."
    end if
  end subroutine generic_map_set_item
  subroutine generic_map_set_scalar(x, key, val, subtype, precision, &
       units_in)
    implicit none
    type(ygggeneric) :: x
    character(len=*) :: key
    type(c_ptr) :: val
    character(len=*) :: subtype
    integer, intent(in) :: precision
    character(len=*), intent(in), optional, target :: units_in
    character(len=:), pointer :: units
    integer(kind=c_int) :: c_out
    character(len=len_trim(key)+1) :: c_key
    character(len=len_trim(subtype)+1) :: c_subtype
    character(len=:), pointer :: c_units
    if (present(units_in)) then
       units => units_in
    else
       allocate(character(len=0) :: units)
       units = ""
    end if
    allocate(character(len=len_trim(units)+1) :: c_units)
    c_key = trim(key)//c_null_char
    c_subtype = trim(subtype)//c_null_char
    c_units = trim(units)//c_null_char
    c_out = generic_map_set_scalar_c(x, c_key, val, c_subtype, &
         int(precision, c_size_t), c_units)
    if (c_out.lt.0) then
       stop "Error setting scalar element in map."
    end if
    deallocate(c_units)
  end subroutine generic_map_set_scalar
  subroutine generic_map_set_1darray(x, key, val, subtype, &
       precision, length, units_in)
    implicit none
    type(ygggeneric) :: x
    character(len=*) :: key
    type(c_ptr) :: val
    character(len=*) :: subtype
    integer, intent(in) :: precision
    integer, intent(in) :: length
    character(len=*), intent(in), optional, target :: units_in
    character(len=:), pointer :: units
    integer(kind=c_int) :: c_out
    character(len=len_trim(key)+1) :: c_key
    character(len=len_trim(subtype)+1) :: c_subtype
    character(len=:), pointer :: c_units
    if (present(units_in)) then
       units => units_in
    else
       units = ""
    end if
    c_key = trim(key)//c_null_char
    c_subtype = trim(subtype)//c_null_char
    c_units = trim(units)//c_null_char
    c_out = generic_map_set_1darray_c(x, c_key, val, c_subtype, &
         int(precision, c_size_t), int(length, c_size_t), c_units)
    if (c_out.lt.0) then
       stop "Error setting 1darray element in map."
    end if
  end subroutine generic_map_set_1darray
  subroutine generic_map_set_ndarray(x, key, data, subtype, &
       precision, shape, units_in)
    implicit none
    type(ygggeneric) :: x
    character(len=*) :: key
    type(c_ptr) :: data
    character(len=*) :: subtype
    integer, intent(in) :: precision
    integer(kind=c_size_t), dimension(:), intent(in), target :: shape
    character(len=*), intent(in), optional, target :: units_in
    character(len=:), pointer :: units
    integer(kind=c_int) :: c_out
    character(len=len_trim(key)+1) :: c_key
    character(len=len_trim(subtype)+1) :: c_subtype
    character(len=:), pointer :: c_units
    if (present(units_in)) then
       units => units_in
    else
       units = ""
    end if
    c_key = trim(key)//c_null_char
    c_subtype = trim(subtype)//c_null_char
    c_units = trim(units)//c_null_char
    c_out = generic_map_set_ndarray_c(x, c_key, data, c_subtype, &
         int(precision, c_size_t), int(size(shape), c_size_t), &
         c_loc(shape), c_units)
    if (c_out.lt.0) then
       stop "Error setting ndarray element in map."
    end if
  end subroutine generic_map_set_ndarray
  
end module fygg
