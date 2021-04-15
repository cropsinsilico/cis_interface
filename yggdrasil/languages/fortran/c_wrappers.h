#ifndef YGG_FC_WRAPPERS_H_
#define YGG_FC_WRAPPERS_H_

#include "../C/YggInterface.h"

#ifdef __cplusplus /* If this is a C++ compiler, use C linkage */
extern "C" {
#endif

const int YGG_MSG_MAX_F = YGG_MSG_MAX;

// Utilities
int ygg_init_f();
void ygg_c_free(void *x);
void ygg_log_info_f(const char* fmt);
void ygg_log_debug_f(const char* fmt);
void ygg_log_error_f(const char* fmt);
void set_global_comm();
void unset_global_comm();
// Methods for initializing channels
int is_comm_format_array_type_f(const void *x);
void* ygg_output_f(const char *name);
void* ygg_input_f(const char *name);
void* yggOutputType_f(const char *name, void* datatype);
void* yggInputType_f(const char *name, void* datatype);
void* yggOutputFmt_f(const char *name, const char *fmt);
void* yggInputFmt_f(const char *name, const char *fmt);
void* yggAsciiFileOutput_f(const char *name);
void* yggAsciiFileInput_f(const char *name);
void* yggAsciiTableOutput_f(const char *name, const char *format_str);
void* yggAsciiTableInput_f(const char *name);
void* yggAsciiArrayOutput_f(const char *name, const char *format_str);
void* yggAsciiArrayInput_f(const char *name);
void *yggPlyOutput_f(const char *name);
void *yggPlyInput_f(const char *name);
void *yggObjOutput_f(const char *name);
void *yggObjInput_f(const char *name);
void *yggGenericOutput_f(const char *name);
void *yggGenericInput_f(const char *name);
void *yggAnyOutput_f(const char *name);
void *yggAnyInput_f(const char *name);
void *yggJSONArrayOutput_f(const char *name);
void *yggJSONArrayInput_f(const char *name);
void *yggJSONObjectOutput_f(const char *name);
void *yggJSONObjectInput_f(const char *name);
void *yggRpcClient_f(const char *name, const char *out_fmt,
		     const char *in_fmt);
void *yggRpcServer_f(const char *name, const char *in_fmt,
		     const char *out_fmt);
void *yggRpcClientType_f(const char *name, void *outType, void *inType);
void *yggRpcServerType_f(const char *name, void *inType, void *outType);
void *yggTimesync_f(const char *name, const char *t_units);
// Method for constructing data types
int is_dtype_format_array_f(void* type_struct);
void *create_dtype_empty_f(const bool use_generic);
void *create_dtype_python_f(void* pyobj, const bool use_generic);
void *create_dtype_direct_f(const bool use_generic);
void *create_dtype_default_f(const char* type, const bool use_generic);
void *create_dtype_scalar_f(const char* subtype, const size_t precision,
			    const char* units, const bool use_generic);
void *create_dtype_1darray_f(const char* subtype, const size_t precision,
			     const size_t length, const char* units,
			     const bool use_generic);
void *create_dtype_ndarray_f(const char* subtype, const size_t precision,
			     const size_t ndim, const size_t* shape,
			     const char* units, const bool use_generic);
void *create_dtype_json_array_f(const size_t nitems, void* items,
				const bool use_generic);
void *create_dtype_json_object_f(const size_t nitems, void* keys,
				 void* values, const bool use_generic);
void *create_dtype_ply_f(const bool use_generic);
void *create_dtype_obj_f(const bool use_generic);
void *create_dtype_format_f(const char *format_str, const int as_array,
			    const bool use_generic);
void *create_dtype_pyobj_f(const char* type, const bool use_generic);
void *create_dtype_schema_f(const bool use_generic);
void *create_dtype_any_f(const bool use_generic);
// Methods for sending/receiving
int ygg_send_f(const void *yggQ, const char *data, const size_t len);
int ygg_recv_f(void *yggQ, char *data, const size_t len);
int ygg_send_var_f(const void *yggQ, int nargs, void *args);
int ygg_recv_var_f(void *yggQ, int nargs, void *args);
int ygg_recv_var_realloc_f(void *yggQ, int nargs, void *args);
int rpc_send_f(const void *yggQ, int nargs, void *args);
int rpc_recv_f(void *yggQ, int nargs, void *args);
int rpc_recv_realloc_f(void *yggQ, int nargs, void *args);
int rpc_call_f(void *yggQ, int nargs, void *args);
int rpc_call_realloc_f(void *yggQ, int nargs, void *args);
// Ply interface
ply_t init_ply_f();
void free_ply_f(void* p);
ply_t copy_ply_f(ply_t p);
void display_ply_indent_f(ply_t p, const char *indent);
void display_ply_f(ply_t p);
// Obj interface
obj_t init_obj_f();
void free_obj_f(void* p);
obj_t copy_obj_f(obj_t p);
void display_obj_indent_f(obj_t p, const char *indent);
void display_obj_f(obj_t p);
// Generic interface
generic_t init_generic_f();
generic_t init_generic_array_f();
generic_t init_generic_map_f();
generic_t create_generic_f(void* type_class, void* data, size_t nbytes);
int free_generic_f(void* x);
generic_t copy_generic_f(generic_t src);
int is_generic_init_f(generic_t x);
void display_generic_f(generic_t x);
int add_generic_array_f(generic_t arr, generic_t x);
int set_generic_array_f(generic_t arr, size_t i, generic_t x);
int get_generic_array_f(generic_t arr, size_t i, void *x);
int set_generic_object_f(generic_t arr, const char* k, generic_t x);
int get_generic_object_f(generic_t arr, const char* k, void *x);
// Python interface
python_t init_python_f();
void free_python_f(void *x);
python_t copy_python_f(python_t x);
void display_python_f(python_t x);
// Interface for getting generic array elements
size_t generic_array_get_size_f(generic_t x);
void* generic_array_get_item_f(generic_t x, const size_t index, const char *type);
int generic_array_get_item_nbytes_f(generic_t x, const size_t index);
void* generic_array_get_scalar_f(generic_t x, const size_t index,
				 const char *subtype, const size_t precision);
size_t generic_array_get_1darray_f(generic_t x, const size_t index,
				   const char *subtype, const size_t precision,
				   void* data);
size_t generic_array_get_ndarray_f(generic_t x, const size_t index,
				   const char *subtype, const size_t precision,
				   void* data, void* shape);
size_t generic_map_get_size_f(generic_t x);
void* generic_map_get_keys_f(generic_t x, void* n_keys_f, void* key_size_f);
void* generic_map_get_item_f(generic_t x, const char* key,
			   const char *type);
int generic_map_get_item_nbytes_f(generic_t x, const char* key);
void* generic_map_get_scalar_f(generic_t x, const char* key,
			     const char *subtype, const size_t precision);
size_t generic_map_get_1darray_f(generic_t x, const char* key,
				 const char *subtype, const size_t precision,
				 void* data);
size_t generic_map_get_ndarray_f(generic_t x, const char* key,
				 const char *subtype, const size_t precision,
				 void* data, void* shape);
// Interface for setting generic array elements
int generic_array_set_item_f(generic_t x, const size_t index,
			     const char *type, void* value);
int generic_array_set_scalar_f(generic_t x, const size_t index,
			       void* value, const char *subtype,
			       const size_t precision,
			       const char* units);
int generic_array_set_1darray_f(generic_t x, const size_t index,
				void* value, const char *subtype,
				const size_t precision,
				const size_t length,
				const char* units);
int generic_array_set_ndarray_f(generic_t x, const size_t index,
				void* data, const char *subtype,
				const size_t precision,
				const size_t ndim, const void* shape,
				const char* units);
// Interface for setting generic map elements
int generic_map_set_item_f(generic_t x, const char* key,
			   const char* type, void* value);
int generic_map_set_scalar_f(generic_t x, const char* key,
			     void* value, const char *subtype,
			     const size_t precision,
			     const char* units);
int generic_map_set_1darray_f(generic_t x, const char* key,
			      void* value, const char *subtype,
			      const size_t precision,
			      const size_t length,
			      const char* units);
int generic_map_set_ndarray_f(generic_t x, const char* key,
			      void* data, const char *subtype,
			      const size_t precision,
			      const size_t ndim, const void* shape,
			      const char* units);

#ifdef __cplusplus /* If this is a C++ compiler, end C linkage */
}
#endif


#endif /*YGG_FC_WRAPPERS_H_*/
