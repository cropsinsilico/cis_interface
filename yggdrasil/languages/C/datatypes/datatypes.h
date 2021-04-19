#ifndef DATATYPES_H_
#define DATATYPES_H_

#include <stdbool.h>

#include "../tools.h"
#include "PlyDict.h"
#include "ObjDict.h"

#define MSG_HEAD_SEP "YGG_MSG_HEAD"
/*! @brief Size of COMM buffer. */
#define COMMBUFFSIZ 2000
#define FMT_LEN 100


#ifdef __cplusplus /* If this is a C++ compiler, use C linkage */
extern "C" {
#endif

static char prefix_char = '#';
#ifdef _OPENMP
#pragma omp threadprivate(prefix_char)
#endif
  
/*! @brief Bit flags. */
#define HEAD_FLAG_VALID      0x00000001  //!< Set if the header is valid.
#define HEAD_FLAG_MULTIPART  0x00000002  //!< Set if the header is for a multipart message
#define HEAD_TYPE_IN_DATA    0x00000004  //!< Set if the type is stored with the data during serialization
#define HEAD_AS_ARRAY        0x00000008  //!< Set if messages will be serialized arrays

/*! @brief C-friendly definition of MetaschemaType. */
typedef struct dtype_t {
  char type[COMMBUFFSIZ]; //!< Type name
  bool use_generic; //!< Flag for empty dtypes to specify generic in/out
  void *obj; //!< MetaschemaType Pointer
} dtype_t;

/*! @brief C-friendly defintion of YggGeneric. */
typedef struct generic_t {
  char prefix; //!< Prefix character for limited verification.
  void *obj; //!< Pointer to YggGeneric class.
} generic_t;

/*! @brief C-friendly definition of vector object. */
typedef generic_t json_array_t;

/*! @brief C-friendly definition of map object. */
typedef generic_t json_object_t;

/*! @brief C-friendly definition of schema object. */
typedef generic_t schema_t;

/*! @brief C-friendly defintion of Python class object. */
typedef python_t python_class_t;

/*! @brief C-friendly defintion of Python function object. */
typedef python_t python_function_t;

/*! @brief C-friendly defintion of Python instance object. */
typedef generic_t python_instance_t;

/*! @brief Macro wrapping call to PyObject_CallFunction. */
#define call_python(x, format, ...) PyObject_CallFunction(x.obj, format, __VA_ARGS__)

/*! @brief Aliases to allow differentiation in parsing model definition. */
typedef char* unicode_t;
typedef char* string_t;
typedef char* bytes_t;
  
/*! @brief Header information passed by comms for multipart messages. */
typedef struct comm_head_t {
  size_t bodysiz; //!< Size of body.
  size_t bodybeg; //!< Start of body in header.
  int flags; //!< Bit flags encoding the status of the header.
  int nargs_populated; //!< Number of arguments populated during deserialization.
  //
  size_t size; //!< Size of incoming message.
  char address[COMMBUFFSIZ]; //!< Address that message will comm in on.
  char id[COMMBUFFSIZ]; //!< Unique ID associated with this message.
  char response_address[COMMBUFFSIZ]; //!< Response address.
  char request_id[COMMBUFFSIZ]; //!< Request id.
  char zmq_reply[COMMBUFFSIZ]; //!< Reply address for ZMQ sockets.
  char zmq_reply_worker[COMMBUFFSIZ]; //!< Reply address for worker socket.
  char model[COMMBUFFSIZ]; //!< Name of model that sent the header.
  // These should be removed once JSON fully implemented
  int serializer_type; //!< Code indicating the type of serializer.
  char format_str[COMMBUFFSIZ]; //!< Format string for serializer.
  char field_names[COMMBUFFSIZ]; //!< String containing field names.
  char field_units[COMMBUFFSIZ]; //!< String containing field units.
  //
  dtype_t* dtype; //!< Type structure.
} comm_head_t;


/*!
  @brief C wrapper for the C++ type_from_doc function.
  @param type_doc void* Pointer to const rapidjson::Value type doc.
  @returns void* Pointer to MetaschemaType class.
 */
void* type_from_doc_c(const void* type_doc, const bool use_generic);


/*!
  @brief C wrapper for the C++ type_from_pyobj function.
  @param type_doc void* Pointer to const rapidjson::Value type doc.
  @returns void* Pointer to MetaschemaType class.
 */
void* type_from_pyobj_c(PyObject* pyobj, const bool use_generic);


/*!
  @brief Determine if a datatype was created from a format.
  @params[in] type_struct dtype_t* Datatype structure.
  @returns int 1 if the datatype was created from a format, 0 if it
  was not, -1 if there is an error.
 */
int is_dtype_format_array(dtype_t* type_struct);
  

/*!
  @brief Initialize an empty generic object.
  @returns generic_t New generic object structure.
 */
generic_t init_generic();
  
/*!
  @brief Initialize an empty array of mixed types with generic wrappers.
  @returns generic_t New generic object structure containing an empty array.
*/
generic_t init_generic_array();

/*!
  @brief Initialize an empty map (JSON object) of mixed types with generic wrappers.
  @returns generic_t New generic object structure contaiing an empty map (JSON object).
 */
generic_t init_generic_map();

/*!
  @brief Determine if the provided character matches the required generic prefix char.
  @param[in] x char Character to check.
  @returns int 1 if the character is the correct prefix, 0 otherwise.
 */
int is_generic_flag(char x);


/*!
  @brief Determine if a generic structure is initialized.
  @param[in] x generic_t Generic structure to test.
  @returns int 1 if the structure is initialized, 0 otherwise.
 */
int is_generic_init(generic_t x);


/*!
  @brief Create a generic object from the provided information.
  @param[in] type_class dtype_t* Type structure/class.
  @param[in] data void* Pointer to data.
  @param[in] nbytes size_t Size of data.
  @returns generic_t Pointer to new generic object structure.
 */
generic_t create_generic(dtype_t* type_class, void* data, size_t nbytes);

  
/*!
  @brief Destroy a generic object.
  @param[in] x generic_t* Pointer to generic object structure to destory.
  @returns int -1 if unsuccessful, 0 otherwise.
 */
int destroy_generic(generic_t* x);


/*!
  @brief Copy data from one generic object to the other.
  @param[in] src generic_t Generic structure that data should be copied from.
  @returns generic_t Copied structure.
 */
generic_t copy_generic(generic_t src);


/*!
  @brief Display information about the generic type.
  @param[in] x generic_t* Wrapper for generic object.
 */
void display_generic(generic_t x);

  
/*!
  @brief Return the recovered generic structure if one is present in
  the variable argument list.
  @param[in] nargs size_t Number of argument present in ap.
  @param[in] ap va_list_t Variable argument list.
  @returns generic_t Generic structure if one is present.
 */
generic_t get_generic_va(size_t nargs, va_list_t ap);


/*!
  @brief Return the recovered generic structure if one is present in
  the variable argument list.
  @param[in] nargs size_t Number of argument present in ap.
  @param[in] ap va_list_t Variable argument list.
  @returns generic_t* Generic structure if one is present, NULL otherwise.
 */
generic_t* get_generic_va_ptr(size_t nargs, va_list_t ap);


/*!
  @brief Return the recovered generic structure if one is present in
  the variable argument list by removing it.
  @param[in] nargs size_t* Pointer to number of arguments present in ap
  that will be decremented by 1.
  @param[in] ap va_list_t* Pointer to variable argument list.
  @returns generic_t Generic structure if one is present.
 */
generic_t pop_generic_va(size_t* nargs, va_list_t* ap);


/*!
  @brief Return the recovered generic structure if one is present in
  the variable argument list by removing it.
  @param[in] nargs size_t* Pointer to number of arguments present in ap
  that will be decremented by 1.
  @param[in] ap va_list_t* Pointer to variable argument list.
  @returns generic_t* Generic structure if one is present, NULL otherwise.
 */
generic_t* pop_generic_va_ptr(size_t* nargs, va_list_t* ap);

/*!
  @brief Add an element to the end of an array of generic elements.
  @param[in] arr generic_t Array to add element to.
  @param[in] x generic_t Element to add.
  @returns int Flag that is 1 if there is an error and 0 otherwise.
 */
int add_generic_array(generic_t arr, generic_t x);


/*!
  @brief Set an element in the array at a given index to a new value.
  @param[in] arr generic_t Array to add element to.
  @param[in] i size_t Index where element should be added.
  @param[in] x generic_t Element to add.
  @returns int Flag that is 1 if there is an error and 0 otherwise.
 */
int set_generic_array(generic_t arr, size_t i, generic_t x);


/*!
  @brief Get an element from an array.
  @param[in] arr generic_t Array to get element from.
  @param[in] i size_t Index of element to get.
  @param[out] x generic_t* Pointer to address where element should be
  stored.
  @returns int Flag that is 1 if there is an error and 0 otherwise.
 */
int get_generic_array(generic_t arr, size_t i, generic_t *x);


/*!
  @brief Set an element in the object at for a given key to a new value.
  @param[in] arr generic_t Object to add element to.
  @param[in] k const char* Key where element should be added.
  @param[in] x generic_t Element to add.
  @returns int Flag that is 1 if there is an error and 0 otherwise.
 */
int set_generic_object(generic_t arr, const char* k, generic_t x);


/*!
  @brief Get an element from an object.
  @param[in] arr generic_t Object to get element from.
  @param[in] k const char* Key of element to return.
  @param[out] x generic_t* Pointer to address where element should be
  stored.
  @returns int Flag that is 1 if there is an error and 0 otherwise.
 */
int get_generic_object(generic_t arr, const char* k, generic_t *x);


/*!
  @brief Get the number of elements in an array object.
  @param[in] x generic_t Generic object that is presumed to contain an array.
  @returns size_t Number of elements in array.
 */
size_t generic_array_get_size(generic_t x);

/*!
  @brief Get an item from an array for types that don't require additional parameters.
  @param[in] x generic_t Generic object that is presumed to contain an array.
  @param[in] index size_t Index for value that should be returned.
  @param[in] type const char* Type of value expected.
  @returns void* Pointer to data for array item.
 */
void* generic_array_get_item(generic_t x, const size_t index,
			   const char *type);
int generic_array_get_item_nbytes(generic_t x, const size_t index);
bool generic_array_get_bool(generic_t x, const size_t index);
int generic_array_get_integer(generic_t x, const size_t index);
void* generic_array_get_null(generic_t x, const size_t index);
double generic_array_get_number(generic_t x, const size_t index);
char* generic_array_get_string(generic_t x, const size_t index);
generic_t generic_array_get_object(generic_t x, const size_t index);
generic_t generic_array_get_array(generic_t x, const size_t index);
char* generic_array_get_direct(generic_t x, const size_t index);
ply_t generic_array_get_ply(generic_t x, const size_t index);
obj_t generic_array_get_obj(generic_t x, const size_t index);
python_t generic_array_get_python_class(generic_t x, const size_t index);
python_t generic_array_get_python_function(generic_t x, const size_t index);
schema_t generic_array_get_schema(generic_t x, const size_t index);
generic_t generic_array_get_any(generic_t x, const size_t index);

  
/*!
  @brief Get a scalar value from an array.
  @param[in] x generic_t Generic object that is presumed to contain an array.
  @param[in] index size_t Index for value that should be returned.
  @param[in] subtype const char* Subtype of scalar expected.
  @param[in] precision const int Precision of scalar that is expected.
  @returns void* Pointer to scalar data.
 */
void* generic_array_get_scalar(generic_t x, const size_t index,
			       const char *subtype, const size_t precision);
int8_t generic_array_get_int8(generic_t x, const size_t index);
int16_t generic_array_get_int16(generic_t x, const size_t index);
int32_t generic_array_get_int32(generic_t x, const size_t index);
int64_t generic_array_get_int64(generic_t x, const size_t index);
uint8_t generic_array_get_uint8(generic_t x, const size_t index);
uint16_t generic_array_get_uint16(generic_t x, const size_t index);
uint32_t generic_array_get_uint32(generic_t x, const size_t index);
uint64_t generic_array_get_uint64(generic_t x, const size_t index);
float generic_array_get_float(generic_t x, const size_t index);
double generic_array_get_double(generic_t x, const size_t index);
long double generic_array_get_long_double(generic_t x, const size_t index);
complex_float_t generic_array_get_complex_float(generic_t x, const size_t index);
complex_double_t generic_array_get_complex_double(generic_t x, const size_t index);
complex_long_double_t generic_array_get_complex_long_double(generic_t x, const size_t index);
char* generic_array_get_bytes(generic_t x, const size_t index);
char* generic_array_get_unicode(generic_t x, const size_t index);
  
/*!
  @brief Get a 1d array value from an array.
  @param[in] x generic_t Generic object that is presumed to contain an array.
  @param[in] index size_t Index for value that should be returned.
  @param[in] subtype const char* Subtype of array expected.
  @param[in] precision const size_t Precision of array that is expected.
  @param[out] data void** Pointer to pointer that should be reallocated to store the data.
  @returns size_t Number of elements in the data.
 */
size_t generic_array_get_1darray(generic_t x, const size_t index,
				 const char *subtype, const size_t precision,
				 void** data);
size_t generic_array_get_1darray_int8(generic_t x, const size_t index, int8_t** data);
size_t generic_array_get_1darray_int16(generic_t x, const size_t index, int16_t** data);
size_t generic_array_get_1darray_int32(generic_t x, const size_t index, int32_t** data);
size_t generic_array_get_1darray_int64(generic_t x, const size_t index, int64_t** data);
size_t generic_array_get_1darray_uint8(generic_t x, const size_t index, uint8_t** data);
size_t generic_array_get_1darray_uint16(generic_t x, const size_t index, uint16_t** data);
size_t generic_array_get_1darray_uint32(generic_t x, const size_t index, uint32_t** data);
size_t generic_array_get_1darray_uint64(generic_t x, const size_t index, uint64_t** data);
size_t generic_array_get_1darray_float(generic_t x, const size_t index, float** data);
size_t generic_array_get_1darray_double(generic_t x, const size_t index, double** data);
size_t generic_array_get_1darray_long_double(generic_t x, const size_t index, long double** data);
size_t generic_array_get_1darray_complex_float(generic_t x, const size_t index, complex_float_t** data);
size_t generic_array_get_1darray_complex_double(generic_t x, const size_t index, complex_double_t** data);
size_t generic_array_get_1darray_complex_long_double(generic_t x, const size_t index, complex_long_double_t** data);
size_t generic_array_get_1darray_bytes(generic_t x, const size_t index, char** data);
size_t generic_array_get_1darray_unicode(generic_t x, const size_t index, char** data);
  
/*!
  @brief Get a nd array value from an array.
  @param[in] x generic_t Generic object that is presumed to contain an array.
  @param[in] index size_t Index for value that should be returned.
  @param[in] subtype const char* Subtype of array expected.
  @param[in] precision const size_t Precision of array that is expected.
  @param[out] data void** Pointer to array that should be reallocated to store the data.
  @param[out] shape size_t** Pointer to array that should be reallocated to store the array shape in each dimension.
  @returns size_t Number of dimensions in the array.
 */
size_t generic_array_get_ndarray(generic_t x, const size_t index,
				 const char *subtype, const size_t precision,
				 void** data, size_t** shape);
size_t generic_array_get_ndarray_int8(generic_t x, const size_t index, int8_t** data, size_t** shape);
size_t generic_array_get_ndarray_int16(generic_t x, const size_t index, int16_t** data, size_t** shape);
size_t generic_array_get_ndarray_int32(generic_t x, const size_t index, int32_t** data, size_t** shape);
size_t generic_array_get_ndarray_int64(generic_t x, const size_t index, int64_t** data, size_t** shape);
size_t generic_array_get_ndarray_uint8(generic_t x, const size_t index, uint8_t** data, size_t** shape);
size_t generic_array_get_ndarray_uint16(generic_t x, const size_t index, uint16_t** data, size_t** shape);
size_t generic_array_get_ndarray_uint32(generic_t x, const size_t index, uint32_t** data, size_t** shape);
size_t generic_array_get_ndarray_uint64(generic_t x, const size_t index, uint64_t** data, size_t** shape);
size_t generic_array_get_ndarray_float(generic_t x, const size_t index, float** data, size_t** shape);
size_t generic_array_get_ndarray_double(generic_t x, const size_t index, double** data, size_t** shape);
size_t generic_array_get_ndarray_long_double(generic_t x, const size_t index, long double** data, size_t** shape);
size_t generic_array_get_ndarray_complex_float(generic_t x, const size_t index, complex_float_t** data, size_t** shape);
size_t generic_array_get_ndarray_complex_double(generic_t x, const size_t index, complex_double_t** data, size_t** shape);
size_t generic_array_get_ndarray_complex_long_double(generic_t x, const size_t index, complex_long_double_t** data, size_t** shape);
size_t generic_array_get_ndarray_bytes(generic_t x, const size_t index, char** data, size_t** shape);
size_t generic_array_get_ndarray_unicode(generic_t x, const size_t index, char** data, size_t** shape);
  
/*!
  @brief Get the number of elements in an map object.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @returns size_t Number of elements in map.
 */
size_t generic_map_get_size(generic_t x);
/*!
  @brief Determine if a map object has a certain key.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[in] key char* Key to check for.
  @returns int 1 if the key is present, 0 otherwise.
 */
int generic_map_has_key(generic_t x, char* key);
/*!
  @brief Get the keys in a map object.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[out] keys char*** Pointer to memory where array of keys should be stored.
  @returns size_t Number of keys in map.
 */
size_t generic_map_get_keys(generic_t x, char*** keys);
/*!
  @brief Get an item from a map for types that don't require additional parameters.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[in] key const char* Key string for value that should be returned.
  @param[in] type const char* Type of value expected.
  @returns void* Pointer to data for map item.
 */
void* generic_map_get_item(generic_t x, const char* key,
			   const char *type);
int generic_map_get_item_nbytes(generic_t x, const char* key);
bool generic_map_get_bool(generic_t x, const char* key);
int generic_map_get_integer(generic_t x, const char* key);
void* generic_map_get_null(generic_t x, const char* key);
double generic_map_get_number(generic_t x, const char* key);
char* generic_map_get_string(generic_t x, const char* key);
generic_t generic_map_get_object(generic_t x, const char* key);
generic_t generic_map_get_array(generic_t x, const char* key);
char* generic_map_get_direct(generic_t x, const char* key);
ply_t generic_map_get_ply(generic_t x, const char* key);
obj_t generic_map_get_obj(generic_t x, const char* key);
python_t generic_map_get_python_class(generic_t x, const char* key);
python_t generic_map_get_python_function(generic_t x, const char* key);
schema_t generic_map_get_schema(generic_t x, const char* key);
generic_t generic_map_get_any(generic_t x, const char* key);
  
/*!
  @brief Get a scalar value from a map.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[in] key const char* Key string for value that should be returned.
  @param[in] subtype const char* Subtype of scalar expected.
  @param[in] precision const int Precision of scalar that is expected.
  @returns void* Pointer to scalar data.
 */
void* generic_map_get_scalar(generic_t x, const char* key,
			     const char *subtype, const size_t precision);
int8_t generic_map_get_int8(generic_t x, const char* key);
int16_t generic_map_get_int16(generic_t x, const char* key);
int32_t generic_map_get_int32(generic_t x, const char* key);
int64_t generic_map_get_int64(generic_t x, const char* key);
uint8_t generic_map_get_uint8(generic_t x, const char* key);
uint16_t generic_map_get_uint16(generic_t x, const char* key);
uint32_t generic_map_get_uint32(generic_t x, const char* key);
uint64_t generic_map_get_uint64(generic_t x, const char* key);
float generic_map_get_float(generic_t x, const char* key);
double generic_map_get_double(generic_t x, const char* key);
long double generic_map_get_long_double(generic_t x, const char* key);
complex_float_t generic_map_get_complex_float(generic_t x, const char* key);
complex_double_t generic_map_get_complex_double(generic_t x, const char* key);
complex_long_double_t generic_map_get_complex_long_double(generic_t x, const char* key);
char* generic_map_get_bytes(generic_t x, const char* key);
char* generic_map_get_unicode(generic_t x, const char* key);
  
/*!
  @brief Get a 1d array value from a map.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[in] key const char* Key string for value that should be returned.
  @param[in] subtype const char* Subtype of array expected.
  @param[in] precision const size_t Precision of array that is expected.
  @param[out] data void** Pointer to pointer that should be reallocated to store the data.
  @returns size_t Number of elements in the data.
 */
size_t generic_map_get_1darray(generic_t x, const char* key,
			       const char *subtype, const size_t precision,
			       void** data);
size_t generic_map_get_1darray_int8(generic_t x, const char* key, int8_t** data);
size_t generic_map_get_1darray_int16(generic_t x, const char* key, int16_t** data);
size_t generic_map_get_1darray_int32(generic_t x, const char* key, int32_t** data);
size_t generic_map_get_1darray_int64(generic_t x, const char* key, int64_t** data);
size_t generic_map_get_1darray_uint8(generic_t x, const char* key, uint8_t** data);
size_t generic_map_get_1darray_uint16(generic_t x, const char* key, uint16_t** data);
size_t generic_map_get_1darray_uint32(generic_t x, const char* key, uint32_t** data);
size_t generic_map_get_1darray_uint64(generic_t x, const char* key, uint64_t** data);
size_t generic_map_get_1darray_float(generic_t x, const char* key, float** data);
size_t generic_map_get_1darray_double(generic_t x, const char* key, double** data);
size_t generic_map_get_1darray_long_double(generic_t x, const char* key, long double** data);
size_t generic_map_get_1darray_complex_float(generic_t x, const char* key, complex_float_t** data);
size_t generic_map_get_1darray_complex_double(generic_t x, const char* key, complex_double_t** data);
size_t generic_map_get_1darray_complex_long_double(generic_t x, const char* key, complex_long_double_t** data);
size_t generic_map_get_1darray_bytes(generic_t x, const char* key, char** data);
size_t generic_map_get_1darray_unicode(generic_t x, const char* key, char** data);
  
/*!
  @brief Get a nd array value from a map.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[in] key const char* Key string for value that should be returned.
  @param[in] subtype const char* Subtype of array expected.
  @param[in] precision const size_t Precision of array that is expected.
  @param[out] data void** Pointer to array that should be reallocated to store the data.
  @param[out] shape size_t** Pointer to array that should be reallocated to store the array shape in each dimension.
  @returns size_t Number of dimensions in the array.
 */
size_t generic_map_get_ndarray(generic_t x, const char* key,
			       const char *subtype, const size_t precision,
			       void** data, size_t** shape);
size_t generic_map_get_ndarray_int8(generic_t x, const char* key, int8_t** data, size_t** shape);
size_t generic_map_get_ndarray_int16(generic_t x, const char* key, int16_t** data, size_t** shape);
size_t generic_map_get_ndarray_int32(generic_t x, const char* key, int32_t** data, size_t** shape);
size_t generic_map_get_ndarray_int64(generic_t x, const char* key, int64_t** data, size_t** shape);
size_t generic_map_get_ndarray_uint8(generic_t x, const char* key, uint8_t** data, size_t** shape);
size_t generic_map_get_ndarray_uint16(generic_t x, const char* key, uint16_t** data, size_t** shape);
size_t generic_map_get_ndarray_uint32(generic_t x, const char* key, uint32_t** data, size_t** shape);
size_t generic_map_get_ndarray_uint64(generic_t x, const char* key, uint64_t** data, size_t** shape);
size_t generic_map_get_ndarray_float(generic_t x, const char* key, float** data, size_t** shape);
size_t generic_map_get_ndarray_double(generic_t x, const char* key, double** data, size_t** shape);
size_t generic_map_get_ndarray_long_double(generic_t x, const char* key, long double** data, size_t** shape);
size_t generic_map_get_ndarray_complex_float(generic_t x, const char* key, complex_float_t** data, size_t** shape);
size_t generic_map_get_ndarray_complex_double(generic_t x, const char* key, complex_double_t** data, size_t** shape);
size_t generic_map_get_ndarray_complex_long_double(generic_t x, const char* key, complex_long_double_t** data, size_t** shape);
size_t generic_map_get_ndarray_bytes(generic_t x, const char* key, char** data, size_t** shape);
size_t generic_map_get_ndarray_unicode(generic_t x, const char* key, char** data, size_t** shape);

/*!
  @brief Set an item in an array for types that don't require additional parameters.
  @param[in] x generic_t Generic object that is presumed to contain an array.
  @param[in] index size_t Index for value that should be set.
  @param[in] type const char* Type of value being set.
  @param[in] value void* Pointer to data that item should be set to.
  @returns int -1 if there is an error, 0 otherwise.
 */
int generic_array_set_item(generic_t x, const size_t index,
			   const char *type, void* value);
int generic_array_set_bool(generic_t x, const size_t index,
			   bool value);
int generic_array_set_integer(generic_t x, const size_t index,
			      int value);
int generic_array_set_null(generic_t x, const size_t index,
			   void* value);
int generic_array_set_number(generic_t x, const size_t index,
			     double value);
int generic_array_set_string(generic_t x, const size_t index,
			     char* value);
int generic_array_set_object(generic_t x, const size_t index,
			     generic_t value);
int generic_array_set_map(generic_t x, const size_t index,
			  generic_t value);
int generic_array_set_array(generic_t x, const size_t index,
			    generic_t value);
int generic_array_set_direct(generic_t x, const size_t index,
			     char* value);
int generic_array_set_ply(generic_t x, const size_t index,
			  ply_t value);
int generic_array_set_obj(generic_t x, const size_t index,
			  obj_t value);
int generic_array_set_python_class(generic_t x, const size_t index,
				   python_t value);
int generic_array_set_python_function(generic_t x, const size_t index,
				      python_t value);
int generic_array_set_schema(generic_t x, const size_t index,
			     schema_t value);
int generic_array_set_any(generic_t x, const size_t index,
			  generic_t value);

/*!
  @brief Set a scalar value in an array.
  @param[in] x generic_t Generic object that is presumed to contain an array.
  @param[in] index size_t Index for value that should be set.
  @param[in] value void* Pointer to scalar data.
  @param[in] subtype const char* Subtype of scalar in value.
  @param[in] precision const int Precision of scalar in value.
  @param[in] units const char* Units of value.
  @returns int -1 if there is an error, 0 otherwise.
 */
int generic_array_set_scalar(generic_t x, const size_t index,
			     void* value, const char *subtype,
			     const size_t precision,
			     const char* units);
int generic_array_set_int8(generic_t x, const size_t index, int8_t value, const char* units);
int generic_array_set_int16(generic_t x, const size_t index, int16_t value, const char* units);
int generic_array_set_int32(generic_t x, const size_t index, int32_t value, const char* units);
int generic_array_set_int64(generic_t x, const size_t index, int64_t value, const char* units);
int generic_array_set_uint8(generic_t x, const size_t index, uint8_t value, const char* units);
int generic_array_set_uint16(generic_t x, const size_t index, uint16_t value, const char* units);
int generic_array_set_uint32(generic_t x, const size_t index, uint32_t value, const char* units);
int generic_array_set_uint64(generic_t x, const size_t index, uint64_t value, const char* units);
int generic_array_set_float(generic_t x, const size_t index, float value, const char* units);
int generic_array_set_double(generic_t x, const size_t index, double value, const char* units);
int generic_array_set_long_double(generic_t x, const size_t index, long double value, const char* units);
int generic_array_set_complex_float(generic_t x, const size_t index,
				    complex_float_t value,
				    const char* units);
int generic_array_set_complex_double(generic_t x, const size_t index,
				     complex_double_t value,
				     const char* units);
int generic_array_set_complex_long_double(generic_t x, const size_t index,
					  complex_long_double_t value,
					  const char* units);
int generic_array_set_bytes(generic_t x, const size_t index, char* value, const char* units);
int generic_array_set_unicode(generic_t x, const size_t index, char* value, const char* units);

/*!
  @brief Set a 1d array value in an array.
  @param[in] x generic_t Generic object that is presumed to contain an array.
  @param[in] index size_t Index for value that should be set.
  @param[in] value void* Pointer to array data.
  @param[in] subtype const char* Subtype of array expected.
  @param[in] precision const size_t Precision of array that is expected.
  @param[in] length const size_t Number of elements in value.
  @param[in] units const char* Units of value.
  @returns int -1 if there is an error, 0 otherwise.
 */
int generic_array_set_1darray(generic_t x, const size_t index,
			      void* value, const char *subtype,
			      const size_t precision,
			      const size_t length,
			      const char* units);
int generic_array_set_1darray_int8(generic_t x, const size_t index,
				   int8_t* value, const size_t length,
				   const char* units);
int generic_array_set_1darray_int16(generic_t x, const size_t index,
				    int16_t* value, const size_t length,
				    const char* units);
int generic_array_set_1darray_int32(generic_t x, const size_t index,
				    int32_t* value, const size_t length,
				    const char* units);
int generic_array_set_1darray_int64(generic_t x, const size_t index,
				    int64_t* value, const size_t length,
				    const char* units);
int generic_array_set_1darray_uint8(generic_t x, const size_t index,
				    uint8_t* value, const size_t length,
				    const char* units);
int generic_array_set_1darray_uint16(generic_t x, const size_t index,
				     uint16_t* value, const size_t length,
				     const char* units);
int generic_array_set_1darray_uint32(generic_t x, const size_t index,
				     uint32_t* value, const size_t length,
				     const char* units);
int generic_array_set_1darray_uint64(generic_t x, const size_t index,
				     uint64_t* value, const size_t length,
				     const char* units);
int generic_array_set_1darray_float(generic_t x, const size_t index,
				    float* value, const size_t length,
				    const char* units);
int generic_array_set_1darray_double(generic_t x, const size_t index,
				     double* value, const size_t length,
				     const char* units);
int generic_array_set_1darray_long_double(generic_t x, const size_t index, long double* value, const size_t length, const char* units);
int generic_array_set_1darray_complex_float(generic_t x, const size_t index, complex_float_t* value, const size_t length, const char* units);
int generic_array_set_1darray_complex_double(generic_t x, const size_t index, complex_double_t* value, const size_t length, const char* units);
int generic_array_set_1darray_complex_long_double(generic_t x, const size_t index, complex_long_double_t* value, const size_t length, const char* units);
int generic_array_set_1darray_bytes(generic_t x, const size_t index,
				    char** value, const size_t length,
				    const char* units);
int generic_array_set_1darray_unicode(generic_t x, const size_t index,
				      char** value, const size_t length,
				      const char* units);
  
/*!
  @brief Set a nd array value from an array.
  @param[in] x generic_t Generic object that is presumed to contain an array.
  @param[in] index size_t Index for value that should be set.
  @param[in] value void* Pointer to array data.
  @param[in] subtype const char* Subtype of array in value.
  @param[in] precision const size_t Precision of array that is in value.
  @param[in] ndim size_t Number of dimensions in the array.
  @param[in] shape size_t* Pointer to array containing the size of
  the array in each dimension.
  @returns int -1 if there is an error, 0 otherwise.
 */
int generic_array_set_ndarray(generic_t x, const size_t index,
			      void* data, const char *subtype,
			      const size_t precision,
			      const size_t ndim, const size_t* shape,
			      const char* units);
int generic_array_set_ndarray_int8(generic_t x, const size_t index,
				   int8_t* data, const size_t ndim,
				   const size_t* shape,
				   const char* units);
int generic_array_set_ndarray_int16(generic_t x, const size_t index,
				    int16_t* data, const size_t ndim,
				    const size_t* shape,
				    const char* units);
int generic_array_set_ndarray_int32(generic_t x, const size_t index,
				    int32_t* data, const size_t ndim,
				    const size_t* shape,
				    const char* units);
int generic_array_set_ndarray_int64(generic_t x, const size_t index,
				    int64_t* data, const size_t ndim,
				    const size_t* shape,
				    const char* units);
int generic_array_set_ndarray_uint8(generic_t x, const size_t index,
				    uint8_t* data, const size_t ndim,
				    const size_t* shape,
				    const char* units);
int generic_array_set_ndarray_uint16(generic_t x, const size_t index,
				     uint16_t* data, const size_t ndim,
				     const size_t* shape,
				     const char* units);
int generic_array_set_ndarray_uint32(generic_t x, const size_t index,
				     uint32_t* data, const size_t ndim,
				     const size_t* shape,
				     const char* units);
int generic_array_set_ndarray_uint64(generic_t x, const size_t index,
				     uint64_t* data, const size_t ndim,
				     const size_t* shape,
				     const char* units);
int generic_array_set_ndarray_float(generic_t x, const size_t index,
				    float* data, const size_t ndim,
				    const size_t* shape,
				    const char* units);
int generic_array_set_ndarray_double(generic_t x, const size_t index,
				     double* data, const size_t ndim,
				     const size_t* shape,
				     const char* units);
int generic_array_set_ndarray_long_double(generic_t x, const size_t index, long double* data, const size_t ndim, const size_t* shape, const char* units);
int generic_array_set_ndarray_complex_float(generic_t x, const size_t index, complex_float_t* data, const size_t ndim, const size_t* shape, const char* units);
int generic_array_set_ndarray_complex_double(generic_t x, const size_t index, complex_double_t* data, const size_t ndim, const size_t* shape, const char* units);
int generic_array_set_ndarray_complex_long_double(generic_t x, const size_t index, complex_long_double_t* data, const size_t ndim, const size_t* shape, const char* units);
int generic_array_set_ndarray_bytes(generic_t x, const size_t index, char** data, const size_t ndim, const size_t* shape, const char* units);
int generic_array_set_ndarray_unicode(generic_t x, const size_t index, char** data, const size_t ndim, const size_t* shape, const char* units);
  
  
/*!
  @brief Set an item from a map for types that don't require additional parameters.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[in] key const char* Key string for value that should be set.
  @param[in] type const char* Type of value being set.
  @param[in] value void* Pointer to data that item should be set to.
  @returns int -1 if there is an error, 0 otherwise.
 */
int generic_map_set_item(generic_t x, const char* key,
			 const char* type, void* value);
int generic_map_set_bool(generic_t x, const char* key,
			 bool value);
int generic_map_set_integer(generic_t x, const char* key,
			    int value);
int generic_map_set_null(generic_t x, const char* key,
			 void* value);
int generic_map_set_number(generic_t x, const char* key,
			   double value);
int generic_map_set_string(generic_t x, const char* key,
			   char* value);
int generic_map_set_object(generic_t x, const char* key,
			   generic_t value);
int generic_map_set_map(generic_t x, const char* key,
			generic_t value);
int generic_map_set_array(generic_t x, const char* key,
			  generic_t value);
int generic_map_set_direct(generic_t x, const char* key,
			   char* value);
int generic_map_set_ply(generic_t x, const char* key,
			ply_t value);
int generic_map_set_obj(generic_t x, const char* key,
			obj_t value);
int generic_map_set_python_class(generic_t x, const char* key,
				 python_t value);
int generic_map_set_python_function(generic_t x, const char* key,
				    python_t value);
int generic_map_set_schema(generic_t x, const char* key,
			   schema_t value);
int generic_map_set_any(generic_t x, const char* key,
			generic_t value);

/*!
  @brief Set a scalar value in a map.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[in] key const char* Key string for value that should be set.
  @param[in] value void* Pointer to scalar data.
  @param[in] subtype const char* Subtype of scalar in value.
  @param[in] precision const int Precision of scalar in value.
  @param[in] units const char* Units of value.
  @returns int -1 if there is an error, 0 otherwise.
 */
int generic_map_set_scalar(generic_t x, const char* key,
			   void* value, const char *subtype,
			   const size_t precision,
			   const char* units);
int generic_map_set_int8(generic_t x, const char* key, int8_t value, const char* units);
int generic_map_set_int16(generic_t x, const char* key, int16_t value, const char* units);
int generic_map_set_int32(generic_t x, const char* key, int32_t value, const char* units);
int generic_map_set_int64(generic_t x, const char* key, int64_t value, const char* units);
int generic_map_set_uint8(generic_t x, const char* key, uint8_t value, const char* units);
int generic_map_set_uint16(generic_t x, const char* key, uint16_t value, const char* units);
int generic_map_set_uint32(generic_t x, const char* key, uint32_t value, const char* units);
int generic_map_set_uint64(generic_t x, const char* key, uint64_t value, const char* units);
int generic_map_set_float(generic_t x, const char* key, float value, const char* units);
int generic_map_set_double(generic_t x, const char* key, double value, const char* units);
int generic_map_set_long_double(generic_t x, const char* key, long double value, const char* units);
int generic_map_set_complex_float(generic_t x, const char* key,
				  complex_float_t value,
				  const char* units);
int generic_map_set_complex_double(generic_t x, const char* key,
				   complex_double_t value,
				   const char* units);
int generic_map_set_complex_long_double(generic_t x, const char* key,
					complex_long_double_t value,
					const char* units);
int generic_map_set_bytes(generic_t x, const char* key, char* value, const char* units);
int generic_map_set_unicode(generic_t x, const char* key, char* value, const char* units);

/*!
  @brief Set a 1d array value in a map.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[in] key const char* Key string for value that should be set.
  @param[in] value void* Pointer to array data.
  @param[in] subtype const char* Subtype of array expected.
  @param[in] precision const size_t Precision of array that is expected.
  @param[in] length const size_t Number of elements in value.
  @param[in] units const char* Units of value.
  @returns int -1 if there is an error, 0 otherwise.
 */
int generic_map_set_1darray(generic_t x, const char* key,
			    void* value, const char *subtype,
			    const size_t precision,
			    const size_t length,
			    const char* units);
int generic_map_set_1darray_int8(generic_t x, const char* key,
				 int8_t* value, const size_t length,
				 const char* units);
int generic_map_set_1darray_int16(generic_t x, const char* key,
				  int16_t* value, const size_t length,
				  const char* units);
int generic_map_set_1darray_int32(generic_t x, const char* key,
				  int32_t* value, const size_t length,
				  const char* units);
int generic_map_set_1darray_int64(generic_t x, const char* key,
				  int64_t* value, const size_t length,
				  const char* units);
int generic_map_set_1darray_uint8(generic_t x, const char* key,
				  uint8_t* value, const size_t length,
				  const char* units);
int generic_map_set_1darray_uint16(generic_t x, const char* key,
				   uint16_t* value, const size_t length,
				   const char* units);
int generic_map_set_1darray_uint32(generic_t x, const char* key,
				   uint32_t* value, const size_t length,
				   const char* units);
int generic_map_set_1darray_uint64(generic_t x, const char* key,
				   uint64_t* value, const size_t length,
				   const char* units);
int generic_map_set_1darray_float(generic_t x, const char* key,
				  float* value, const size_t length,
				  const char* units);
int generic_map_set_1darray_double(generic_t x, const char* key,
				   double* value, const size_t length,
				   const char* units);
int generic_map_set_1darray_long_double(generic_t x, const char* key, long double* value, const size_t length, const char* units);
int generic_map_set_1darray_complex_float(generic_t x, const char* key, complex_float_t* value, const size_t length, const char* units);
int generic_map_set_1darray_complex_double(generic_t x, const char* key, complex_double_t* value, const size_t length, const char* units);
int generic_map_set_1darray_complex_long_double(generic_t x, const char* key, complex_long_double_t* value, const size_t length, const char* units);
int generic_map_set_1darray_bytes(generic_t x, const char* key,
				  char** value, const size_t length,
				  const char* units);
int generic_map_set_1darray_unicode(generic_t x, const char* key,
				    char** value, const size_t length,
				    const char* units);
  
/*!
  @brief Set a nd array value in a map.
  @param[in] x generic_t Generic object that is presumed to contain a map.
  @param[in] key const char* Key string for value that should be set.
  @param[in] value void* Pointer to array data.
  @param[in] subtype const char* Subtype of array in value.
  @param[in] precision const size_t Precision of array that is in value.
  @param[in] ndim size_t Number of dimensions in the array.
  @param[in] shape size_t* Pointer to array containing the size of
  the array in each dimension.
  @returns int -1 if there is an error, 0 otherwise.
 */
int generic_map_set_ndarray(generic_t x, const char* key,
			    void* data, const char *subtype,
			    const size_t precision,
			    const size_t ndim, const size_t* shape,
			    const char* units);
int generic_map_set_ndarray_int8(generic_t x, const char* key,
				 int8_t* data, const size_t ndim,
				 const size_t* shape,
				 const char* units);
int generic_map_set_ndarray_int16(generic_t x, const char* key,
				  int16_t* data, const size_t ndim,
				  const size_t* shape,
				  const char* units);
int generic_map_set_ndarray_int32(generic_t x, const char* key,
				  int32_t* data, const size_t ndim,
				  const size_t* shape,
				  const char* units);
int generic_map_set_ndarray_int64(generic_t x, const char* key,
				  int64_t* data, const size_t ndim,
				  const size_t* shape,
				  const char* units);
int generic_map_set_ndarray_uint8(generic_t x, const char* key,
				  uint8_t* data, const size_t ndim,
				  const size_t* shape,
				  const char* units);
int generic_map_set_ndarray_uint16(generic_t x, const char* key,
				   uint16_t* data, const size_t ndim,
				   const size_t* shape,
				   const char* units);
int generic_map_set_ndarray_uint32(generic_t x, const char* key,
				   uint32_t* data, const size_t ndim,
				   const size_t* shape,
				   const char* units);
int generic_map_set_ndarray_uint64(generic_t x, const char* key,
				   uint64_t* data, const size_t ndim,
				   const size_t* shape,
				   const char* units);
int generic_map_set_ndarray_float(generic_t x, const char* key,
				  float* data, const size_t ndim,
				  const size_t* shape,
				  const char* units);
int generic_map_set_ndarray_double(generic_t x, const char* key,
				   double* data, const size_t ndim,
				   const size_t* shape,
				   const char* units);
int generic_map_set_ndarray_long_double(generic_t x, const char* key, long double* data, const size_t ndim, const size_t* shape, const char* units);
int generic_map_set_ndarray_complex_float(generic_t x, const char* key, complex_float_t* data, const size_t ndim, const size_t* shape, const char* units);
int generic_map_set_ndarray_complex_double(generic_t x, const char* key, complex_double_t* data, const size_t ndim, const size_t* shape, const char* units);
int generic_map_set_ndarray_complex_long_double(generic_t x, const char* key, complex_long_double_t* data, const size_t ndim, const size_t* shape, const char* units);
int generic_map_set_ndarray_bytes(generic_t x, const char* key, char** data, const size_t ndim, const size_t* shape, const char* units);
int generic_map_set_ndarray_unicode(generic_t x, const char* key, char** data, const size_t ndim, const size_t* shape, const char* units);
  
/*!
>>>>>>> topic/timesync
  @brief Destroy a structure containing a Python object.
  @param[in] x python_t* Pointer to Python object structure that should be freed.
*/
void destroy_python(python_t *x);


/*!
  @brief Copy a Python object structure (NOTE: this dosn't copy the underlying Python object but does increment the reference count).
  @param[in] x python_t Structure containing Python object to copy.
  @returns python_t Copy of x.
 */
python_t copy_python(python_t x);


/*!
  @brief Display a Python object structure.
  @param[in] x python_t Structure containing Python object to display.
 */
void display_python(python_t x);

  
/*!
  @brief Destroy a structure containing a Python function object.
  @param[in] x python_function_t* Pointer to Python function structure that should be freed.
*/
void destroy_python_function(python_function_t *x);


/*!
  @brief Skip datatype arguments.
  @param[in] dtype dtype_t* Type structure to skip arguments for.
  @param[in, out] nargs Pointer to number of arguments in ap.
  @param[in, out] ap va_list_t Variable argument list.
  @returns int 0 if there are no errors, 1 otherwise.
 */
int skip_va_elements(const dtype_t* dtype, size_t *nargs, va_list_t *ap);


/*!
  @brief Determine if a datatype is empty.
  @param[in] dtype dtype_t* Type structure to test.
  @returns int 1 if dtype is empty, 0 otherwise.
 */
int is_empty_dtype(const dtype_t* dtype);

  
/*!
  @brief Get the name of the type from the class.
  @param[in] type_class dtype_t* Type structure/class.
  @returns const char* Type name.
*/
const char* dtype_name(const dtype_t* type_class);


/*!
  @brief Get the subtype of the type.
  @param[in] type_class dtype_t* Type structure/class.
  @returns const char* The subtype of the class, "" if there is an error.
*/
const char* dtype_subtype(const dtype_t* type_class);


/*!
  @brief Get the precision of the type.
  @param[in] type_class dtype_t* Type structure/class.
  @returns const size_t The precision of the class, 0 if there is an error.
*/
const size_t dtype_precision(const dtype_t* type_class);

/*!
  @brief Initialize a datatype structure including setting the type string.
  @param[in] dtype dtype_t* Type structure/class.
  @returns dtype_t* Initialized type structure/class.
*/
dtype_t* complete_dtype(dtype_t *dtype, const bool use_generic);
  

/*!
  @brief Construct and empty type object.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_empty(const bool use_generic);


/*!
  @brief Create a datatype based on a JSON document.
  @param type_doc void* Pointer to const rapidjson::Value type doc.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
 */
dtype_t* create_dtype_doc(void* type_doc, const bool use_generic);


/*!
  @brief Create a datatype based on a Python dictionary.
  @param[in] pyobj PyObject* Python dictionary.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
 */
dtype_t* create_dtype_python(PyObject* pyobj, const bool use_generic);


/*!
  @brief Construct a Direct type object.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_direct(const bool use_generic);


  
/*!
  @brief Construct a type object for one of the default JSON types.
  @param[in] type char* Name of the type.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_default(const char* type,
			      const bool use_generic);


/*!
  @brief Construct a Scalar type object.
  @param[in] subtype char* Name of the scalar subtype (e.g. int, uint, float, bytes).
  @param[in] precision size_t Precision of the scalar in bits.
  @param[in] units char* Units for scalar. (e.g. "cm", "g", "" for unitless)
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_scalar(const char* subtype, const size_t precision,
			     const char* units, const bool use_generic);


/*!
  @brief Construct a 1D array type object.
  @param[in] subtype char* Name of the array subtype (e.g. int, uint, float, bytes).
  @param[in] precision size_t Precision of the array in bits.
  @param[in] length size_t Number of elements in the array.
  @param[in] units char* Units for array elements. (e.g. "cm", "g", "" for unitless)
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_1darray(const char* subtype, const size_t precision,
			      const size_t length, const char* units,
			      const bool use_generic);


/*!
  @brief Construct a ND array type object.
  @param[in] subtype char* Name of the array subtype (e.g. int, uint, float, bytes).
  @param[in] precision size_t Precision of the array in bits.
  @param[in] ndim size_t Number of dimensions in the array (and therefore also the
  number of elements in shape).
  @param[in] shape size_t* Pointer to array where each element is the size of the
  array in that dimension.
  @param[in] units char* Units for array elements. (e.g. "cm", "g", "" for unitless)
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_ndarray(const char* subtype, const size_t precision,
			      const size_t ndim, const size_t* shape,
			      const char* units, const bool use_generic);

  
/*!
  @brief Construct a ND array type object.
  @param[in] subtype char* Name of the array subtype (e.g. int, uint, float, bytes).
  @param[in] precision size_t Precision of the array in bits.
  @param[in] ndim size_t Number of dimensions in the array (and therefore also the
  number of elements in shape).
  @param[in] shape[] size_t Array where each element is the size of the
  array in that dimension.
  @param[in] units char* Units for array elements. (e.g. "cm", "g", "" for unitless)
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_ndarray_arr(const char* subtype, const size_t precision,
				  const size_t ndim, const int64_t shape[],
				  const char* units, const bool use_generic);

  
/*!
  @brief Construct a JSON array type object.
  @param[in] nitems size_t Number of types in items.
  @param[in] items dtype_t** Pointer to array of types describing the array
  elements.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_json_array(const size_t nitems, dtype_t** items,
				 const bool use_generic);


/*!
  @brief Construct a JSON object type object.
  @param[in] nitems size_t Number of keys/types in keys and values.
  @param[in] keys char** Pointer to array of keys for each type.
  @param[in] values dtype_t** Pointer to array of types describing the values
  for each key.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_json_object(const size_t nitems, char** keys,
				  dtype_t** values, const bool use_generic);

/*!
  @brief Construct a Ply type object.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_ply(const bool use_generic);


/*!
  @brief Construct a Obj type object.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_obj(const bool use_generic);


/*!
  @brief Construct an AsciiTable type object.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_ascii_table(const char *format_str, const int as_array,
				  const bool use_generic);


/*!
  @brief Construct a type object based on the provided format string.
  @param[in] format_str const char* C-style format string that will be used to determine
  the type of elements in arrays that will be serialized/deserialized using
  the resulting type.
  @param[in] as_array int If 1, the types will be arrays. Otherwise they will be
  scalars.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
*/
dtype_t* create_dtype_format(const char *format_str, const int as_array,
			     const bool use_generic);

  
/*!
  @brief Construct a type object for Python objects.
  @param[in] type char* Type string.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
 */
dtype_t* create_dtype_pyobj(const char* type, const bool use_generic);
  

/*!
  @brief Construct a type object for Python object instances.
  @param[in] class_name char* Python class name.
  @param[in] args_dtype dtype_t* Datatype describing the arguments
  creating the instance.
  @param[in] kwargs_dtype dtype_t* Datatype describing the keyword 
  arguments creating the instance.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
 */
dtype_t* create_dtype_pyinst(const char* class_name,
			     const dtype_t* args_dtype,
			     const dtype_t* kwargs_dtype,
			     const bool use_generic);

  
/*!
  @brief Construct a type object for a schema.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
 */
dtype_t* create_dtype_schema(const bool use_generic);


/*!
  @brief Construct a type object for receiving any type.
  @param[in] use_generic bool If true, serialized/deserialized
  objects will be expected to be YggGeneric classes.
  @returns dtype_t* Type structure/class.
 */
dtype_t* create_dtype_any(const bool use_generic);


/*!
  @brief Wrapper for freeing MetaschemaType class wrapper struct.
  @param[in] dtype dtype_t** Wrapper struct for C++ Metaschema type class.
  @returns: int 0 if free was successfull, -1 if there was an error.
*/
int destroy_dtype(dtype_t** dtype);

/*!
  @brief Initialize a header struct.
  @param[in] size size_t Size of message to be sent.
  @param[in] address char* Address that should be used for remainder of 
  message following this header if it is a multipart message.
  @param[in] id char* Message ID.
  @returns comm_head_t Structure with provided information, char arrays
  correctly initialized to empty strings if NULLs provided.
 */
static inline
comm_head_t init_header(const size_t size, const char *address, const char *id) {
  comm_head_t out;
  // Parameters set during read
  out.bodysiz = 0;
  out.bodybeg = 0;
  out.flags = HEAD_FLAG_VALID;
  out.nargs_populated = 0;
  // Parameters sent in header
  out.size = size;
  if (address == NULL)
    out.address[0] = '\0';
  else
    strncpy(out.address, address, COMMBUFFSIZ);
  if (id == NULL)
    out.id[0] = '\0';
  else
    strncpy(out.id, id, COMMBUFFSIZ);
  out.response_address[0] = '\0';
  out.request_id[0] = '\0';
  out.zmq_reply[0] = '\0';
  out.zmq_reply_worker[0] = '\0';
  out.model[0] = '\0';
  // Parameters that will be removed
  out.serializer_type = -1;
  out.format_str[0] = '\0';
  // Parameters used for type
  out.dtype = NULL;
  return out;
};


/*!
  @brief Destroy a header object.
  @param[in] x comm_head_t* Pointer to the header that should be destroyed.
  @returns int 0 if successful, -1 otherwise.
*/
static inline
int destroy_header(comm_head_t* x) {
  int ret = 0;
  if (x->dtype != NULL) {
    ret = destroy_dtype(&(x->dtype));
  }
  return ret;
};


/*!
  @brief Split header and body of message.
  @param[in] buf const char* Message that should be split.
  @param[in] buf_siz size_t Size of buf.
  @param[out] head const char** pointer to buffer where the extracted header
  should be stored.
  @param[out] headsiz size_t reference to memory where size of extracted header
  should be stored.
  @returns: int 0 if split is successful, -1 if there was an error.
*/
static inline
int split_head_body(const char *buf, const size_t buf_siz,
		    char **head, size_t *headsiz) {
  // Split buffer into head and body
  int ret;
  size_t sind, eind, sind_head, eind_head;
  sind = 0;
  eind = 0;
#ifdef _WIN32
  // Windows regex of newline is buggy
  UNUSED(buf_siz);
  size_t sind1, eind1, sind2, eind2;
  char re_head_tag[COMMBUFFSIZ];
  sprintf(re_head_tag, "(%s)", MSG_HEAD_SEP);
  ret = find_match(re_head_tag, buf, &sind1, &eind1);
  if (ret > 0) {
    sind = sind1;
    ret = find_match(re_head_tag, buf + eind1, &sind2, &eind2);
    if (ret > 0)
      eind = eind1 + eind2;
  }
#else
  // Extract just header
  char re_head[COMMBUFFSIZ] = MSG_HEAD_SEP;
  strcat(re_head, "(.*)");
  strcat(re_head, MSG_HEAD_SEP);
  // strcat(re_head, ".*");
  ret = find_match(re_head, buf, &sind, &eind);
#endif
  if (ret < 0) {
    ygglog_error("split_head_body: Could not find header in '%.1000s'", buf);
    return -1;
  } else if (ret == 0) {
    ygglog_debug("split_head_body: No header in '%.1000s...'", buf);
    sind_head = 0;
    eind_head = 0;
  } else {
    sind_head = sind + strlen(MSG_HEAD_SEP);
    eind_head = eind - strlen(MSG_HEAD_SEP);
  }
  headsiz[0] = (eind_head - sind_head);
  char* temp = (char*)realloc(*head, *headsiz + 1);
  if (temp == NULL) {
    ygglog_error("split_head_body: Failed to reallocate header.");
    return -1;
  }
  *head = temp;
  memcpy(*head, buf + sind_head, *headsiz);
  (*head)[*headsiz] = '\0';
  return 0;
};


/*!
  @brief Format header to a string.
  @param[in] head comm_head_t* Pointer to header to be formatted.
  @param[out] buf char ** Pointer to buffer where header should be written.
  @param[in] buf_siz size_t Size of buf.
  @param[in] max_header_size size_t Maximum size that header can occupy
  before the type should be moved to the data portion of the message.
  @param[in] int no_type If 1, type information will not be added to
  the header. If 0, it will be.
  @returns: int Size of header written.
*/
int format_comm_header(comm_head_t *head, char **buf, size_t buf_siz,
		       const size_t max_header_size, const int no_type);


/*!
  @brief Extract type from data and updated header.
  @param[in] buf char** Pointer to data containing type.
  @param[in] buf_siz size_t Size of buf.
  @param[in,out] head comm_head_t* Pointer to header structure that
  should be updated.
  @returns: int -1 if there is an error, size of adjusted data that
  dosn't include type otherwise.
 */
int parse_type_in_data(char **buf, const size_t buf_siz,
		       comm_head_t* head);

  
/*!
  @brief Extract header information from a string.
  @param[in] buf const char* Message that header should be extracted from.
  @param[in] buf_siz size_t Size of buf.
  @returns: comm_head_t Header information structure.
*/
comm_head_t parse_comm_header(const char *buf, const size_t buf_siz);


/*!
  @brief Get the ascii table data structure.
  @param[in] dtype dtype_t* Wrapper struct for C++ Metaschema type class.
  @returns: void* Cast pointer to ascii table.
*/
void* dtype_ascii_table(const dtype_t* dtype);


/*!
  @brief Get a copy of a type structure.
  @param[in] dtype dtype_t* Wrapper struct for C++ Metaschema type class.
  @returns: dtype_t* Type class.
*/
dtype_t* copy_dtype(const dtype_t* dtype);


/*!
  @brief Wrapper for updating a type object with information from another.
  @param[in] dtype1 dtype_t* Wrapper struct for C++ Metaschema type class that should be updated.
  @param[in] dtype2 dtype_t* Wrapper struct for C++ Metaschema type class that should be updated from.
  @returns: int 0 if successfull, -1 if there was an error.
*/
int update_dtype(dtype_t* dtype1, dtype_t* dtype2);


/*!
  @brief Wrapper for updatining a type object with information from
  the provided variable arguments if a generic structure is present.
  @param[in] dtype1 dtype_t* Wrapper struct for C++ Metaschema type class that should be updated.
  @param[in] nargs size_t Number of arguments in ap.
  @param[in] ap va_list_t Variable argument list.
  @returns: int 0 if successfull, -1 if there was an error.
 */
int update_dtype_from_generic_ap(dtype_t* dtype1, size_t nargs, va_list_t ap);

  
/*!
  @brief Wrapper for updating the precision of a bytes or unicode scalar type.
  @param[in] dtype dtype_t* Wrapper struct for C++ Metaschema type class.
  @param[in] new_precision size_t New precision.
  @returns: int 0 if free was successfull, -1 if there was an error.
*/
int update_precision_dtype(const dtype_t* dtype,
			   const size_t new_precision);

/*!
  @brief Wrapper for deserializing from a data type.
  @param[in] dtype dtype_t* Wrapper struct for C++ Metaschema type class.
  @param[in] buf character pointer to serialized message.
  @param[in] buf_siz size_t Size of buf.
  @param[in] allow_realloc int If 1, variables being filled are assumed to be
  pointers to pointers for heap memory. If 0, variables are assumed to be pointers
  to stack memory. If allow_realloc is set to 1, but stack variables are passed,
  a segfault can occur.
  @param[in, out] nargs int Number of arguments remaining in argument list.
  @param[in] ap va_list Arguments to be parsed from message.
  returns: int The number of populated arguments. -1 indicates an error.
*/
int deserialize_dtype(const dtype_t *dtype, const char *buf, const size_t buf_siz,
		      const int allow_realloc, size_t *nargs, va_list_t ap);


/*!
  @brief Wrapper for serializing from a data type.
  @param[in] dtype dtype_t* Wrapper struct for C++ Metaschema type class.
  @param[in] buf character pointer to pointer to memory where serialized message
  should be stored.
  @param[in] buf_siz size_t Size of memory allocated to buf.
  @param[in] allow_realloc int If 1, buf will be realloced if it is not big
  enough to hold the serialized emssage. If 0, an error will be returned.
  @param[in, out] nargs int Number of arguments remaining in argument list.
  @param[in] ap va_list Arguments to be formatted.
  returns: int The length of the serialized message or -1 if there is an error.
*/
int serialize_dtype(const dtype_t *dtype, char **buf, size_t *buf_siz,
		    const int allow_realloc, size_t *nargs, va_list_t ap);


/*!
  @brief Wrapper for displaying a data type.
  @param[in] dtype dtype_t* Wrapper struct for C++ Metaschema type class.
  @param[in] indent char* Indentation to add to display output.
*/
  void display_dtype(const dtype_t *dtype, const char* indent);


/*!
  @brief Wrapper for determining how many arguments a data type expects.
  @param[in] dtype dtype_t* Wrapper struct for C++ Metaschema type class.
*/
size_t nargs_exp_dtype(const dtype_t *dtype);


#define free_generic destroy_generic
#define init_json_object init_generic_map
#define init_json_array init_generic_array
#define init_schema init_generic
#define free_json_object free_generic
#define free_json_array free_generic
#define free_schema free_generic
#define copy_json_object copy_generic
#define copy_json_array copy_generic
#define copy_schema copy_generic
#define display_json_object display_generic
#define display_json_array display_generic
#define display_schema display_generic

  
#ifdef __cplusplus /* If this is a C++ compiler, end C linkage */
}
#endif

#endif /*DATATYPES_H_*/
