/*! @brief Flag for checking if this header has already been included. */
#ifndef YGGCLIENTCOMM_H_
#define YGGCLIENTCOMM_H_

#include <../tools.h>
#include <CommBase.h>
#include <DefaultComm.h>
#include "../datatypes/datatypes.h"

#ifdef __cplusplus /* If this is a C++ compiler, use C linkage */
extern "C" {
#endif

// Handle is send address
// Info is response
static unsigned _client_rand_seeded = 0;

// @brief Structure for storing requests/responses
typedef struct responses_t {
  comm_t* comm; //!< Response comm.
  size_t nreq; //!< Number of requests sent.
  char** request_id; //!< Request ids.
  char** data; //!< Received responses
  size_t* len; //!< Lengths of received messages.
} responses_t;
  
/*!
  @brief Create a new registry of requests and responses.
  @returns responses_t* Structure containing a registry of requests and
  responses.
*/
static inline
responses_t* client_new_responses() {
  responses_t* out = (responses_t*)malloc(sizeof(responses_t));
  if (out != NULL) {
    out->comm = NULL;
    out->nreq = 0;
    out->request_id = NULL;
    out->data = NULL;
    out->len = NULL;
  }
  return out;
};

/*!
  @brief Free a registry of requests and responses.
  @param[in] x responses_t** Pointer to structure containing a registry of
  requests and responses.
*/
static inline
void client_free_responses(responses_t** x) {
  if (x[0] != NULL) {
    if (x[0]->comm != NULL) {
      free_default_comm(x[0]->comm);
      free_comm_base(x[0]->comm);
    }
    if (x[0]->data != NULL) {
      for (size_t i = 0; i < x[0]->nreq; i++)
	if (x[0]->data[i] != NULL) free(x[0]->data[i]);
      free(x[0]->data);
    }
    if (x[0]->len != NULL)
      free(x[0]->len);
    free(x[0]);
    x[0] = NULL;
  }
};

/*!
  @brief Determine if there is a request in the registry.
  @param[in] x responses_t* Structure containing a registry of requests and
  responses.
  @param[in] request_id const char* ID associated with the request to check for.
  @returns int -1 if there is an error, otherwise the index of the request
  in the registry.
*/
static inline
int client_has_request(responses_t *x, const char* request_id) {
  if (x == NULL) return -1;
  for (size_t i = 0; i < x->nreq; i++) {
    if (strcmp(x->request_id[i], request_id) == 0)
      return (int)i;
  }
  return -1;
};

/*!
  @brief Determine if there is a response in the registry.
  @param[in] x responses_t* Structure containing a registry of requests and
  responses.
  @param[in] request_id const char* ID associated with the response to check for.
  @returns int -1 if there is an error, otherwise the index of the response
  in the registry.
*/
static inline
int client_has_response(responses_t *x, const char* request_id) {
  int idx = client_has_request(x, request_id);
  if (idx < 0) return idx;
  if (x->data[idx] != NULL) return idx;
  return -1;
};

/*!
  @brief Add a request to the registry.
  @param[in] x responses_t* Structure containing a registry of requests and
  responses.
  @param[in] request_id const char* ID associated with the request being added.
  @returns int -1 if there is an error, 0 otherwise.
*/
static inline
int client_add_request(responses_t *x, const char* request_id) {
  if (x == NULL) return -1;
  x->request_id = (char**)realloc(x->request_id, (x->nreq + 1) * sizeof(char*));
  if (x->request_id == NULL) return -1;
  size_t request_len = strlen(request_id);
  x->request_id[x->nreq] = (char*)malloc(request_len + 1);
  if (x->request_id[x->nreq] == NULL) return -1;
  memcpy(x->request_id[x->nreq], request_id, request_len);
  x->request_id[x->nreq][request_len] = '\0';
  x->data = (char**)realloc(x->data, (x->nreq + 1) * sizeof(char*));
  if (x->data == NULL) return -1;
  x->data[x->nreq] = NULL;
  x->len = (size_t*)realloc(x->len, (x->nreq + 1) * sizeof(size_t));
  if (x->len == NULL) return -1;
  x->len[x->nreq] = 0;
  x->nreq++;
  return 0;
};

/*!
  @brief Add a response to the registry.
  @param[in] x responses_t* Structure containing a registry of requests and
  responses.
  @param[in] request_id const char* ID associated with the response being added.
  @param[in] data const char* Response message.
  @param[in] len size_t Size of the response message.
  @returns int -1 if there is an error, 0 otherwise.
*/
static inline
int client_add_response(responses_t *x, const char* request_id, const char* data,
		 const size_t len) {
  int idx = client_has_request(x, request_id);
  if (idx < 0) {
    ygglog_error("client_add_response: idx = %d", idx);
    return idx;
  }
  x->data[idx] = (char*)malloc(len + 1);
  if (x->data[idx] == NULL) {
    ygglog_error("client_add_response: failed to malloc data");
    return -1;
  }
  memcpy(x->data[idx], data, len);
  x->data[idx][len] = '\0';
  x->len[idx] = len;
  return 0;
};

/*!
  @brief Remove a request/response from the registry.
  @param[in] x responses_t* Structure containing a registry of requests and
  responses.
  @param[in] request_id const char* ID associated with the request/response
  that should be removed.
  @returns int -1 if there is an error, 0 otherwise.
*/
static inline
int client_remove_request(responses_t *x, const char* request_id) {
  if (x == NULL) return -1;
  int idx = client_has_request(x, request_id);
  if (idx < 0) return 0;
  int nrem = x->nreq - (idx + 1);
  free(x->request_id[idx]);
  if (x->data[idx] != NULL) free(x->data[idx]);
  if (nrem > 0) {
    memmove(x->request_id + idx, x->request_id + idx + 1, nrem * sizeof(char*));
    memmove(x->data + idx, x->data + idx + 1, nrem * sizeof(char*));
    memmove(x->len + idx, x->len + idx + 1, nrem * sizeof(size_t));
  }
  x->nreq--;
  return 0;
};

/*!
  @brief Remove and return a response from the registry after it has been received.
  @param[in] x responses_t* Structure containing a registry of requests and
  responses.
  @param[in] request_id const char* ID associated with the response that
  should be removed and returned.
  @param[in,out] data char** Pointer to memory where the response should be stored.
  @param[in] len const size_t Size of the existing buffer pointed to by data.
  @param[in] allow_realloc int If 1 and the response exceeds len, the buffer
  pointed to by data will be reallocated, if 0 and the response exceeds len,
  an error will be returned.
  @returns int -1 if there is an error, otherwise the size of the reponse
  message will be returned.
*/
static inline
int client_pop_response(responses_t *x, const char* request_id, char **data,
		 const size_t len, const int allow_realloc) {
  if (x == NULL) return -1;
  int idx = client_has_response(x, request_id);
  if (idx < 0) return -1;
  int ret = x->len[idx];
  if ((ret + 1) > len) {
    if (allow_realloc) {
      ygglog_debug("client_pop_response: reallocating buffer from %d to %d bytes.",
		   len, ret + 1);
      (*data) = (char*)realloc(*data, ret + 1);
      if (*data == NULL) {
	ygglog_error("client_pop_response: failed to realloc buffer.");
	return -1;
      }
    } else {
      ygglog_error("client_pop_response: buffer (%d bytes) is not large enough for message (%d bytes)",
		   len, ret + 1);
      return -((int)(ret));
    }
  }
  memcpy(*data, x->data[idx], ret);
  (*data)[ret] = '\0';
  if (client_remove_request(x, request_id) < 0) return -1;
  return ret;
};


/*!
  @brief Create a new channel.
  @param[in] comm comm_t * Comm structure initialized with new_comm_base.
  @returns int -1 if the address could not be created.
*/
static inline
int new_client_address(comm_t *comm) {
#ifdef _OPENMP
#pragma omp critical (client)
  {
#endif
  if (!(_client_rand_seeded)) {
    srand(ptr2seed(comm));
    _client_rand_seeded = 1;
  }
#ifdef _OPENMP
  }    
#endif
  comm->type = _default_comm;
  return new_default_address(comm);
};

/*!
  @brief Initialize a client communicator.
  @param[in] comm comm_t * Comm structure initialized with init_comm_base.
  @returns int -1 if the comm could not be initialized.
 */
static inline
int init_client_comm(comm_t *comm) {
  int ret = 0;
  ygglog_debug("init_client_comm: Creating a client comm");
#ifdef _OPENMP
#pragma omp critical (client)
  {
#endif
  if (!(_client_rand_seeded)) {
    srand(ptr2seed(comm));
    _client_rand_seeded = 1;
  }
#ifdef _OPENMP
  }    
#endif
  // Called to create temp comm for send/recv
  if ((strlen(comm->name) == 0) && (strlen(comm->address) > 0)) {
    comm->type = _default_comm;
    return init_default_comm(comm);
  }
  // Called to initialize/create client comm
  dtype_t *dtype_out = NULL;
  if (strlen(comm->direction) > 0) {
    dtype_out = create_dtype_format(comm->direction, 0, false);
    if (dtype_out == NULL) {
      ygglog_error("init_client_comm: Failed to create output datatype.");
      return -1;
    }
  }
  comm_t *handle;
  if (strlen(comm->name) == 0) {
    handle = new_comm_base(comm->address, "send", _default_comm, dtype_out);
    sprintf(handle->name, "client_request.%s", comm->address);
  } else {
    handle = init_comm_base(comm->name, "send", _default_comm, dtype_out);
  }
  handle->flags = handle->flags | COMM_FLAG_CLIENT;
  ret = init_default_comm(handle);
  strcpy(comm->address, handle->address);
  comm->handle = (void*)handle;
  // Keep track of response comms
  responses_t *resp = client_new_responses();
  if (resp == NULL) {
    ygglog_error("init_client_comm: Failed to malloc responses.");
    return -1;
  }
  comm->info = (void*)resp;
  strcpy(comm->direction, "send");
  comm->flags = comm->flags | COMM_ALWAYS_SEND_HEADER;
  return ret;
};

/*!
  @brief Perform deallocation for client communicator.
  @param[in] x comm_t* Pointer to communicator to deallocate.
  @returns int 1 if there is and error, 0 otherwise.
*/
static inline
int free_client_comm(comm_t *x) {
  if (x->info != NULL) {
    responses_t *resp = (responses_t*)(x->info);
    if (resp != NULL)
      client_free_responses(&resp);
    x->info = NULL;
  }
  if (x->handle != NULL) {
    comm_t *handle = (comm_t*)(x->handle);
    free_default_comm(handle);
    free_comm_base(handle);
    free(x->handle);
    x->handle = NULL;
  }
  return 0;
};

/*!
  @brief Get number of messages in the comm.
  @param[in] x comm_t* Communicator to check.
  @returns int Number of messages. -1 indicates an error.
 */
static inline
int client_comm_nmsg(const comm_t* x) {
  comm_t *handle = (comm_t*)(x->handle);
  int ret = default_comm_nmsg(handle);
  return ret;
};

/*!
  @brief Create response comm and add info to header.
  @param[in] x comm_t* structure that header will be sent to.
  @param[in] head comm_head_t Prexisting header structure.
  @returns comm_head_t Header structure that includes the additional
  information about the response comm.
*/
static inline
comm_head_t client_response_header(const comm_t* x, comm_head_t head) {
  // Initialize new comm
  responses_t *resp = (responses_t*)(x->info);
  if (resp->comm == NULL) {
    dtype_t * dtype_copy = copy_dtype(x->datatype);
    resp->comm = new_comm_base(NULL, "recv", _default_comm, dtype_copy);
    resp->comm->flags = resp->comm->flags | COMM_FLAG_CLIENT_RESPONSE;
    int ret = new_default_address(resp->comm);
    if (ret < 0) {
      ygglog_error("client_response_header(%s): could not create response comm", x->name);
      head.flags = head.flags & ~HEAD_FLAG_VALID;
      return head;
    }
    resp->comm->const_flags[0] = resp->comm->const_flags[0] | COMM_EOF_SENT | COMM_EOF_RECV;
    ygglog_debug("client_response_header(%s): Created response comm",
		 x->name);
  }
  // Add address & request ID to header
  strcpy(head.response_address, resp->comm->address);
  sprintf(head.request_id, "%d", rand());
  if (client_add_request(resp, head.request_id) < 0) {
    ygglog_error("client_response_header(%s): Failed to add request",
		 x->name);
    head.flags = head.flags & ~HEAD_FLAG_VALID;
    return head;
  }
  if (client_has_request(resp, head.request_id) < 0) {
    ygglog_error("client_response_header(%s): Failed to add request",
		 x->name);
    head.flags = head.flags & ~HEAD_FLAG_VALID;
    return head;
  }
  ygglog_debug("client_response_header(%s): response_address = %s, request_id = %s",
	       x->name, head.response_address, head.request_id);
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
int client_comm_send(const comm_t* x, const char *data, const size_t len) {
  int ret;
  ygglog_debug("client_comm_send(%s): %d bytes", x->name, len);
  if (x->handle == NULL) {
    ygglog_error("client_comm_send(%s): no request comm registered", x->name);
    return -1;
  }
  comm_t *req_comm = (comm_t*)(x->handle);
  ret = default_comm_send(req_comm, data, len);
  if (is_eof(data)) {
    req_comm->const_flags[0] = req_comm->const_flags[0] | COMM_EOF_SENT;
  }
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
int client_comm_recv(const comm_t* x, char **data, const size_t len, const int allow_realloc) {
  ygglog_debug("client_comm_recv(%s)", x->name);
  if (x->info == NULL) {
    ygglog_error("client_comm_recv(%s): no response struct set up", x->name);
    return -1;
  }
  responses_t *resp = (responses_t*)(x->info);
  if ((resp->comm == NULL) || (resp->nreq == 0)) {
    ygglog_error("client_comm_recv(%s): no response comm registered", x->name);
    return -1;
  }
  char* request_id = resp->request_id[0];
  int ret = 0;
  while (client_has_response(resp, request_id) < 0) {
    ret = default_comm_recv(resp->comm, data, len, allow_realloc);
    if (ret < 0) {
      ygglog_error("client_comm_recv(%s): default_comm_recv returned %d",
		   x->name, ret);
      return ret;
    }
    comm_head_t head = parse_comm_header(*data, len);
    if (!(head.flags & HEAD_FLAG_VALID)) {
      ygglog_error("client_comm_recv(%s): Invalid header.", x->name);
      return -1;
    }
    if (strcmp(head.request_id, request_id) == 0) {
      ygglog_debug("client_comm_recv(%s): default_comm_recv returned %d",
		   x->name, ret);
      if (client_remove_request(resp, request_id) < 0) {
	ygglog_error("client_comm_recv(%s): Failed to remove request %s",
		     x->name, request_id);
	return -1;
      }
      return ret;
    }
    if (client_add_response(resp, head.request_id, *data, ret) < 0) {
      ygglog_error("client_comm_recv(%s): Failed to add response %s",
		   x->name, head.request_id);
      return -1;
    }
  }
  ret = client_pop_response(resp, request_id, data, len, allow_realloc);
  // Close response comm and decrement count of response comms
  ygglog_debug("client_comm_recv(%s): client_pop_response returned %d",
	       x->name, ret);
  return ret;
};


#ifdef __cplusplus /* If this is a C++ compiler, end C linkage */
}
#endif

#endif /*YGGCLIENTCOMM_H_*/
