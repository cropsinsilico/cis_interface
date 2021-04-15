#include "c_wrappers.h"

// Utilities
int ygg_init_f() {
  return ygg_init();
}

void ygg_c_free(void *x) {
  if (x != NULL) {
    free(x);
  }
}

void ygg_log_info_f(const char* fmt) {
  ygglog_info(fmt);
}
void ygg_log_debug_f(const char* fmt) {
  ygglog_debug(fmt);
  /* yggInfo(fmt); */
}
void ygg_log_error_f(const char* fmt) {
  ygglog_error(fmt);
}

void set_global_comm_f() {
  global_scope_comm = 1;
}
void unset_global_comm_f() {
  global_scope_comm = 0;
}

// Methods for initializing channels
int is_comm_format_array_type_f(const void *x) {
  return is_comm_format_array_type((const comm_t*)x);
}

void* ygg_output_f(const char *name) {
  return (void*)yggOutput(name);
}

void* ygg_input_f(const char *name) {
  return (void*)yggInput(name);
}

void* yggOutputType_f(const char *name, void* datatype) {
  return (void*)yggOutputType(name, (dtype_t*)datatype);
}

void* yggInputType_f(const char *name, void* datatype) {
  return (void*)yggInputType(name, (dtype_t*)datatype);
}

void* yggOutputFmt_f(const char *name, const char *fmt) {
  return (void*)yggOutputFmt(name, fmt);
}

void* yggInputFmt_f(const char *name, const char *fmt) {
  return (void*)yggInputFmt(name, fmt);
}

void* yggAsciiFileOutput_f(const char *name) {
  return (void*)yggAsciiFileOutput(name);
}

void* yggAsciiFileInput_f(const char *name) {
  return (void*)yggAsciiFileInput(name);
}

void* yggAsciiTableOutput_f(const char *name, const char *format_str) {
  return (void*)yggAsciiTableOutput(name, format_str);
}

void* yggAsciiTableInput_f(const char *name) {
  return (void*)yggAsciiTableInput(name);
}

void* yggAsciiArrayOutput_f(const char *name, const char *format_str) {
  return (void*)yggAsciiArrayOutput(name, format_str);
}

void* yggAsciiArrayInput_f(const char *name) {
  return (void*)yggAsciiArrayInput(name);
}

void *yggPlyOutput_f(const char *name) {
  return (void*)yggPlyOutput(name);
}

void *yggPlyInput_f(const char *name) {
  return (void*)yggPlyInput(name);
}

void *yggObjOutput_f(const char *name) {
  return (void*)yggObjOutput(name);
}

void *yggObjInput_f(const char *name) {
  return (void*)yggObjInput(name);
}

void *yggGenericOutput_f(const char *name) {
  return (void*)yggGenericOutput(name);
}

void *yggGenericInput_f(const char *name) {
  return (void*)yggGenericInput(name);
}

void *yggAnyOutput_f(const char *name) {
  return (void*)yggAnyOutput(name);
}

void *yggAnyInput_f(const char *name) {
  return (void*)yggAnyInput(name);
}

void *yggJSONArrayOutput_f(const char *name) {
  return (void*)yggJSONArrayOutput(name);
}

void *yggJSONArrayInput_f(const char *name) {
  return (void*)yggJSONArrayInput(name);
}

void *yggJSONObjectOutput_f(const char *name) {
  return (void*)yggJSONObjectOutput(name);
}

void *yggJSONObjectInput_f(const char *name) {
  return (void*)yggJSONObjectInput(name);
}

void *yggRpcClient_f(const char *name, const char *out_fmt,
		     const char *in_fmt) {
  return (void*)yggRpcClient(name, out_fmt, in_fmt);
}

void *yggRpcServer_f(const char *name, const char *in_fmt,
		     const char *out_fmt) {
  return (void*)yggRpcServer(name, in_fmt, out_fmt);
}

void *yggRpcClientType_f(const char *name, void *outType, void *inType) {
  return (void*)yggRpcClientType(name, (dtype_t*)outType, (dtype_t*)inType);
}
void *yggRpcServerType_f(const char *name, void *inType, void *outType) {
  return (void*)yggRpcServerType(name, (dtype_t*)inType, (dtype_t*)outType);
}

void *yggTimesync_f(const char *name, const char *t_units) {
  return (void*)yggTimesync(name, t_units);
}

// Method for constructing data types
int is_dtype_format_array_f(void* type_struct) {
  return is_dtype_format_array((dtype_t*)type_struct);
}

void *create_dtype_empty_f(const bool use_generic) {
  return (void*)create_dtype_empty(use_generic);
}

void *create_dtype_python_f(void* pyobj, const bool use_generic) {
  return (void*)create_dtype_python((PyObject*)pyobj, use_generic);
}

void *create_dtype_direct_f(const bool use_generic) {
  return (void*)create_dtype_direct(use_generic);
}

void *create_dtype_default_f(const char* type, const bool use_generic) {
  return (void*)create_dtype_default(type, use_generic);
}

void *create_dtype_scalar_f(const char* subtype, const size_t precision,
			    const char* units, const bool use_generic) {
  return (void*)create_dtype_scalar(subtype, precision, units, use_generic);
}

void *create_dtype_1darray_f(const char* subtype, const size_t precision,
			     const size_t length, const char* units,
			     const bool use_generic) {
  return (void*)create_dtype_1darray(subtype, precision, length,
				     units, use_generic);
}

void *create_dtype_ndarray_f(const char* subtype, const size_t precision,
			     const size_t ndim, const size_t* shape,
			     const char* units, const bool use_generic) {
  return (void*)create_dtype_ndarray(subtype, precision, ndim, shape,
				     units, use_generic);
}

void *create_dtype_json_array_f(const size_t nitems, void* items,
				const bool use_generic) {
  return (void*)create_dtype_json_array(nitems, (dtype_t**)items,
					use_generic);
}

void *create_dtype_json_object_f(const size_t nitems, void* keys,
				 void* values, const bool use_generic) {
  return (void*)create_dtype_json_object(nitems, (char**)keys,
					 (dtype_t**)values, use_generic);
}

void *create_dtype_ply_f(const bool use_generic) {
  return (void*)create_dtype_ply(use_generic);
}

void *create_dtype_obj_f(const bool use_generic) {
  return (void*)create_dtype_obj(use_generic);
}

void *create_dtype_format_f(const char *format_str, const int as_array,
			    const bool use_generic) {
  return (void*)create_dtype_format(format_str, as_array, use_generic);
}

void *create_dtype_pyobj_f(const char* type, const bool use_generic) {
  return (void*)create_dtype_pyobj(type, use_generic);
}

void *create_dtype_schema_f(const bool use_generic) {
  return (void*)create_dtype_schema(use_generic);
}

void *create_dtype_any_f(const bool use_generic) {
  return (void*)create_dtype_any(use_generic);
}

// Methods for sending/receiving
int ygg_send_f(const void *yggQ, const char *data, const size_t len) {
  return ygg_send((const comm_t*)yggQ, data, len);
}

int ygg_recv_f(void *yggQ, char *data, const size_t len) {
  return ygg_recv((comm_t*)yggQ, data, len);
}

int ygg_send_var_f(const void *yggQ, int nargs, void *args) {
  if (args == NULL) {
    ygglog_error("ygg_send_var_f: args pointer is NULL.");
    return -1;
  }
  va_list_t ap = init_va_ptrs(nargs, (void**)args);
  return vcommSend((const comm_t*)yggQ, (size_t)nargs, ap);
}

int ygg_recv_var_f(void *yggQ, int nargs, void *args) {
  if (args == NULL) {
    ygglog_error("ygg_recv_var_f: args pointer is NULL.");
    return -1;
  }
  va_list_t ap = init_va_ptrs(nargs, (void**)args);
  ap.for_fortran = 1;
  return vcommRecv((comm_t*)yggQ, 0, (size_t)nargs, ap);
}

int ygg_recv_var_realloc_f(void *yggQ, int nargs, void *args) {
  if (args == NULL) {
    ygglog_error("ygg_recv_var_realloc_f: args pointer is NULL.");
    return -1;
  }
  va_list_t ap = init_va_ptrs(nargs, (void**)args);
  ap.for_fortran = 1;
  return vcommRecv((comm_t*)yggQ, 1, (size_t)nargs, ap);
}

int rpc_send_f(const void *yggQ, int nargs, void *args) {
  return ygg_send_var_f(yggQ, nargs, args);
}

int rpc_recv_f(void *yggQ, int nargs, void *args) {
  return ygg_recv_var_f(yggQ, nargs, args);
}

int rpc_recv_realloc_f(void *yggQ, int nargs, void *args) {
  return ygg_recv_var_realloc_f(yggQ, nargs, args);
}

int rpc_call_f(void *yggQ, int nargs, void *args) {
  if (args == NULL) {
    ygglog_error("rpc_call_f: args pointer is NULL.");
    return -1;
  }
  va_list_t ap = init_va_ptrs(nargs, (void**)args);
  ap.for_fortran = 1;
  return vrpcCallBase((comm_t*)yggQ, 0, (size_t)nargs, ap);
}

int rpc_call_realloc_f(void *yggQ, int nargs, void *args) {
  if (args == NULL) {
    ygglog_error("rpc_call_realloc_f: args pointer is NULL.");
    return -1;
  }
  va_list_t ap = init_va_ptrs(nargs, (void**)args);
  ap.for_fortran = 1;
  return vrpcCallBase((comm_t*)yggQ, 1, (size_t)nargs, ap);
}

// Ply interface
ply_t init_ply_f() {
  return init_ply();
}

void free_ply_f(void* p) {
  ply_t* c_p = (ply_t*)p;
  if (c_p != NULL) {
    free_ply(c_p);
  }
}

ply_t copy_ply_f(ply_t p) {
  return copy_ply(p);
}

void display_ply_indent_f(ply_t p, const char *indent) {
  display_ply_indent(p, indent);
}

void display_ply_f(ply_t p) {
  display_ply(p);
}

// Obj interface
obj_t init_obj_f() {
  return init_obj();
}

void free_obj_f(void* p) {
  obj_t* c_p = (obj_t*)p;
  if (c_p != NULL) {
    free_obj(c_p);
  }
}

obj_t copy_obj_f(obj_t p) {
  return copy_obj(p);
}

void display_obj_indent_f(obj_t p, const char *indent) {
  display_obj_indent(p, indent);
}

void display_obj_f(obj_t p) {
  display_obj(p);
}


// Generic interface
generic_t init_generic_f() {
  return init_generic();
}

generic_t init_generic_array_f() {
  return init_generic_array();
}

generic_t init_generic_map_f() {
  return init_generic_map();
}

generic_t create_generic_f(void* type_class, void* data, size_t nbytes) {
  return create_generic((dtype_t*)type_class, data, nbytes);
}

int free_generic_f(void* x) {
  return destroy_generic((generic_t*)x);
}

generic_t copy_generic_f(generic_t src) {
  return copy_generic(src);
}

int is_generic_init_f(generic_t x) {
  return is_generic_init(x);
}

void display_generic_f(generic_t x) {
  display_generic(x);
}

int add_generic_array_f(generic_t arr, generic_t x) {
  return add_generic_array(arr, x);
}

int set_generic_array_f(generic_t arr, size_t i, generic_t x) {
  return set_generic_array(arr, i, x);
}

int get_generic_array_f(generic_t arr, size_t i, void* x) {
  return get_generic_array(arr, i, (generic_t*)x);
}

int set_generic_object_f(generic_t arr, const char* k, generic_t x) {
  return set_generic_object(arr, k, x);
}

int get_generic_object_f(generic_t arr, const char* k, void* x) {
  return get_generic_object(arr, k, (generic_t*)x);
}

// Python interface
python_t init_python_f() {
  python_t out = init_python();
  return out;
}

void free_python_f(void *x) {
  destroy_python((python_t*)x);
}

python_t copy_python_f(python_t x) {
  python_t out = copy_python(x);
  return out;
}

void display_python_f(python_t x) {
  display_python(x);
}

// Interface for getting/setting generic array elements
size_t generic_array_get_size_f(generic_t x) {
  return generic_array_get_size(x);
}

void* generic_array_get_item_f(generic_t x, const size_t index, const char *type) {
  return generic_array_get_item(x, index, type);
}

int generic_array_get_item_nbytes_f(generic_t x, const size_t index) {
  return generic_array_get_item_nbytes(x, index);
}

void* generic_array_get_scalar_f(generic_t x, const size_t index,
				 const char *subtype, const size_t precision) {
  return generic_array_get_scalar(x, index, subtype, precision);
}

size_t generic_array_get_1darray_f(generic_t x, const size_t index,
				   const char *subtype, const size_t precision,
				   void* data) {
  return generic_array_get_1darray(x, index, subtype, precision, (void**)data);
}

size_t generic_array_get_ndarray_f(generic_t x, const size_t index,
				   const char *subtype, const size_t precision,
				   void* data, void* shape) {
  return generic_array_get_ndarray(x, index, subtype, precision, (void**)data, (size_t**)shape);
}

int generic_array_set_item_f(generic_t x, const size_t index,
			     const char *type, void* value) {
  return generic_array_set_item(x, index, type, value);
}

int generic_array_set_scalar_f(generic_t x, const size_t index,
			       void* value, const char *subtype,
			       const size_t precision,
			       const char* units) {
  return generic_array_set_scalar(x, index, value, subtype, precision, units);
}

int generic_array_set_1darray_f(generic_t x, const size_t index,
				void* value, const char *subtype,
				const size_t precision,
				const size_t length,
				const char* units) {
  return generic_array_set_1darray(x, index, value, subtype, precision, length, units);
}

int generic_array_set_ndarray_f(generic_t x, const size_t index,
				void* data, const char *subtype,
				const size_t precision,
				const size_t ndim, const void* shape,
				const char* units) {
  return generic_array_set_ndarray(x, index, data, subtype, precision,
				   ndim, (const size_t*)shape, units);
}


// Interface for getting/setting generic map elements
size_t generic_map_get_size_f(generic_t x) {
  return generic_map_get_size(x);
}

void* generic_map_get_keys_f(generic_t x, void* n_keys_f, void* key_size_f) {
  char** keys_c = NULL;
  char* keys_f = NULL;
  size_t n_keys = generic_map_get_keys(x, &keys_c);
  size_t i, i_key_size, max_key_size = 0;
  for (i = 0; i < n_keys; i++) {
    i_key_size = strlen(keys_c[i]);
    if (i_key_size > max_key_size) {
      max_key_size = i_key_size;
    }
  }
  max_key_size++;
  keys_f = (char*)malloc(max_key_size * n_keys);
  for (i = 0; i < (n_keys * max_key_size); i++) {
    keys_f[i] = ' ';
  }
  for (i = 0; i < n_keys; i++) {
    memcpy(keys_f + (i * max_key_size), keys_c[i], strlen(keys_c[i]));
    free(keys_c[i]);
  }
  free(keys_c);
  ((size_t*)n_keys_f)[0] = n_keys;
  ((size_t*)key_size_f)[0] = max_key_size;
  return (void*)keys_f;
}

void* generic_map_get_item_f(generic_t x, const char* key,
			     const char *type) {
  return generic_map_get_item(x, key, type);
}

int generic_map_get_item_nbytes_f(generic_t x, const char* key) {
  return generic_map_get_item_nbytes(x, key);
}

void* generic_map_get_scalar_f(generic_t x, const char* key,
			       const char *subtype, const size_t precision) {
  return generic_map_get_scalar(x, key, subtype, precision);
}

size_t generic_map_get_1darray_f(generic_t x, const char* key,
				 const char *subtype, const size_t precision,
				 void* data) {
  return generic_map_get_1darray(x, key, subtype, precision, (void**)data);
}

size_t generic_map_get_ndarray_f(generic_t x, const char* key,
				 const char *subtype, const size_t precision,
				 void* data, void* shape) {
  return generic_map_get_ndarray(x, key, subtype, precision, (void**)data, (size_t**)shape);
}

int generic_map_set_item_f(generic_t x, const char* key,
			   const char* type, void* value) {
  return generic_map_set_item(x, key, type, value);
}

int generic_map_set_scalar_f(generic_t x, const char* key,
			     void* value, const char *subtype,
			     const size_t precision,
			     const char* units) {
  return generic_map_set_scalar(x, key, value, subtype, precision, units);
}

int generic_map_set_1darray_f(generic_t x, const char* key,
			      void* value, const char *subtype,
			      const size_t precision,
			      const size_t length,
			      const char* units) {
  return generic_map_set_1darray(x, key, value, subtype, precision,
				 length, units);
}

int generic_map_set_ndarray_f(generic_t x, const char* key,
			      void* data, const char *subtype,
			      const size_t precision,
			      const size_t ndim, const void* shape,
			      const char* units) {
  return generic_map_set_ndarray(x, key, data, subtype, precision,
				 ndim, (const size_t*)shape, units);
}
