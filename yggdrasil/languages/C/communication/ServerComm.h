/*! @brief Flag for checking if this header has already been included. */
#ifndef YGGSERVERCOMM_H_
#define YGGSERVERCOMM_H_

#include <CommBase.h>
#include <DefaultComm.h>
#include "../datatypes/datatypes.h"

#ifdef __cplusplus /* If this is a C++ compiler, use C linkage */
extern "C" {
#endif

// Handle is recv address
// Info is response

// @brief Structure for storing requests
typedef struct requests_t {
  size_t ncomm; //!< Number of response comms.
  comm_t** comms; //!< Array of response comms.
  size_t nreq; //!< Number of requests.
  char** response_id; //!< Response ids.
  char** request_id; //!< Request ids.
  size_t* comm_idx; //!< Index of comm associated w/ a request
} requests_t;

/*!
  @brief Create a new registry of requests.
  @param[in] datatype dtype_t* Data type to copy and use for all response
  comms.
  @returns requests_t* Structure containing a registry of requests.
 */
static inline
requests_t* server_new_requests(const dtype_t* datatype) {
  requests_t* out = (requests_t*)malloc(sizeof(requests_t));
  if (out != NULL) {
    out->ncomm = 0;
    out->comms = NULL;
    out->nreq = 0;
    out->response_id = NULL;
    out->request_id = NULL;
    out->comm_idx = NULL;
  }
  return out;
};

/*!
  @brief Free a registry of requests.
  @param[in] x requests_t** Pointer to structure containing a registry.
*/
static inline
void server_free_requests(requests_t** x) {
  if (x[0] != NULL) {
    if (x[0]->comms != NULL) {
      for (size_t i = 0; i < x[0]->ncomm; i++) {
	if (x[0]->comms[i] != NULL) {
	  free_default_comm(x[0]->comms[i]);
	  free_comm_base(x[0]->comms[i]);
	  x[0]->comms[i] = NULL;
	}
      }
      free(x[0]->comms);
      x[0]->comms = NULL;
    }
    x[0]->ncomm = 0;
    if (x[0]->response_id != NULL) {
      for (size_t i = 0; i < x[0]->nreq; i++) {
	if (x[0]->response_id[i] != NULL) {
	  free(x[0]->response_id[i]);
	  x[0]->response_id[i] = NULL;
	}
      }
      free(x[0]->response_id);
      x[0]->response_id = NULL;
    }
    if (x[0]->request_id != NULL) {
      for (size_t i = 0; i < x[0]->nreq; i++) {
	if (x[0]->request_id[i] != NULL) {
	  free(x[0]->request_id[i]);
	  x[0]->request_id[i] = NULL;
	}
      }
      free(x[0]->request_id);
      x[0]->request_id = NULL;
    }
    if (x[0]->comm_idx != NULL) free(x[0]->comm_idx);
    x[0]->nreq = 0;
    free(x[0]);
    x[0] = NULL;
  }
};

/*!
  @brief Determine if there is a request in the registry.
  @param[in] x requests_t* Structure containing a registry of requests.
  @param[in] request_id const char* ID associated with the request to check for.
  @returns int -1 if there is an error, otherwise the index of the request
  in the registry.
*/
static inline
int server_has_request(requests_t *x, const char* request_id) {
  if (x == NULL) return -1;
  for (size_t i = 0; i < x->nreq; i++) {
    if (strcmp(x->request_id[i], request_id) == 0)
      return (int)i;
  }
  return -1;
};

/*!
  @brief Determine if there is a response in the registry.
  @param[in] x requests_t* Structure containing a registry of requests.
  @param[in] response_id const char* ID associated with the response to check for.
  @returns int -1 if there is an error, otherwise the index of the response
  in the registry.
*/
static inline
int server_has_response(requests_t *x, const char* response_id) {
  if (x == NULL) return -1;
  ygglog_debug("server_has_response: nreq = %ld", x->nreq);
  for (size_t i = 0; i < x->nreq; i++) {
    if (strcmp(x->response_id[i], response_id) == 0)
      return (int)i;
  }
  return -1;
};

/*!
  @brief Determine if there is a response in the registry.
  @param[in] x requests_t* Structure containing a registry of requests.
  @param[in] response_address const char* Address to check for.
  @returns int -1 if there is an error, otherwise the index of the comm
  in the registry.
*/
static inline
int server_has_comm(requests_t *x, const char* response_address) {
  if (x == NULL) return 0;
  for (size_t i = 0; i < x->ncomm; i++) {
    if (strcmp(x->comms[i]->address, response_address) == 0)
      return (int)i;
  }
  return -1;
};

/*!
  @brief Add a comm to the registry.
  @param[in] x requests_t* Structure containing a registry of requests.
  @param[in] response_address char* Address to create a comm for.
  @param[in] datatype const dtype_t* Data type that should be copied.
  @returns int -1 if there is an error, 0 otherwise.
 */
static inline
int server_add_comm(requests_t *x, char* response_address,
		    const dtype_t* datatype) {
  if (x == NULL) return -1;
  x->comms = (comm_t**)realloc(x->comms, (x->ncomm + 1) * sizeof(comm_t*));
  if (x->comms == NULL) return -1;
  x->comms[x->ncomm] = NULL;
  dtype_t* dtype_copy = copy_dtype(datatype);
  if (dtype_copy == NULL) {
    ygglog_error("server_add_comm(%s): Failed to create dtype_copy.",
		 response_address);
    return -1;
  }
  x->comms[x->ncomm] = new_comm_base(response_address, "send",
				     _default_comm, dtype_copy);
  x->comms[x->ncomm]->flags = x->comms[x->ncomm]->flags | COMM_ALLOW_MULTIPLE_COMMS;
  /* sprintf(x->comms[x->ncomm]->name, "server_response.%s",x->comms[x->ncomm]->address); */
  int newret = init_default_comm(x->comms[x->ncomm]);
  if (newret < 0) {
    ygglog_error("server_add_comm(%s): Could not initialize response comm.", response_address);
    return newret;
  }
  x->comms[x->ncomm]->const_flags[0] = x->comms[x->ncomm]->const_flags[0] | COMM_EOF_SENT | COMM_EOF_RECV;
  x->ncomm++;
  ygglog_debug("server_add_comm(%s): Added comm %ld", response_address, x->ncomm);
  return 0;
};

/*!
  @brief Get a comm associated with a request.
  @param[in] x requests_t* Structure containing a registry of requests.
  @param[in] idx size_t Index of request to get comm for.
  @returns comm_t* Response comm associated with the specified request.
 */
static inline
comm_t* server_get_comm(requests_t *x, size_t idx) {
  if (x == NULL) return NULL;
  if (x->nreq == 0) return NULL;
  size_t idx_comm = x->comm_idx[0];
  if (idx_comm >= x->ncomm) return NULL;
  return x->comms[idx_comm];
};

/*!
  @brief Add a request to the registry.
  @param[in] x requests_t* Structure containing a registry of requests.
  @param[in] request_id const char* ID associated with the request being added.
  @param[in] datatype const dtype_t* Data type that should be copied.
  @returns int -1 if there is an error, 0 otherwise.
*/
static inline
int server_add_request(requests_t *x, const char* request_id, char* response_address,
		       const dtype_t* datatype) {
  if (x == NULL) return -1;
  ygglog_debug("server_add_request: adding request %s for address %s",
	       request_id, response_address);
  char response_id[500] = "";
  char uuid[10] = "";
  strcpy(response_id, request_id);
  while (server_has_response(x, response_id) >= 0) {
    sprintf(uuid, "%d", rand());
    strcat(response_id, uuid);
  }
  ygglog_debug("server_add_request: Response id = %s", response_id);
  // request_id
  x->request_id = (char**)realloc(x->request_id, (x->nreq + 1) * sizeof(char*));
  if (x->request_id == NULL) return -1;
  size_t request_len = strlen(request_id);
  x->request_id[x->nreq] = (char*)malloc(request_len + 1);
  if (x->request_id[x->nreq] == NULL) return -1;
  memcpy(x->request_id[x->nreq], request_id, request_len);
  x->request_id[x->nreq][request_len] = '\0';
  // response_id
  x->response_id = (char**)realloc(x->response_id, (x->nreq + 1) * sizeof(char*));
  if (x->response_id == NULL) return -1;
  size_t response_len = strlen(response_id);
  x->response_id[x->nreq] = (char*)malloc(response_len + 1);
  if (x->response_id[x->nreq] == NULL) return -1;
  memcpy(x->response_id[x->nreq], response_id, response_len);
  x->response_id[x->nreq][response_len] = '\0';
  // comm
  int comm_idx = server_has_comm(x, response_address);
  if (comm_idx < 0) {
    if (server_add_comm(x, response_address, datatype) < 0) {
      ygglog_error("server_add_request: Failed to add comm");
      return -1;
    }
    comm_idx = x->ncomm - 1;
    ygglog_debug("server_add_request: Added comm %ld (of %ld), %s",
		 comm_idx, x->ncomm, response_address);
  }
  x->comm_idx = (size_t*)realloc(x->comm_idx, (x->nreq + 1) * sizeof(size_t));
  if (x->comm_idx == NULL) return -1;
  x->comm_idx[x->nreq] = (size_t)comm_idx;
  x->nreq++;
  ygglog_debug("server_add_request: nreq = %ld, comm_idx = %ld",
	       x->nreq, comm_idx);
  return 0;
};

/*!
  @brief Remove a request from the registry.
  @param[in] x requests_t* Structure containing a registry of requests.
  @param[in] idx size_t Index of request that should be removed.
  @returns int -1 if there is an error, 0 otherwise.
*/
static inline
int server_remove_request(requests_t *x, size_t idx) {
  if (x == NULL) return -1;
  if (x->nreq == 0) return -1;
  ygglog_debug("server_remove_request: Removing request %ld", idx);
  int nrem = x->nreq - (idx + 1);
  free(x->request_id[idx]);
  free(x->response_id[idx]);
  if (nrem > 0) {
    memmove(x->request_id + idx, x->request_id + idx + 1, nrem * sizeof(char*));
    memmove(x->response_id + idx, x->response_id + idx + 1, nrem * sizeof(char*));
    memmove(x->comm_idx + idx, x->comm_idx + idx + 1, nrem * sizeof(size_t));
  }
  x->nreq--;
  return 0;
};

/*!
  @brief Create a new channel.
  @param[in] comm comm_t * Comm structure initialized with new_comm_base.
  @returns int -1 if the address could not be created.
*/
static inline
int new_server_address(comm_t *comm) {
  comm->type = _default_comm;
  return new_default_address(comm);
};

/*!
  @brief Initialize a server communicator.
  @param[in] comm comm_t * Comm structure initialized with init_comm_base.
  @returns int -1 if the comm could not be initialized.
 */
static inline
int init_server_comm(comm_t *comm) {
  int ret = 0;
  // Called to create temp comm for send/recv
  if ((strlen(comm->name) == 0) && (strlen(comm->address) > 0)) {
    comm->type = _default_comm;
    return init_default_comm(comm);
  }
  // Called to initialize/create server comm
  dtype_t *dtype_in = create_dtype_format(comm->direction, 0, false);
  if (dtype_in == NULL) {
    ygglog_error("init_server_comm: Failed to create dtype_in.");
    return -1;
  }
  comm_t *handle;
  if (strlen(comm->name) == 0) {
    handle = new_comm_base(comm->address, "recv", _default_comm, dtype_in);
    sprintf(handle->name, "server_request.%s", comm->address);
  } else {
    handle = init_comm_base(comm->name, "recv", _default_comm, dtype_in);
  }
  handle->flags = handle->flags | COMM_FLAG_SERVER;
  ret = init_default_comm(handle);
  strcpy(comm->address, handle->address);
  // printf("init_server_comm: name = %s, type=%d, address = %s\n",
  // 	 handle->name, handle->type, handle->address);
  strcpy(comm->direction, "recv");
  comm->handle = (void*)handle;
  comm->flags = comm->flags | COMM_ALWAYS_SEND_HEADER;
  requests_t* info = server_new_requests(comm->datatype);
  if (info == NULL) {
    ygglog_error("init_server_comm: Failed to malloc info.");
    return -1;
  }
  comm->info = (void*)info;
  return ret;
};

/*!
  @brief Perform deallocation for server communicator.
  @param[in] x comm_t* Pointer to communicator to deallocate.
  @returns int 1 if there is and error, 0 otherwise.
*/
static inline
int free_server_comm(comm_t *x) {
  if (x->handle != NULL) {
    comm_t *handle = (comm_t*)(x->handle);
    free_default_comm(handle);
    free_comm_base(handle);
    free(x->handle);
    x->handle = NULL;
  }
  if (x->info != NULL) {
    requests_t* info = (requests_t*)(x->info);
    server_free_requests(&info);
  }
  return 0;
};

/*!
  @brief Get number of messages in the comm.
  @param[in] x comm_t* Communicator to check.
  @returns int Number of messages. -1 indicates an error.
 */
static inline
int server_comm_nmsg(const comm_t* x) {
  comm_t *handle = (comm_t*)(x->handle);
  int ret = default_comm_nmsg(handle);
  return ret;
};

/*!
  @brief Add request info to the header.
  @param[in] x comm_t* structure that header will be sent to.
  @param[in] head comm_head_t Prexisting header structure.
  @returns comm_head_t Header structure that includes the additional
  information about the response comm.
*/
static inline
comm_head_t server_response_header(const comm_t* x, comm_head_t head) {
  requests_t* info = (requests_t*)(x->info);
  if ((info == NULL) || (info->nreq == 0)) {
    ygglog_error("server_response_header(%s): There are not any registered requests.",
		 x->name);
    head.flags = head.flags & ~HEAD_FLAG_VALID;
    return head;
  }
  // Add request ID to header
  strcpy(head.request_id, info->request_id[0]);
  ygglog_debug("server_response_header(%s): request_id = %s",
	       x->name, head.request_id);
  return head;
};

/*!
  @brief Send a message to the comm.
  @param[in] x comm_t* structure that comm should be sent to.
  @param[in] data character pointer to message that should be sent.
  @param[in] len size_t length of message to be sent.
  @returns int 0 if send succesfull, -1 if send unsuccessful.
 */
static inline
int server_comm_send(const comm_t* x, const char *data, const size_t len) {
  ygglog_debug("server_comm_send(%s): %d bytes", x->name, len);
  if (x->info == NULL) {
    ygglog_error("server_comm_send(%s): no response comm registered", x->name);
    return -1;
  }
  requests_t* info = (requests_t*)(x->info);
  comm_t* response_comm = server_get_comm(info, 0);
  if (response_comm == NULL) {
    ygglog_error("server_comm_send(%s): Failed to get response comm", x->name);
    return -1;
  }
  int ret = default_comm_send(response_comm, data, len);
  ygglog_debug("server_comm_send(%s): Sent %d bytes", x->name, len);
  if (server_remove_request(info, 0) < 0) return -1;
  return ret;
};

/*!
  @brief Receive a message from an input comm.
  @param[in] x comm_t* structure that message should be sent to.
  @param[out] data char ** pointer to allocated buffer where the message
  should be saved. This should be a malloc'd buffer if allow_realloc is 1.
  @param[in] len const size_t length of the allocated message buffer in bytes.
  @param[in] allow_realloc const int If 1, the buffer will be realloced if it
  is not large enought. Otherwise an error will be returned.
  @returns int -1 if message could not be received. Length of the received
  message if message was received.
 */
static inline
int server_comm_recv(comm_t* x, char **data, const size_t len, const int allow_realloc) {
  ygglog_debug("server_comm_recv(%s)", x->name);
  if (x->handle == NULL) {
    ygglog_error("server_comm_recv(%s): no request comm registered", x->name);
    return -1;
  }
  comm_t *req_comm = (comm_t*)(x->handle);
  int ret = default_comm_recv(req_comm, data, len, allow_realloc);
  if (ret < 0) {
    return ret;
  }
  // Return EOF
  if (is_eof(*data)) {
    req_comm->const_flags[0] = req_comm->const_flags[0] | COMM_EOF_RECV;
    return ret;
  }
  // Initialize new comm from received address
  comm_head_t head = parse_comm_header(*data, ret);
  if (!(head.flags & HEAD_FLAG_VALID)) {
    ygglog_error("server_comm_recv(%s): Error parsing header.", x->name);
    return -1;
  }
  // Return EOF
  if (is_eof((*data) + head.bodybeg)) {
    req_comm->const_flags[0] = req_comm->const_flags[0] | COMM_EOF_RECV;
    return ret;
  }
  // On client sign off, do a second recv
  if (strcmp((*data) + head.bodybeg, YGG_CLIENT_EOF) == 0) {
    return server_comm_recv(x, data, len, allow_realloc);
  }
  // If there is not a response address
  if (strlen(head.response_address) == 0) {
    ygglog_error("server_comm_recv(%s): No response address in message.", x->name);
    return -1;
  }
  strcpy(x->address, head.id);
  requests_t *info = (requests_t*)(x->info);
  if (server_add_request(info, head.request_id, head.response_address,
			 x->datatype) < 0) return -1;
  return ret;
};

#ifdef __cplusplus /* If this is a C++ compiler, end C linkage */
}
#endif

#endif /*YGGSERVERCOMM_H_*/
