/*! @brief Flag for checking if this header has already been included. */
#ifndef YGGCOMMUNICATION_H_
#define YGGCOMMUNICATION_H_

#include "../tools.h"
#include "../datatypes/datatypes.h"
#include "CommBase.h"
#include "IPCComm.h"
#include "ZMQComm.h"
#include "ServerComm.h"
#include "ClientComm.h"
#include "AsciiFileComm.h"
#include "AsciiTableComm.h"
#include "DefaultComm.h"

#ifdef __cplusplus /* If this is a C++ compiler, use C linkage */
extern "C" {
#endif

/*! @brief Memory to keep track of comms to clean up at exit. */
static void **vcomms2clean = NULL;
static size_t ncomms2clean = 0;
static size_t clean_registered = 0;
static size_t clean_in_progress = 0;
static size_t clean_called = 0;
#ifdef _OPENMP
#pragma omp threadprivate(clean_in_progress)
#endif

/*! @brief Memory to keep track of global scope comms. */
#ifdef _OPENMP
static size_t global_scope_comm = 1;
#define WITH_GLOBAL_SCOPE(COMM) global_scope_comm = 1; COMM
#pragma omp threadprivate(global_scope_comm)
#else
static size_t global_scope_comm = 0;
#define WITH_GLOBAL_SCOPE(COMM) global_scope_comm = 1; COMM; global_scope_comm = 0
#endif


/*!
 @brief Check if EOF should be sent for a comm being used on multiple threads.
 @param[in] x const comm_t* Comm to check.
 @returns int 1 if EOF has been sent for all but this comm and 0 otherwise.
 */
static
int check_threaded_eof(const comm_t* x) {
  int out = 1;
#ifdef _OPENMP
#pragma omp critical (comms)
  {
    size_t i;
    comm_t* icomm = NULL;
    int nthreads = 1;
    for (i = 0; i < ncomms2clean; i++) {
      if ((out == 1) && (vcomms2clean[i] != NULL)) {
	icomm = (comm_t*)(vcomms2clean[i]);
	if ((strcmp(icomm->name, x->name) == 0)
	    && (icomm->thread_id != x->thread_id)) {
	  nthreads++;
#pragma omp critical (sent_eof)
	  {
	    if ((x->const_flags != NULL) && (!(x->const_flags[0] & COMM_EOF_SENT)))
	      out = 0;
	  }
	}
      }
    }
    if (nthreads < omp_get_num_threads())
      out = 0;  // all threads havn't initialized a comm
  }
#endif
  return out;
};

/*!
  @brief Set the sent_eof flag on the comm.
  @param[in] x comm_t* Comm to set the flag for.
*/
static
void set_sent_eof(const comm_t* x) {
#ifdef _OPENMP
#pragma omp critical (sent_eof)
  {
#endif
  x->const_flags[0] = x->const_flags[0] | COMM_EOF_SENT;
  if (x->type == CLIENT_COMM) {
    comm_t *req_comm = (comm_t*)(x->handle);
    // Don't recurse to prevent block w/ omp critical recursion
    req_comm->const_flags[0] = req_comm->const_flags[0] | COMM_EOF_SENT;
  }
#ifdef _OPENMP
  }
#endif
};


/*!
  @brief Retrieve a registered global comm if it exists.
  @param[in] const char* name Name that comm might be registered under.
  @returns comm_t* Pointer to registered comm. NULL if one does not exist
  with the specified name.
 */
static
comm_t* get_global_scope_comm(const char *name) {
  comm_t* out = NULL;
#ifdef _OPENMP
#pragma omp critical (comms)
  {
#endif
  if (global_scope_comm) {
    size_t i;
    comm_t* icomm = NULL;
    int current_thread = get_thread_id();
    for (i = 0; i < ncomms2clean; i++) {
      if (vcomms2clean[i] != NULL) {
	icomm = (comm_t*)(vcomms2clean[i]);
	if ((strcmp(icomm->name, name) == 0) && (icomm->thread_id == current_thread)) {
	  out = icomm;
	  break;
	} else {
	  const char* YGG_MODEL_NAME = getenv("YGG_MODEL_NAME");
	  char alt_name[100];
	  sprintf(alt_name, "%s:%s", YGG_MODEL_NAME, name);
	  if ((strcmp(icomm->name, alt_name) == 0) && (icomm->thread_id == current_thread)) {
	    out = icomm;
	    break;
	  }
	}
      }
    }
  }
#ifdef _OPENMP
  }
#endif
  return out;
};


// Forward declaration of eof
static
int comm_send_eof(const comm_t *x);
static
int comm_nmsg(const comm_t *x);


/*!
  @brief Determine if a channel has a format type associated with it.
  @param[in] x comm_t * Pointer to communicator to check.
  @returns int 1 if format type, 0 otherwise.
 */
static
int is_comm_format_array_type(const comm_t *x) {
  dtype_t *datatype = x->datatype;
  return is_dtype_format_array(datatype);
};


/*!
  @brief Determine if the current thread can use a comm registered by another.
  @param[in] int Thread that created the comm.
  @returns int 1 if the current thread can use the comm, 0 otherwise.
 */
static
int thread_can_use(int thread_id) {
  int current_thread_id = get_thread_id();
  if ((clean_in_progress) && (current_thread_id == 0))
    return 1;
  if (thread_id == current_thread_id)
    return 1;
  return 0;
};

  
/*!
  @brief Perform deallocation for type specific communicator.
  @param[in] x comm_t * Pointer to communicator to deallocate.
  @returns int 1 if there is an error, 0 otherwise.
*/
static
int free_comm_type(comm_t *x) {
  comm_type t = x->type;
  int ret = 1;
  if (!(thread_can_use(x->thread_id))) {
    ygglog_error("free_comm_type: Thread is attempting to use a comm it did not initialize");
    return ret;
  }
  if (t == IPC_COMM)
    ret = free_ipc_comm(x);
  else if (t == ZMQ_COMM)
    ret = free_zmq_comm(x);
  else if (t == SERVER_COMM)
    ret = free_server_comm(x);
  else if (t == CLIENT_COMM)
    ret = free_client_comm(x);
  else if (t == ASCII_FILE_COMM)
    ret = free_ascii_file_comm(x);
  else if ((t == ASCII_TABLE_COMM) || (t == ASCII_TABLE_ARRAY_COMM))
    ret = free_ascii_table_comm(x);
  else {
    ygglog_error("free_comm_type: Unsupported comm_type %d", t);
  }
  return ret;
};

/*!
  @brief Perform deallocation for generic communicator.
  @param[in] x comm_t * Pointer to communicator to deallocate.
  @returns int 1 if there is an error, 0 otherwise.
*/
static
int free_comm(comm_t *x) {
  int ret = 0;
  if (x == NULL)
    return ret;
  ygglog_debug("free_comm(%s)", x->name);
  // Send EOF for output comms and then wait for messages to be recv'd
  if ((is_send(x->direction)) && (x->flags & COMM_FLAG_VALID)) {
    if (_ygg_error_flag == 0) {
      ygglog_debug("free_comm(%s): Sending EOF", x->name);
      comm_send_eof(x);
      while (comm_nmsg(x) > 0) {
        ygglog_debug("free_comm(%s): draining %d messages",
          x->name, comm_nmsg(x));
        usleep(YGG_SLEEP_TIME);
      }
    } else {
      ygglog_error("free_comm(%s): Error registered", x->name);
    }
  }
#ifdef _OPENMP
#pragma omp critical (comms)
  {
#endif
  ret = free_comm_type(x);
  int idx = x->index_in_register;
  free_comm_base(x);
  if (idx >= 0) {
    if (vcomms2clean[idx] != NULL) {
      free(vcomms2clean[idx]);
      vcomms2clean[idx] = NULL;
    }
  }
  ygglog_debug("free_comm: Finished");
#ifdef _OPENMP
  }
#endif
  return ret;
};

/*!
  @brief Free comms created that were not freed.
*/
static
void clean_comms(void) {
#ifdef _OPENMP
#pragma omp critical (clean)
    {
#endif
  size_t i;
  if (!(clean_called)) {
    clean_in_progress = 1;
    ygglog_debug("atexit begin");
    if (vcomms2clean != NULL) {
      for (i = 0; i < ncomms2clean; i++) {
	if (vcomms2clean[i] != NULL) {
	  free_comm((comm_t*)(vcomms2clean[i]));
	}
      }
    }
#ifdef _OPENMP
#pragma omp critical (comms)
    {
#endif
    if (vcomms2clean != NULL) {
      free(vcomms2clean);
      vcomms2clean = NULL;
    }
    ncomms2clean = 0;
    ygglog_debug("atexit finished cleaning comms, in final shutdown");
#if defined(ZMQINSTALLED)
    // #if defined(_MSC_VER) && defined(ZMQINSTALLED)
    ygg_zsys_shutdown();
#endif
    if (Py_IsInitialized()) {
      Py_Finalize();
    }
  /* printf(""); */
    clean_called = 1;
#ifdef _OPENMP
    }
#endif
  }
#ifdef _OPENMP
  }
#endif
  ygglog_debug("atexit done");
  if (_ygg_error_flag != 0) {
    _exit(_ygg_error_flag);
  }
};

/*!
  @brief Initialize yggdrasil in a thread-safe way
 */
static inline
int ygg_init() {
  int out = 0;
#ifdef _OPENMP
#pragma omp critical (init)
  {
#endif
  ygglog_debug("ygg_init: clean_registered = %d", clean_registered);
  if (clean_registered == 0) {
#if defined(ZMQINSTALLED)
    if (!(ygg_zsys_init())) {
      out = -1;
    }
#endif
    if (out == 0) {
      ygglog_debug("ygg_init: Registering cleanup");
      atexit(clean_comms);
      clean_registered = 1;
    }
  }
#ifdef _OPENMP
  }
#endif
  return out;
};

/*!
  @brief Register a comm so that it can be cleaned up later if not done explicitly.
  @param[in] x comm_t* Address of communicator structure that should be
  registered.
  @returns int -1 if there is an error, 0 otherwise.
 */
static
int register_comm(comm_t *x) {
  if (x == NULL) {
    return 0;
  }
  int error_flag = 0;
#ifdef _OPENMP
#pragma omp critical (comms)
  {
#endif
    if (ygg_init()) {
      error_flag = 1;
    } else {
      void **t_vcomms2clean = (void**)realloc(vcomms2clean, sizeof(void*)*(ncomms2clean + 1));
      if (t_vcomms2clean == NULL) {
	ygglog_error("register_comm(%s): Failed to realloc the comm list.", x->name);
	error_flag = -1;
      } else {
	vcomms2clean = t_vcomms2clean;
	x->index_in_register = (int)ncomms2clean;
	vcomms2clean[ncomms2clean++] = (void*)x;
      }
    }
#ifdef _OPENMP
  }
#endif
  return error_flag;
};

/*!
  @brief Initialize a new communicator based on its type.
  @param[in] x comm_t * Pointer to communicator structure initialized with
  new_base_comm;
  @returns int -1 if the comm could not be initialized.
 */
static
int new_comm_type(comm_t *x) {
  comm_type t = x->type;
  int flag;
  if (t == IPC_COMM)
    flag = new_ipc_address(x);
  else if (t == ZMQ_COMM)
    flag = new_zmq_address(x);
  else if (t == SERVER_COMM)
    flag = new_server_address(x);
  else if (t == CLIENT_COMM)
    flag = new_client_address(x);
  else if (t == ASCII_FILE_COMM)
    flag = new_ascii_file_address(x);
  else if (t == ASCII_TABLE_COMM)
    flag = new_ascii_table_address(x);
  else if (t == ASCII_TABLE_ARRAY_COMM)
    flag = new_ascii_table_array_address(x);
  else {
    ygglog_error("new_comm_type: Unsupported comm_type %d", t);
    flag = -1;
  }
  return flag;
};

/*!
  @brief Initialize the communicator based on its type.
  @param[in] x comm_t * Pointer to communicator structure initialized with
  init_base_comm;
  @returns int -1 if the comm could not be initialized.
 */
static
int init_comm_type(comm_t *x) {
  comm_type t = x->type;
  int flag;
  if (t == IPC_COMM)
    flag = init_ipc_comm(x);
  else if (t == ZMQ_COMM)
    flag = init_zmq_comm(x);
  else if (t == SERVER_COMM)
    flag = init_server_comm(x);
  else if (t == CLIENT_COMM)
    flag = init_client_comm(x);
  else if (t == ASCII_FILE_COMM)
    flag = init_ascii_file_comm(x);
  else if (t == ASCII_TABLE_COMM)
    flag = init_ascii_table_comm(x);
  else if (t == ASCII_TABLE_ARRAY_COMM)
    flag = init_ascii_table_array_comm(x);
  else {
    ygglog_error("init_comm_type: Unsupported comm_type %d", t);
    flag = -1;
  }
  ygglog_debug("init_comm_type(%s): Done, flag = %d", x->name, flag);
  return flag;
};

/*!
  @brief Initialize comm from the address.
  @param[in] address char * Address for new comm. If NULL, a new address is
  generated.
  @param[in] direction Direction that messages will go through the comm.
  Values include "recv" and "send".
  @param[in] t comm_type Type of comm that should be created.
  @param[in] datatype dtype_t* Pointer to data type structure.
  @returns comm_t* Pointer to comm structure.
 */
static
comm_t* new_comm(char *address, const char *direction,
		 const comm_type t, dtype_t* datatype) {
  comm_t *ret = new_comm_base(address, direction, t, datatype);
  if (ret == NULL) {
    ygglog_error("new_comm: Could not initialize base.");
    return ret;
  }
  int flag;
  if (address == NULL) {
    flag = new_comm_type(ret);
  } else {
    flag = init_comm_type(ret);
  }
  if (flag < 0) {
    ygglog_error("new_comm: Failed to initialize new comm address.");
    ret->flags = ret->flags & ~COMM_FLAG_VALID;
  } else {
    if (strlen(ret->name) == 0) {
      sprintf(ret->name, "temp.%s", ret->address);
    }
    flag = register_comm(ret);
    if (flag < 0) {
      ygglog_error("new_comm: Failed to register new comm.");
      ret->flags = ret->flags & ~COMM_FLAG_VALID;
    }
  }
  return ret;
};

/*!
  @brief Initialize a generic communicator.
  The name is used to locate the comm address stored in the associated
  environment variable.
  @param[in] name Name of environment variable that the queue address is
  stored in.
  @param[in] direction Direction that messages will go through the comm.
  Values include "recv" and "send".
  @param[in] t comm_type Type of comm that should be created.
  @param[in] datatype dtype_t* Pointer to data type structure.
  @returns comm_t* Comm structure.
 */
static
comm_t* init_comm(const char *name, const char *direction,
		  const comm_type t, dtype_t *datatype) {
  ygglog_debug("init_comm: Initializing comm.");
#ifdef _MSC_VER
  SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX);
  _set_abort_behavior(0,_WRITE_ABORT_MSG);
#endif
  comm_t *ret = get_global_scope_comm(name);
  if (ret != NULL) {
    destroy_dtype(&datatype);
    return ret;
  }
  if ((datatype == NULL) && (strcmp(direction, "send") == 0)) {
    datatype = create_dtype_scalar("bytes", 0, "", false);
  }
  ret = init_comm_base(name, direction, t, datatype);
  if (ret == NULL) {
    ygglog_error("init_comm(%s): Could not initialize base.", name);
    return ret;
  }
  int flag = init_comm_type(ret);
  if (flag < 0) {
    ygglog_error("init_comm(%s): Could not initialize comm.", name);
    ret->flags = ret->flags & ~COMM_FLAG_VALID;
  } else {
    flag = register_comm(ret);
    if (flag < 0) {
      ygglog_error("init_comm(%s): Failed to register new comm.", name);
      ret->flags = ret->flags & ~COMM_FLAG_VALID;
    }
  }
  if (ret->flags & COMM_FLAG_VALID) {
    if (global_scope_comm) {
      ret->flags = ret->flags | COMM_FLAG_GLOBAL;
      ygglog_debug("init_comm(%s): Global comm!", name);
    }
    ygglog_debug("init_comm(%s): Initialized comm.", name);
  }
  return ret;
};


/*!
  @brief Convert a format string to a datatype.
  @param[in] format_str char* Format string.
  @param[in] as_array int If 1, inputs/outputs are processed as arrays.
  @returns dtype_t* Pointer to datatype structure.
 */
static
dtype_t* formatstr2datatype(const char *format_str, const int as_array) {
  dtype_t* datatype = NULL;
  if (format_str != NULL) {
    datatype = create_dtype_format(format_str, as_array, false);
  }
  return datatype;
};

/*!
  @brief Initialize a generic communicator using a format string to determine
  the type.
  The name is used to locate the comm address stored in the associated
  environment variable.
  @param[in] name Name of environment variable that the queue address is
  stored in.
  @param[in] direction Direction that messages will go through the comm.
  Values include "recv" and "send".
  @param[in] t comm_type Type of comm that should be created.
  @param[in] format_str char* Format string.
  @param[in] as_array int If 1, inputs/outputs are processed as arrays.
  @returns comm_t* Pointer to comm structure.
 */
static
comm_t* init_comm_format(const char *name, const char *direction,
			 const comm_type t, const char *format_str,
			 const int as_array) {
  dtype_t* datatype = formatstr2datatype(format_str, as_array);
  comm_t* out = init_comm(name, direction, t, datatype);
  if ((format_str != NULL) && (datatype == NULL)) {
    ygglog_error("init_comm_format: Failed to create type from format_str.");
    if (out != NULL) {
      out->flags = out->flags & ~COMM_FLAG_VALID;
    }
  }
  return out;
};


/*!
  @brief Get number of messages in the comm.
  @param[in] x comm_t Communicator to check.
  @returns int Number of messages.
 */
static
int comm_nmsg(const comm_t *x) {
  int ret = -1;
  if ((x == NULL) || (!(x->flags & COMM_FLAG_VALID))) {
    ygglog_error("comm_nmsg: Invalid comm");
    return ret;
  }
  comm_type t = x->type;
  if (t == IPC_COMM)
    ret = ipc_comm_nmsg(x);
  else if (t == ZMQ_COMM)
    ret = zmq_comm_nmsg(x);
  else if (t == SERVER_COMM)
    ret = server_comm_nmsg(x);
  else if (t == CLIENT_COMM)
    ret = client_comm_nmsg(x);
  else if (t == ASCII_FILE_COMM)
    ret = ascii_file_comm_nmsg(x);
  else if ((t == ASCII_TABLE_COMM) || (t == ASCII_TABLE_ARRAY_COMM))
    ret = ascii_table_comm_nmsg(x);
  else {
    ygglog_error("comm_nmsg: Unsupported comm_type %d", t);
  }
  return ret;
};

/*!
  @brief Send a single message to the comm.
  Send a message smaller than YGG_MSG_MAX bytes to an output comm. If the
  message is larger, it will not be sent.
  @param[in] x comm_t* structure that comm should be sent to.
  @param[in] data character pointer to message that should be sent.
  @param[in] len size_t length of message to be sent.
  @returns int 0 if send succesfull, -1 if send unsuccessful.
 */
static
int comm_send_single(const comm_t *x, const char *data, const size_t len) {
  ygglog_debug("Sending %d bytes: '%s'\n", len, data);
  int ret = -1;
  if ((x == NULL) || (!(x->flags & COMM_FLAG_VALID))) {
    ygglog_error("comm_send_single: Invalid comm");
    return ret;
  }
  if (!(thread_can_use(x->thread_id))) {
    ygglog_error("comm_send_single: Thread is attempting to use a comm it did not initialize");
    return ret;
  }
  comm_type t = x->type;
  if (t == IPC_COMM)
    ret = ipc_comm_send(x, data, len);
  else if (t == ZMQ_COMM)
    ret = zmq_comm_send(x, data, len);
  else if (t == SERVER_COMM)
    ret = server_comm_send(x, data, len);
  else if (t == CLIENT_COMM)
    ret = client_comm_send(x, data, len);
  else if (t == ASCII_FILE_COMM)
    ret = ascii_file_comm_send(x, data, len);
  else if ((t == ASCII_TABLE_COMM) || (t == ASCII_TABLE_ARRAY_COMM))
    ret = ascii_table_comm_send(x, data, len);
  else {
    ygglog_error("comm_send_single: Unsupported comm_type %d", t);
  }
  if (ret >= 0) {
    time(x->last_send);
    /* time_t now; */
    /* time(&now); */
    /* x->last_send[0] = now; */
  }
  return ret;
};


/*!
  @brief Create header for multipart message.
  @param[in] x comm_t* structure that header will be sent to.
  @param[in] data const char * Message to be sent.
  @param[in] len size_t Size of message body.
  @returns comm_head_t Header info that should be sent before the message
  body.
*/
static
comm_head_t comm_send_multipart_header(const comm_t *x, const char * data,
				       const size_t len) {
  comm_head_t head = init_header(len, NULL, NULL);
  sprintf(head.id, "%d", rand());
  char *model_name = getenv("YGG_MODEL_NAME");
  if (model_name != NULL) {
    strcpy(head.model, model_name);
  }
  head.flags = head.flags | HEAD_FLAG_VALID | HEAD_FLAG_MULTIPART;
  // Add datatype information to header
  if (!(x->flags & COMM_FLAG_FILE)) {
    dtype_t *datatype;
    if (x->type == CLIENT_COMM) {
      comm_t *req_comm = (comm_t*)(x->handle);
      datatype = req_comm->datatype;
    } else {
      datatype = x->datatype;
    }
    head.dtype = datatype;
  }
  const comm_t *x0;
  if (x->type == SERVER_COMM) {
    if (!(is_eof(data))) {
      head = server_response_header(x, head);
    }
    x0 = server_get_comm((requests_t*)(x->info), 0);
    if (x0 == NULL) {
      ygglog_error("comm_send_multipart_header(%s): no response comm registered",
		   x->name);
      head.flags = head.flags & ~HEAD_FLAG_VALID;
      return head;
    }
    // This gives the server access to the ID of the message last received
    strcpy(head.id, x->address);
  } else if (x->type == CLIENT_COMM) {
    if (!(is_eof(data))) {
      head = client_response_header(x, head);
    }
    x0 = (comm_t*)(x->handle);
  } else {
    x0 = x;
  }
  // Get ZMQ header info
  if (x0->type == ZMQ_COMM) {
    char *reply_address = set_reply_send(x0);
    if (reply_address == NULL) {
      ygglog_error("comm_send_multipart_header: Could not set reply address.");
      head.flags = head.flags & ~HEAD_FLAG_VALID;
      return head;
    }
    strcpy(head.zmq_reply, reply_address);
    ygglog_debug("reply_address = %s\n", head.zmq_reply);
  }
  return head;
};

/*!
  @brief Send a large message in multiple parts via a new comm.
  @param[in] x comm_t* Structure that message should be sent to.
  @param[in] data const char * Message that should be sent.
  @param[in] len size_t Size of data.
  @returns: int 0 if send successfull, -1 if send unsuccessful.
*/
static
int comm_send_multipart(const comm_t *x, const char *data, const size_t len) {
  //char headbuf[YGG_MSG_BUF];
  size_t headbuf_len = YGG_MSG_BUF;
  int headlen = 0, ret = -1;
  comm_t* xmulti = NULL;
  int no_type = is_eof(data);
  if ((x == NULL) || (!(x->flags & COMM_FLAG_VALID))) {
    ygglog_error("comm_send_multipart: Invalid comm");
    return ret;
  }
  // Get header
  comm_head_t head = comm_send_multipart_header(x, data, len);
  if (!(head.flags & HEAD_FLAG_VALID)) {
    ygglog_error("comm_send_multipart: Invalid header generated.");
    return -1;
  }
  char *headbuf = (char*)malloc(headbuf_len);
  if (headbuf == NULL) {
    ygglog_error("comm_send_multipart: Failed to malloc headbuf.");
    return -1;
  }
  // Try to send body in header
  if (len < (x->maxMsgSize - x->msgBufSize)) {
    headlen = format_comm_header(&head, &headbuf, headbuf_len,
				 x->maxMsgSize - x->msgBufSize,
				 no_type);
    if (headlen < 0) {
      ygglog_error("comm_send_multipart: Failed to format header.");
      free(headbuf);
      return -1;
    }
    if (((size_t)headlen + len) < (x->maxMsgSize - x->msgBufSize)) {
      if (((size_t)headlen + len + 1) > headbuf_len) {
        char *t_headbuf = (char*)realloc(headbuf, (size_t)headlen + len + 1);
        if (t_headbuf == NULL) {
          ygglog_error("comm_send_multipart: Failed to realloc headbuf.");
	  free(headbuf);
          return -1;          
        }
	headbuf = t_headbuf;
        headbuf_len = (size_t)headlen + len + 1;
      }
      head.flags = head.flags & ~HEAD_FLAG_MULTIPART;
      memcpy(headbuf + headlen, data, len);
      headlen += (int)len;
      headbuf[headlen] = '\0';
    }
  }
  // Get head string
  if (head.flags & HEAD_FLAG_MULTIPART) {
    // Get address for new comm and add to header
    xmulti = new_comm(NULL, "send", x->type, NULL);
    if ((xmulti == NULL) || (!(xmulti->flags & COMM_FLAG_VALID))) {
      ygglog_error("comm_send_multipart: Failed to initialize a new comm.");
      free(headbuf);
      return -1;
    }
    xmulti->const_flags[0] = xmulti->const_flags[0] | COMM_EOF_SENT | COMM_EOF_RECV;
    xmulti->flags = xmulti->flags | COMM_FLAG_WORKER;
    strcpy(head.address, xmulti->address);
    if (xmulti->type == ZMQ_COMM) {
      char *reply_address = set_reply_send(xmulti);
      if (reply_address == NULL) {
	ygglog_error("comm_send_multipart: Could not set worker reply address.");
	return -1;
      }
      strcpy(head.zmq_reply_worker, reply_address);
      ygglog_debug("comm_send_multipart: zmq worker reply address is '%s'",
		   head.zmq_reply_worker);
    }
    headlen = format_comm_header(&head, &headbuf, headbuf_len,
				 x->maxMsgSize - x->msgBufSize,
				 no_type);
    if (headlen < 0) {
      ygglog_error("comm_send_multipart: Failed to format header.");
      free(headbuf);
      if (xmulti != NULL) {
	free_comm(xmulti);
      }
      return -1;
    }
  }
  // Send header
  size_t data_in_header = 0;
  if ((head.flags & HEAD_TYPE_IN_DATA) && ((size_t)headlen > (x->maxMsgSize - x->msgBufSize))) {
    ret = comm_send_single(x, headbuf, x->maxMsgSize - x->msgBufSize);
    data_in_header = headlen - (x->maxMsgSize - x->msgBufSize);
  } else {
    ret = comm_send_single(x, headbuf, headlen);
  }
  if (ret < 0) {
    ygglog_error("comm_send_multipart: Failed to send header.");
    if (xmulti != NULL) {
      free_comm(xmulti);
    }
    free(headbuf);
    return -1;
  }
  if (!(head.flags & HEAD_FLAG_MULTIPART)) {
    ygglog_debug("comm_send_multipart(%s): %d bytes completed", x->name, head.size);
    free(headbuf);
    return ret;
  }
  // Send data stored in header
  size_t msgsiz;
  size_t prev = headlen - data_in_header;
  while (prev < (size_t)headlen) {
    if ((headlen - prev) > (xmulti->maxMsgSize - xmulti->msgBufSize)) {
      msgsiz = xmulti->maxMsgSize - xmulti->msgBufSize;
    } else {
      msgsiz = headlen - prev;
    }
    ret = comm_send_single(xmulti, headbuf + prev, msgsiz);
    if (ret < 0) {
      ygglog_debug("comm_send_multipart(%s): send of data in header interupted at %d of %d bytes.",
		   x->name, prev - (headlen - data_in_header), data_in_header);
      break;
    }
    prev += msgsiz;
    ygglog_debug("comm_send_multipart(%s): %d of %d bytes sent from data in header",
		 x->name, prev - (headlen - data_in_header), data_in_header);
  }
  head.size = head.size - data_in_header;
  if (ret < 0) {
    ygglog_error("comm_send_multipart: Failed to send data from header.");
    if (xmulti != NULL) {
      free_comm(xmulti);
    }
    free(headbuf);
    return -1;
  }
  // Send multipart
  prev = 0;
  while (prev < head.size) {
    if ((head.size - prev) > (xmulti->maxMsgSize - xmulti->msgBufSize)) {
      msgsiz = xmulti->maxMsgSize - xmulti->msgBufSize;
    } else {
      msgsiz = head.size - prev;
    }
    ret = comm_send_single(xmulti, data + prev, msgsiz);
    if (ret < 0) {
      ygglog_debug("comm_send_multipart(%s): send interupted at %d of %d bytes.",
		   x->name, prev, head.size);
      break;
    }
    prev += msgsiz;
    ygglog_debug("comm_send_multipart(%s): %d of %d bytes sent",
		 x->name, prev, head.size);
  }
  if (ret == 0)
    ygglog_debug("comm_send_multipart(%s): %d bytes completed", x->name, head.size);
  // Free multipart
  if (xmulti != NULL) {
    free_comm(xmulti);
  }
  free(headbuf);
  if (ret >= 0)
    x->const_flags[0] = x->const_flags[0] | COMM_FLAGS_USED;
  return ret;
};


/*!
  @brief Send a message to the comm.
  Send a message smaller than YGG_MSG_MAX bytes to an output comm. If the
  message is larger, it will not be sent.
  @param[in] x comm_t* structure that comm should be sent to.
  @param[in] data character pointer to message that should be sent.
  @param[in] len size_t length of message to be sent.
  @returns int 0 if send succesfull, -1 if send unsuccessful.
 */
static
int comm_send(const comm_t *x, const char *data, const size_t len) {
  int ret = -1;
  if ((x == NULL) || (!(x->flags & COMM_FLAG_VALID))) {
    ygglog_error("comm_send: Invalid comm");
    return ret;
  }
  if (x->const_flags == NULL) {
    ygglog_error("comm_send(%s): const_flags not initialized.", x->name);
    return ret;
  }
  int sending_eof = 0;
  if (is_eof(data)) {
    if (x->const_flags[0] & COMM_EOF_SENT) {
      ygglog_debug("comm_send(%s): EOF already sent", x->name);
      return ret;
    } else if (!(check_threaded_eof(x))) {
      ygglog_debug("comm_send(%s): EOF not sent on other threads", x->name);
      set_sent_eof(x);
      return 0;
    } else {
      set_sent_eof(x);
      sending_eof = 1;
      ygglog_debug("comm_send(%s): Sending EOF", x->name);
    }
  }
  if (((len > x->maxMsgSize) && (x->maxMsgSize > 0)) ||
      (((x->flags & COMM_ALWAYS_SEND_HEADER) ||
	(!(x->const_flags[0] & COMM_FLAGS_USED))))) {
    ygglog_debug("comm_send(%s): Sending as one or more messages with a header.",
		 x->name);
    ret = comm_send_multipart(x, data, len);
  } else {
    ygglog_debug("comm_send(%s): Sending as single message without a header.",
		 x->name);
    ret = comm_send_single(x, data, len);
  }
  if (sending_eof) {
    ygglog_debug("comm_send(%s): sent EOF, ret = %d", x->name, ret);
  }
  if (ret >= 0)
    x->const_flags[0] = x->const_flags[0] | COMM_FLAGS_USED;
  return ret;
};

/*!
  @brief Send EOF message to the comm.
  @param[in] x comm_t structure that message should be sent to.
  @returns int 0 if send successfull, -1 otherwise.
*/
static
int comm_send_eof(const comm_t *x) {
  int ret = -1;
  char buf[100] = YGG_MSG_EOF;
  ret = comm_send(x, buf, strlen(buf));
  return ret;
};

/*!
  @brief Receive a message from an input comm.
  Receive a message smaller than YGG_MSG_MAX bytes from an input comm.
  @param[in] x comm_t* structure that message should be sent to.
  @param[out] data char ** pointer to allocated buffer where the message
  should be saved. This should be a malloc'd buffer if allow_realloc is 1.
  @param[in] len const size_t length of the allocated message buffer in bytes.
  @param[in] allow_realloc const int If 1, the buffer will be realloced if it
  is not large enought. Otherwise an error will be returned.
  @returns int -1 if message could not be received, otherwise the length of
  the received message.
 */
static
int comm_recv_single(comm_t *x, char **data, const size_t len,
		     const int allow_realloc) {
  int ret = -1;
  if ((x == NULL) || (!(x->flags & COMM_FLAG_VALID))) {
    ygglog_error("comm_recv_single: Invalid comm");
    return ret;
  }
  if (!(thread_can_use(x->thread_id))) {
    ygglog_error("comm_recv_single: Thread is attempting to use a comm it did not initialize");
    return ret;
  }
  comm_type t = x->type;
  if (t == IPC_COMM)
    ret = ipc_comm_recv(x, data, len, allow_realloc);
  else if (t == ZMQ_COMM)
    ret = zmq_comm_recv(x, data, len, allow_realloc);
  else if (t == SERVER_COMM)
    ret = server_comm_recv(x, data, len, allow_realloc);
  else if (t == CLIENT_COMM)
    ret = client_comm_recv(x, data, len, allow_realloc);
  else if (t == ASCII_FILE_COMM)
    ret = ascii_file_comm_recv(x, data, len, allow_realloc);
  else if ((t == ASCII_TABLE_COMM) || (t == ASCII_TABLE_ARRAY_COMM))
    ret = ascii_table_comm_recv(x, data, len, allow_realloc);
  else {
    ygglog_error("comm_recv: Unsupported comm_type %d", t);
  }
  return ret;
};

/*!
  @brief Receive a message in multiple parts.
  @param[in] x comm_t* Comm that message should be recieved from.
  @param[in] data char ** Pointer to buffer where message should be stored.
  @param[in] len size_t Size of data buffer.
  @param[in] headlen size_t Size of header in data buffer.
  @param[in] allow_realloc int If 1, data will be realloced if the incoming
  message is larger than the buffer. Otherwise, an error will be returned.
  @returns int -1 if unsucessful, size of message received otherwise.
*/
static
int comm_recv_multipart(comm_t *x, char **data, const size_t len,
			const size_t headlen, const int allow_realloc) {
  int ret = -1;
  if ((x == NULL) || (!(x->flags & COMM_FLAG_VALID))) {
    ygglog_error("comm_recv_multipart: Invalid comm");
    return ret;
  }
  usleep(100);
  comm_head_t head = parse_comm_header(*data, headlen);
  if (!(head.flags & HEAD_FLAG_VALID)) {
    ygglog_error("comm_recv_multipart(%s): Error parsing header.", x->name);
    ret = -1;
  } else {
    // Move body to front of data and return if EOF
    memmove(*data, *data + head.bodybeg, head.bodysiz);
    (*data)[head.bodysiz] = '\0';
    if (is_eof(*data)) {
      ygglog_debug("comm_recv_multipart(%s): EOF received.", x->name);
      x->const_flags[0] = x->const_flags[0] | COMM_EOF_RECV;
      destroy_header(&head);
      return -2;
    }
    // Get datatype information from header on first recv
    dtype_t *updtype;
    if (x->type == SERVER_COMM) {
      comm_t *handle = (comm_t*)(x->handle);
      updtype = handle->datatype;
    } else {
      updtype = x->datatype;
    }
    if ((!(x->const_flags[0] & COMM_FLAGS_USED)) && (!(x->flags & COMM_FLAG_FILE)) && (updtype->obj == NULL) && (!(head.flags & HEAD_TYPE_IN_DATA))) {
      ygglog_debug("comm_recv_multipart(%s): Updating datatype to '%s'",
		   x->name, head.dtype->type);
      ret = update_dtype(updtype, head.dtype);
      if (ret != 0) {
	ygglog_error("comm_recv_multipart(%s): Error updating datatype.", x->name);
	destroy_header(&head);
	return -1;
      }
    } else if ((!(x->flags & COMM_FLAG_FILE)) && (head.dtype != NULL)) {
      ret = update_dtype(updtype, head.dtype);
      if (ret != 0) {
	ygglog_error("comm_recv_multipart(%s): Error updating existing datatype.", x->name);
	destroy_header(&head);
	return -1;
      }
    }
    if (head.flags & HEAD_FLAG_MULTIPART) {
      // Return early if header contained entire message
      if (head.size == head.bodysiz) {
        x->const_flags[0] = x->const_flags[0] | COMM_FLAGS_USED;
	destroy_header(&head);
	return (int)(head.bodysiz);
      }
      // Get address for new comm
      comm_t* xmulti = new_comm(head.address, "recv", x->type, NULL);
      if ((xmulti == NULL) || (!(xmulti->flags & COMM_FLAG_VALID))) {
	ygglog_error("comm_recv_multipart: Failed to initialize a new comm.");
	destroy_header(&head);
	return -1;
      }
      xmulti->const_flags[0] = xmulti->const_flags[0] | COMM_EOF_SENT | COMM_EOF_RECV;
      xmulti->flags = xmulti->flags | COMM_FLAG_WORKER;
      if (xmulti->type == ZMQ_COMM) {
	int reply_socket = set_reply_recv(xmulti, head.zmq_reply_worker);
	if (reply_socket < 0) {
	  ygglog_error("comm_recv_multipart: Failed to set worker reply address.");
	  destroy_header(&head);
	  return -1;
	}
      }
      // Receive parts of message
      size_t prev = head.bodysiz;
      size_t msgsiz = 0;
      // Reallocate data if necessary
      if ((head.size + 1) > len) {
	if (allow_realloc) {
	  char *t_data = (char*)realloc(*data, head.size + 1);
	  if (t_data == NULL) {
	    ygglog_error("comm_recv_multipart(%s): Failed to realloc buffer",
			 x->name);
	    free(*data);
	    free_comm(xmulti);
	    destroy_header(&head);
	    return -1;
	  }
	  *data = t_data;
 	} else {
	  ygglog_error("comm_recv_multipart(%s): buffer is not large enough",
		       x->name);
	  free_comm(xmulti);
	  destroy_header(&head);
	  return -1;
	}
      }
      ret = -1;
      char *pos = (*data) + prev;
      while (prev < head.size) {
	msgsiz = head.size - prev + 1;
	ret = comm_recv_single(xmulti, &pos, msgsiz, 0);
	if (ret < 0) {
	  ygglog_debug("comm_recv_multipart(%s): recv interupted at %d of %d bytes.",
		       x->name, prev, head.size);
	  break;
	}
	prev += ret;
	pos += ret;
	ygglog_debug("comm_recv_multipart(%s): %d of %d bytes received",
		     x->name, prev, head.size);
      }
      if ((ret > 0) && (head.flags & HEAD_TYPE_IN_DATA)) {
	ygglog_debug("comm_recv_multipart(%s): Extracting type from data.");
	ret = parse_type_in_data(data, prev, &head);
	if (ret > 0) {
	  prev = ret;
	  ret = update_dtype(updtype, head.dtype);
	  if (ret != 0) {
	    ygglog_error("comm_recv_multipart(%s): Error updating existing datatype.", x->name);
	    destroy_header(&head);
	    return -1;
	  } else {
	    ret = (int)prev;
	  }
	}
      }
      if (ret > 0) {
	ygglog_debug("comm_recv_multipart(%s): %d bytes completed", x->name, prev);
	ret = (int)prev;
      }
      free_comm(xmulti);
    } else {
      ret = (int)(head.bodysiz);
    }
  }
  if (ret >= 0)
    x->const_flags[0] = x->const_flags[0] | COMM_FLAGS_USED;
  destroy_header(&head);
  return ret;
};

/*!
  @brief Receive a message from an input comm.
  An error will be returned if the buffer is not large enough.
  @param[in] x comm_t* structure that message should be sent to.
  @param[out] data character pointer to allocated buffer where the
  message should be saved.
  @param[in] len const size_t length of the allocated message buffer in bytes.
  @returns int -1 if message could not be received and -2 if EOF is received.
  Length of the received message otherwise.
 */
static
int comm_recv(comm_t *x, char *data, const size_t len) {
  int ret = comm_recv_single(x, &data, len, 0);
  if (ret > 0) {
    if (is_eof(data)) {
      ygglog_debug("comm_recv(%s): EOF received.", x->name);
      x->const_flags[0] = x->const_flags[0] | COMM_EOF_RECV;
      ret = -2;
    } else {
      ret = comm_recv_multipart(x, &data, len, ret, 0);
    }
  } else {
    ygglog_error("comm_recv(%s): Failed to receive header or message.",
      x->name);
  }
  return ret;
};

/*!
  @brief Receive a message from an input comm, reallocating as necessary.
  @param[in] x comm_t* structure that message should be sent to.
  @param[out] data character pointer to pointer to allocated buffer where the
  message should be saved.
  @param[in] len const size_t length of the allocated message buffer in bytes.
  @returns int -1 if message could not be received and -2 if EOF is received.
  Length of the received message otherwise.
 */
static
int comm_recv_realloc(comm_t *x, char **data, const size_t len) {
  int ret = comm_recv_single(x, data, len, 1);
  if (ret > 0) {
    if (is_eof(*data)) {
      ygglog_debug("comm_recv_realloc(%s): EOF received.", x->name);
      x->const_flags[0] = x->const_flags[0] | COMM_EOF_RECV;
      ret = -2;
    } else {
      ret = comm_recv_multipart(x, data, len, ret, 1);
    }
  } else {
    ygglog_error("comm_recv_realloc(%s): Failed to receive header or message.",
      x->name);
  }
  return ret;
};


/*! @brief alias for comm_send. */
static
int comm_send_nolimit(const comm_t *x, const char *data, const size_t len) {
  return comm_send(x, data, len);
};

/*!
  @brief Send EOF message to the comm.
  @param[in] x comm_t* structure that message should be sent to.
  @returns int 0 if send successfull, -1 otherwise.
*/
static
int comm_send_nolimit_eof(const comm_t *x) {
  int ret = -1;
  if ((x == NULL) || (!(x->flags & COMM_FLAG_VALID))) {
    ygglog_error("comm_send_nolimit_eof: Invalid comm");
    return ret;
  }
  if (x->const_flags == NULL) {
    ygglog_error("comm_send_nolimit_eof(%s): const_flags not initialized.", x->name);
    return ret;
  }
  if (!(x->const_flags[0] & COMM_EOF_SENT)) {
    char buf[2048] = YGG_MSG_EOF;
    ret = comm_send_nolimit(x, buf, strlen(buf));
    set_sent_eof(x);
  } else {
    ygglog_debug("comm_send_nolimit_eof(%s): EOF already sent", x->name);
  }
  return ret;
};

/*!
  @brief Receive a large message from an input comm.
  Receive a message larger than YGG_MSG_MAX bytes from an input comm by
  receiving it in parts. This expects the first message to be the size of
  the total message.
  @param[in] x comm_t structure that message should be sent to.
  @param[out] data character pointer to pointer for allocated buffer where the
  message should be stored. A pointer to a pointer is used so that the buffer
  may be reallocated as necessary for the incoming message.
  @param[in] len size_t length of the initial allocated message buffer in bytes.
  @returns int -1 if message could not be received and -2 if EOF is received.
  Length of the received message otherwise.
 */
static
int comm_recv_nolimit(comm_t *x, char **data, const size_t len) {
  return comm_recv_realloc(x, data, len);
};

/*!
  @brief Send arguments as a small formatted message to an output comm.
  Use the format string to create a message from the input arguments that
  is then sent to the specified output comm. If the message is larger than
  YGG_MSG_MAX or cannot be encoded, it will not be sent.  
  @param[in] x comm_t* structure for comm that message should be sent to.
  @param[in] nargs size_t Number of arguments in the variable argument list.
  @param[in] ap va_list arguments to be formatted into a message using sprintf.
  @returns int Number of arguments formatted if send succesfull, -1 if send
  unsuccessful.
 */
static
int vcommSend(const comm_t *x, size_t nargs, va_list_t ap) {
  ygglog_debug("vcommSend: Formatting %lu arguments.", nargs);
  int ret = -1;
  if ((x == NULL) || (!(x->flags & COMM_FLAG_VALID))) {
    ygglog_error("vcommSend: Invalid comm");
    return ret;
  }
  size_t buf_siz = YGG_MSG_BUF;
  // char *buf = NULL;
  char *buf = (char*)malloc(buf_siz);
  if (buf == NULL) {
    ygglog_error("vcommSend(%s): Failed to alloc buffer", x->name);
    return -1;
  }
  dtype_t *datatype = x->datatype;
  if (x->type == CLIENT_COMM) {
    comm_t *handle = (comm_t*)(x->handle);
    datatype = handle->datatype;
  }
  // Update datatype if not yet set and object being sent includes type
  if (update_dtype_from_generic_ap(datatype, nargs, ap) < 0) {
    return -1;
  }
  size_t nargs_orig = nargs;
  ret = serialize_dtype(datatype, &buf, &buf_siz, 1, &nargs, ap);
  if (ret < 0) {
    ygglog_error("vcommSend(%s): serialization error", x->name);
    free(buf);
    return -1;
  }
  ret = comm_send(x, buf, ret);
  ygglog_debug("vcommSend(%s): comm_send returns %d, nargs (remaining) = %d",
	       x->name, ret, nargs);
  free(buf);
  if (ret < 0) {
    return ret;
  } else {
    return (int)(nargs_orig - nargs);
  }
};

/*!
  @brief Send arguments as a formatted message to an output comm.
  Use the format string to create a message from the input arguments that
  is then sent to the specified output comm.
  @param[in] x comm_t structure for comm that message should be sent to.
  @param[in] nargs size_t Number of variable arguments provided.
  @param[in] ... Arguments to be formatted into a message using sprintf.
  @returns int Number of arguments formatted if send succesfull, -1 if send
  unsuccessful.
*/
static
int ncommSend(const comm_t *x, size_t nargs, ...) {
  va_list_t ap = init_va_list();
  va_start(ap.va, nargs);
  ygglog_debug("ncommSend: nargs = %d", nargs);
  int ret = vcommSend(x, nargs, ap);
  va_end(ap.va);
  return ret;
};
#define commSend(x, ...) ncommSend(x, COUNT_VARARGS(__VA_ARGS__), __VA_ARGS__)

/*!
  @brief Assign arguments by receiving and parsing a message from an input comm.
  Receive a message smaller than YGG_MSG_MAX bytes from an input comm and parse
  it using the associated format string.
  @param[in] x comm_t structure for comm that message should be sent to.
  @param[in] allow_realloc int If 1, variables being filled are assumed to be
  pointers to pointers for heap memory. If 0, variables are assumed to be pointers
  to stack memory. If allow_realloc is set to 1, but stack variables are passed,
  a segfault can occur.
  @param[in] nargs size_t Number of arguments in the variable argument list.
  @param[out] ap va_list arguments that should be assigned by parsing the
  received message using sscanf. As these are being assigned, they should be
  pointers to memory that has already been allocated.
  @returns int -1 if message could not be received or could not be parsed.
  Length of the received message if message was received and parsed. -2 is
  returned if EOF is received.
 */
static
int vcommRecv(comm_t *x, const int allow_realloc, size_t nargs, va_list_t ap) {
  int ret = -1;
  ygglog_debug("vcommRecv: Parsing %lu arguments.", nargs);
  if ((x == NULL) || (!(x->flags & COMM_FLAG_VALID))) {
    ygglog_error("vcommRecv: Invalid comm");
    return ret;
  }
  // Receive message
  size_t buf_siz = YGG_MSG_BUF;
  /* char *buf = NULL; */
  char *buf = (char*)malloc(buf_siz);
  if (buf == NULL) {
    ygglog_error("vcommRecv(%s): Failed to alloc buffer", x->name);
    return -1;
  }
  ret = comm_recv_nolimit(x, &buf, buf_siz);
  if (ret < 0) {
    // ygglog_error("vcommRecv(%s): Error receiving.", x->name);
    free(buf);
    return ret;
  }
  ygglog_debug("vcommRecv(%s): comm_recv returns %d: %.10s...", x->name, ret, buf);
  // Deserialize message
  dtype_t *datatype = x->datatype;
  if (x->type == SERVER_COMM) {
    comm_t *handle = (comm_t*)(x->handle);
    datatype = handle->datatype;
  }
  ret = deserialize_dtype(datatype, buf, ret, allow_realloc, &nargs, ap);
  if (ret < 0) {
    ygglog_error("vcommRecv(%s): error deserializing message (ret=%d)",
		 x->name, ret);
    free(buf);
    return -1;
  }
  ygglog_debug("vcommRecv(%s): deserialize_format returns %d", x->name, ret);
  free(buf);
  return ret;
};

/*!
  @brief Assign arguments by receiving and parsing a message from an input comm.
  Receive a message from an input comm and parse it using the associated type.
  @param[in] x comm_t* structure for comm that message should be sent to.
  @param[in] allow_realloc int If 1, variables being filled are assumed to be
  pointers to pointers for heap memory. If 0, variables are assumed to be pointers
  to stack memory. If allow_realloc is set to 1, but stack variables are passed,
  a segfault can occur.
  @param[in] nargs size_t Number of variable arguments provided.
  @param[out] ... arguments that should be assigned by parsing the
  received message using sscanf. As these are being assigned, they should be
  pointers to memory that has already been allocated.
  @returns int -1 if message could not be received or could not be parsed.
  Length of the received message if message was received and parsed. -2 is
  returned if EOF is received.
 */
static
int ncommRecv(comm_t *x, const int allow_realloc, size_t nargs, ...) {
  va_list_t ap = init_va_list();
  va_start(ap.va, nargs);
  ygglog_debug("ncommRecv: nargs = %d", nargs);
  int ret = vcommRecv(x, allow_realloc, nargs, ap);
  va_end(ap.va);
  return ret;
};
#define commRecvStack(x, ...) ncommRecv(x, 0, COUNT_VARARGS(__VA_ARGS__), __VA_ARGS__)
#define commRecvHeap(x, ...) ncommRecv(x, 1, COUNT_VARARGS(__VA_ARGS__), __VA_ARGS__)
#define commRecv commRecvStack
#define commRecvRealloc commRecvHeap


#define vcommSend_nolimit vcommSend
#define vcommRecv_nolimit vcommRecv

#ifdef __cplusplus /* If this is a C++ compiler, end C linkage */
}
#endif

#endif /*YGGCOMMUNICATION_H_*/
