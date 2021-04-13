/*! @brief Flag for checking if this header has already been included. */
#ifndef YGGZMQCOMM_H_
#define YGGZMQCOMM_H_

#include <CommBase.h>
#include "../datatypes/datatypes.h"

#ifdef ZMQINSTALLED
#include <czmq.h>
#endif

#ifdef __cplusplus /* If this is a C++ compiler, use C linkage */
extern "C" {
#endif

#ifdef ZMQINSTALLED

static unsigned _zmq_rand_seeded = 0;
static unsigned _last_port_set = 0;
static int _last_port = 49152;
/* static double _wait_send_t = 0;  // 0.0001; */
static char _reply_msg[100] = "YGG_REPLY";
static char _purge_msg[100] = "YGG_PURGE";
static int _zmq_sleeptime = 10000;
#ifdef _OPENMP
#pragma omp threadprivate(_reply_msg, _purge_msg, _zmq_sleeptime)
#endif
static void *ygg_s_process_ctx = NULL;


typedef struct ygg_zsock_t {
  uint32_t tag;               //  Object tag for runtime detection
  void *handle;               //  The libzmq socket handle
  char *endpoint;             //  Last bound endpoint, if any
  char *cache;                //  Holds last zsock_brecv strings
  int type;                   //  Socket type
  size_t cache_size;          //  Current size of cache
  uint32_t routing_id;        //  Routing ID for server sockets
} ygg_zsock_t;


/*!
  @brief Initialize zeromq.
  @returns A zeromq context.
*/
#ifdef _OPENMP
static inline
void* ygg_zsys_init() {
#pragma omp critical (zmq)
  {
    if (!(ygg_s_process_ctx)) {
      if (get_thread_id() == 0) {
	ygglog_debug("ygg_zsys_init: Creating ZMQ context.");
	ygg_s_process_ctx = zsys_init();
	if (!(ygg_s_process_ctx)) {
	  ygglog_error("ygg_zsys_init: ZMQ context is NULL.");
	}
      } else {
	ygglog_error("ygg_zsys_init: Can only initialize the "
		     "zeromq context on the main thread. Call ygg_init "
		     "before the threaded portion of your model.");
      }
    }
  }
  return ygg_s_process_ctx;
};
#else
#define ygg_zsys_init zsys_init
#endif


/*!
  @brief Shutdown zeromq.
 */
#ifdef _OPENMP
static
void ygg_zsys_shutdown() {
#pragma omp critical (zmq)
  {
    ygg_s_process_ctx = NULL;
    zsys_shutdown();
  }    
};
#else
#define ygg_zsys_shutdown zsys_shutdown
#endif


/*!
  @brief Destroy a socket in thread safe way.
  @param[in] self_p zsock_t** Pointer to a CZMQ socket wrapper struct.
*/
#ifdef _OPENMP
static inline
void ygg_zsock_destroy(zsock_t **self_p) {
  // Recreation of czmq zsock_destroy that is OMP aware
  /* assert(self_p); */
  if (*self_p) {
    ygg_zsock_t *self = (ygg_zsock_t*)(*self_p);
    /* assert (zsock_is (*self_p)); */
    self->tag = 0xDeadBeef;
    zmq_close (self->handle);
    freen (self->endpoint);
    freen (self->cache);
    freen (self);
    *self_p = NULL;
  }
};
#else
#define ygg_zsock_destroy zsock_destroy
#endif


/*!
  @brief Get a new socket, using the exising context.
  @param[in] type int Socket type.
  @returns zsock_t* CZMQ socket wrapper struct.
*/
#ifdef _OPENMP
static inline
zsock_t *
ygg_zsock_new(int type) {
  // Recreation of czmq zsock_new that is OMP aware
  ygg_zsock_t *self = (ygg_zsock_t *) zmalloc (sizeof (ygg_zsock_t));
  if (!(self)) {
    ygglog_error("ygg_zsock_new: Error allocating for new socket.");
    return NULL;
  }
  self->tag = 0xcafe0004;
  self->type = type;
  void* ctx = ygg_zsys_init();
  if (!(ctx)) {
    ygglog_error("ygg_zsock_new: Context is NULL.");
    freen(self);
    return NULL;
  }
#pragma omp critical (zmq)
  {
    self->handle = zmq_socket (ctx, type);
  }
  if (!(self->handle)) {
    ygglog_error("ygg_zsock_new: Error creating new socket.");
    freen(self);
    return NULL;
  }
  return (zsock_t*)(self);
};
#else
#define ygg_zsock_new zsock_new
#endif

static inline
zsock_t* create_zsock(int type) {
  zsock_t* out = ygg_zsock_new(type);
  zsock_set_linger(out, 0);
  zsock_set_immediate(out, 1);
  return out;
};
  

/*! 
  @brief Struct to store info for reply.
*/
typedef struct zmq_reply_t {
  int nsockets;
  zsock_t **sockets;
  char **addresses;
  int n_msg;
  int n_rep;
} zmq_reply_t;


// Forward declarations
static inline
int zmq_comm_nmsg(const comm_t *x);
static inline
int zmq_comm_recv(const comm_t *x, char **data, const size_t len,
		  const int allow_realloc);


/*!
  @brief Free a reply structure.
  @param[in] x zmq_reply_t * Structure to free.
  @returns int 0 if successfull, -1 otherwise.
 */
static inline
int free_zmq_reply(zmq_reply_t *x) {
  int i = 0;
  if (x != NULL) {
    if (x->sockets != NULL) {
      for (i = 0; i < x->nsockets; i++) {
	if (x->sockets[i] != NULL) {
	  ygg_zsock_destroy(&(x->sockets[i]));
	  x->sockets[i] = NULL;
	}
      }
      free(x->sockets);
    }
    if (x->addresses != NULL) {
      for (i = 0; i < x->nsockets; i++) {
	if (x->addresses[i] != NULL) {
	  free(x->addresses[i]);
	  x->addresses[i] = NULL;
	}
      }
      free(x->addresses);
    }
    x->nsockets = 0;
  }
  return 0;
}

/*!
  @brief Add empty reply structure information to comm.
  @param[in] comm comm_t * Comm to initialize reply for.
  @returns int 0 if successfull, -1 otherwise.
 */
static inline
int init_zmq_reply(comm_t *comm) {
  zmq_reply_t *zrep = (zmq_reply_t*)malloc(sizeof(zmq_reply_t));
  if (zrep == NULL) {
    ygglog_error("init_zmq_reply(%s): Failed to malloc reply.", comm->name);
    return -1;
  }
  zrep->nsockets = 0;
  zrep->sockets = NULL;
  zrep->addresses = NULL;
  zrep->n_msg = 0;
  zrep->n_rep = 0;
  comm->reply = (void*)zrep;
  return 0;
};

/*!
  @brief Locate matching reply socket.
  @param[in] comm comm_t* Comm that should be checked for matching reply socket.
  @param[in] address char* Address that should be matched against.
  @returns int Index of matched socket, -1 if no match, -2 if error.
 */
static inline
int find_reply_socket(const comm_t *comm, const char *address) {
  int ret = -1;
  // Get reply
  zmq_reply_t *zrep = (zmq_reply_t*)(comm->reply);
  if (zrep == NULL) {
    ygglog_error("find_reply_socket(%s): Reply structure not initialized.", comm->name);
    return -2;
  }
  int i = 0;
  for (i = 0; i < zrep->nsockets; i++) {
    if (strcmp(zrep->addresses[i], address) == 0) {
      ret = i;
      break;
    }
  }
  return ret;
};

/*!
  @brief Request confirmation from receiving socket.
  @param[in] comm comm_t* Comm structure to do reply for.
  @returns int 0 if successful, -2 on EOF, -1 otherwise.
 */
static inline
int do_reply_send(const comm_t *comm) {
  // Get reply
  zmq_reply_t *zrep = (zmq_reply_t*)(comm->reply);
  if (zrep == NULL) {
    ygglog_error("do_reply_send(%s): Reply structure not initialized.", comm->name);
    return -1;
  }
  zrep->n_msg++;
  zsock_t *s = (zsock_t*)(zrep->sockets[0]);
  if (s == NULL) {
    ygglog_error("do_reply_send(%s): Socket is NULL.", comm->name);
    return -1;
  }
  // Poll
  ygglog_debug("do_reply_send(%s): address=%s, begin", comm->name,
  	       zrep->addresses[0]);
#if defined(__cplusplus) && defined(_WIN32)
  // TODO: There seems to be an error in the poller when using it in C++
#else
  zpoller_t *poller = zpoller_new(s, NULL);
  if (!(poller)) {
    ygglog_error("do_reply_send(%s): Could not create poller", comm->name);
    return -1;
  }
  assert(poller);
  ygglog_debug("do_reply_send(%s): waiting on poller...", comm->name);
  void *p = zpoller_wait(poller, -1);
  //void *p = zpoller_wait(poller, 1000);
  ygglog_debug("do_reply_send(%s): poller returned", comm->name); 
  if (p == NULL) {
    if (zpoller_terminated(poller)) {
      ygglog_error("do_reply_send(%s): Poller interrupted", comm->name);
    } else if (zpoller_expired(poller)) {
      ygglog_error("do_reply_send(%s): Poller expired", comm->name);
    } else {
      ygglog_error("do_reply_send(%s): Poller failed", comm->name);
    }
    zpoller_destroy(&poller);
    return -1;
  }
  zpoller_destroy(&poller);
#endif
  // Receive
  zframe_t *msg = zframe_recv(s);
  if (msg == NULL) {
    ygglog_error("do_reply_send(%s): did not receive", comm->name);
    return -1;
  }
  char *msg_data = (char*)zframe_data(msg);
  // Check for EOF
  int is_purge = 0;
  if (strcmp(msg_data, YGG_MSG_EOF) == 0) {
    ygglog_debug("do_reply_send(%s): EOF received", comm->name);
    zrep->n_msg = 0;
    zrep->n_rep = 0;
    return -2;
  } else if (strcmp(msg_data, _purge_msg) == 0) {
    is_purge = 1;
  }
  // Send
  // zsock_set_linger(s, _zmq_sleeptime);
  int ret = zframe_send(&msg, s, 0);
  // Check for purge or EOF
  if (ret < 0) {
    ygglog_error("do_reply_send(%s): Error sending reply frame.", comm->name);
    zframe_destroy(&msg);
  } else {
    if (is_purge == 1) {
      ygglog_debug("do_reply_send(%s): PURGE received", comm->name);
      zrep->n_msg = 0;
      zrep->n_rep = 0;
      ret = do_reply_send(comm);
    } else {
      zrep->n_rep++;
    }
  }
  ygglog_debug("do_reply_send(%s): address=%s, end", comm->name,
	       zrep->addresses[0]);
#if defined(__cplusplus) && defined(_WIN32)
  // TODO: There seems to be an error in the poller when using it in C++
#else
  if (ret >= 0) {
    poller = zpoller_new(s, NULL);
    if (!(poller)) {
      ygglog_error("do_reply_send(%s): Could not create poller", comm->name);
      return -1;
    }
    assert(poller);
    ygglog_debug("do_reply_send(%s): waiting on poller...", comm->name);
    p = zpoller_wait(poller, 10);
    ygglog_debug("do_reply_send(%s): poller returned", comm->name); 
    zpoller_destroy(&poller);
  }
#endif
  return ret;
};

/*!
  @brief Send confirmation to sending socket.
  @param[in] comm comm_t* Comm structure to do reply for.
  @param[in] isock int Index of socket that reply should be done for.
  @param[in] msg char* Mesage to send/recv.
  @returns int 0 if successfule, -1 otherwise.
 */
static inline
int do_reply_recv(const comm_t *comm, const int isock, const char *msg) {
  // Get reply
  zmq_reply_t *zrep = (zmq_reply_t*)(comm->reply);
  if (zrep == NULL) {
    ygglog_error("do_reply_recv(%s): Reply structure not initialized.", comm->name);
    return -1;
  }
  zsock_t *s = (zsock_t*)(zrep->sockets[isock]);
  if (s == NULL) {
    ygglog_error("do_reply_recv(%s): Socket is NULL.", comm->name);
    return -1;
  }
  ygglog_debug("do_reply_recv(%s): address=%s, begin", comm->name,
	       zrep->addresses[isock]);
  zframe_t *msg_send = zframe_new(msg, strlen(msg));
  if (msg_send == NULL) {
    ygglog_error("do_reply_recv(%s): Error creating frame.", comm->name);
    return -1;
  }
  // Send
  int ret = zframe_send(&msg_send, s, 0);
  if (ret < 0) {
    ygglog_error("do_reply_recv(%s): Error sending confirmation.", comm->name);
    zframe_destroy(&msg_send);
    return -1;
  }
  if (strcmp(msg, YGG_MSG_EOF) == 0) {
    ygglog_info("do_reply_recv(%s): EOF confirmation.", comm->name);
    zrep->n_msg = 0;
    zrep->n_rep = 0;
    zsock_set_linger(s, _zmq_sleeptime);
    return -2;
  }
  // Poll to prevent block
  ygglog_debug("do_reply_recv(%s): address=%s, polling for reply", comm->name,
	       zrep->addresses[isock]);
#if defined(__cplusplus) && defined(_WIN32)
  // TODO: There seems to be an error in the poller when using it in C++
#else
  zpoller_t *poller = zpoller_new(s, NULL);
  if (!(poller)) {
    ygglog_error("do_reply_send(%s): Could not create poller", comm->name);
    return -1;
  }
  assert(poller);
  ygglog_debug("do_reply_recv(%s): waiting on poller...", comm->name);
  void *p = zpoller_wait(poller, 1000);
  ygglog_debug("do_reply_recv(%s): poller returned", comm->name); 
  if (p == NULL) {
    if (zpoller_terminated(poller)) {
      ygglog_error("do_reply_recv(%s): Poller interrupted", comm->name);
    } else if (zpoller_expired(poller)) {
      ygglog_error("do_reply_recv(%s): Poller expired", comm->name);
    } else {
      ygglog_error("do_reply_recv(%s): Poller failed", comm->name);
    }
    zpoller_destroy(&poller);
    return -1;
  }
  zpoller_destroy(&poller);
#endif
  // Receive
  zframe_t *msg_recv = zframe_recv(s);
  if (msg_recv == NULL) {
    ygglog_error("do_reply_recv(%s): did not receive", comm->name);
    return -1;
  }
  zframe_destroy(&msg_recv);
  zrep->n_rep++;
  ygglog_debug("do_reply_recv(%s): address=%s, end", comm->name,
	       zrep->addresses[isock]);
  return 0;
};

/*!
  @brief Add reply socket information to a send comm.
  @param[in] comm comm_t* Comm that confirmation is for.
  @returns char* Reply socket address.
*/
static inline
char *set_reply_send(const comm_t *comm) {
  char *out = NULL;
  // Get reply
  zmq_reply_t *zrep = (zmq_reply_t*)(comm->reply);
  if (zrep == NULL) {
    ygglog_error("set_reply_send(%s): Reply structure not initialized.", comm->name);
    return out;
  }
  // Create socket
  if (zrep->nsockets == 0) {
    zrep->sockets = (zsock_t**)malloc(sizeof(zsock_t*));
    if (zrep->sockets == NULL) {
      ygglog_error("set_reply_send(%s): Error mallocing sockets.", comm->name);
      return out;
    }
    zrep->nsockets = 1;
    zrep->sockets[0] = create_zsock(ZMQ_REP);
    if (zrep->sockets[0] == NULL) {
      ygglog_error("set_reply_send(%s): Could not initialize empty socket.",
		   comm->name);
      return out;
    }
    char protocol[50] = "tcp";
    char host[50] = "localhost";
    if (strcmp(host, "localhost") == 0)
      strncpy(host, "127.0.0.1", 50);
    char address[100];
    int port = -1;
#ifdef _OPENMP
#pragma omp critical (zmqport)
  {
#endif
    if (_last_port_set == 0) {
      ygglog_debug("model_index = %s", getenv("YGG_MODEL_INDEX"));
      _last_port = 49152 + 1000 * atoi(getenv("YGG_MODEL_INDEX"));
      _last_port_set = 1;
      ygglog_debug("_last_port = %d", _last_port);
    }
    sprintf(address, "%s://%s:*[%d-]", protocol, host, _last_port + 1);
    port = zsock_bind(zrep->sockets[0], "%s", address);
    if (port != -1)
      _last_port = port;
#ifdef _OPENMP
  }
#endif
    if (port == -1) {
      ygglog_error("set_reply_send(%s): Could not bind socket to address = %s",
		   comm->name, address);
      return out;
    }
    sprintf(address, "%s://%s:%d", protocol, host, port);
    zrep->addresses = (char**)malloc(sizeof(char*));
    zrep->addresses[0] = (char*)malloc((strlen(address) + 1)*sizeof(char));
    strncpy(zrep->addresses[0], address, strlen(address) + 1);
    ygglog_debug("set_reply_send(%s): New reply socket: %s", comm->name, address);
  }
  out = zrep->addresses[0];
  return out;
};

/*!
  @brief Add reply socket information to a recv comm.
  @param[in] comm comm_t* Comm that confirmation is for.
  @returns int Index of the reply socket.
*/
static inline
int set_reply_recv(const comm_t *comm, const char* address) {
  int out = -1;
  // Get reply
  zmq_reply_t *zrep = (zmq_reply_t*)(comm->reply);
  if (zrep == NULL) {
    ygglog_error("set_reply_recv(%s): Reply structure not initialized.", comm->name);
    return out;
  }
  // Match address and create if it dosn't exist
  int isock = find_reply_socket(comm, address);
  if (isock < 0) {
    if (isock == -2) {
      ygglog_error("set_reply_recv(%s): Error locating socket.", comm->name);
      return out;
    }
    // Realloc arrays
    zrep->sockets = (zsock_t**)realloc(zrep->sockets,
				       sizeof(zsock_t*)*(zrep->nsockets + 1));
    if (zrep->sockets == NULL) {
      ygglog_error("set_reply_recv(%s): Error reallocing sockets.", comm->name);
      return out;
    }
    zrep->addresses = (char**)realloc(zrep->addresses,
				      sizeof(char*)*(zrep->nsockets + 1));
    if (zrep->addresses == NULL) {
      ygglog_error("set_reply_recv(%s): Error reallocing addresses.", comm->name);
      return out;
    }
    // Create new socket
    isock = zrep->nsockets;
    zrep->nsockets++;
    zrep->sockets[isock] = create_zsock(ZMQ_REQ);
    if (zrep->sockets[isock] == NULL) {
      ygglog_error("set_reply_recv(%s): Could not initialize empty socket.",
		   comm->name);
      return out;
    }
    zrep->addresses[isock] = (char*)malloc(sizeof(char)*(strlen(address) + 1));
    if (zrep->addresses[isock] == NULL) {
      ygglog_error("set_reply_recv(%s): Could not realloc new address.",
		   comm->name);
      return out;
    }
    strncpy(zrep->addresses[isock], address, strlen(address) + 1);
    int ret = zsock_connect(zrep->sockets[isock], "%s", address);
    if (ret < 0) {
      ygglog_error("set_reply_recv(%s): Could not connect to socket.",
		   comm->name);
      return out;
    }
    ygglog_debug("set_reply_recv(%s): New recv socket: %s", comm->name, address);
  }
  return isock;
};

/*!
  @brief Add information about reply socket to outgoing message.
  @param[in] comm comm_t* Comm that confirmation is for.
  @param[in] data char* Message that reply info should be added to.
  @param[in] len int Length of the outgoing message.
  @returns char* Message with reply information added.
 */
static inline
char* check_reply_send(const comm_t *comm, const char *data, const int len,
		       int *new_len) {
  // Prevent C4100 warning on windows by referencing param
#ifdef _WIN32
  UNUSED(comm);
#endif
  char *out = (char*)malloc(len + 1);
  memcpy(out, data, len + 1);
  new_len[0] = len;
  return out;
};


/*!
  @brief Get reply information from message.
  @param[in] comm comm_* Comm structure for incoming message.
  @param[in, out] data char* Received message containing reply info that will be
  removed on return.
  @param[in] len size_t Length of received message.
  @returns int Length of message without the reply info. -1 if there is an error.
 */
static inline
int check_reply_recv(const comm_t *comm, char *data, const size_t len) {
  int new_len = (int)len;
  int ret = 0;
  // Get reply
  zmq_reply_t *zrep = (zmq_reply_t*)(comm->reply);
  if (zrep == NULL) {
    ygglog_error("check_reply_recv(%s): Reply structure not initialized.", comm->name);
    return -1;
  }
  zrep->n_msg++;
  // Extract address
  comm_head_t head = parse_comm_header(data, len);
  if (!(head.flags & HEAD_FLAG_VALID)) {
    ygglog_error("check_reply_recv(%s): Invalid header.", comm->name);
    return -1;
  }
  char address[100];
  size_t address_len;
  if ((comm->flags & COMM_FLAG_WORKER) && (zrep->nsockets == 1)) {
    address_len = strlen(zrep->addresses[0]);
    memcpy(address, zrep->addresses[0], address_len);
  } else if (strlen(head.zmq_reply) > 0) {
    address_len = strlen(head.zmq_reply);
    memcpy(address, head.zmq_reply, address_len);
  } else {
    ygglog_error("check_reply_recv(%s): Error parsing reply header in '%s'",
		 comm->name, data);
    destroy_header(&head);
    return -1;
  }
  destroy_header(&head);
  address[address_len] = '\0';
  // Match address and create if it dosn't exist
  int isock = set_reply_recv(comm, address);
  if (isock < 0) {
    ygglog_error("check_reply_recv(%s): Error setting reply socket.");
    return -1;
  }
  // Confirm message receipt
  ret = do_reply_recv(comm, isock, _reply_msg);
  if (ret < 0) {
    ygglog_error("check_reply_recv(%s): Error during reply.", comm->name);
    return -1;
  }
  return new_len;
};

/*!
  @brief Create a new socket.
  @param[in] comm comm_t * Comm structure initialized with new_comm_base.
  @returns int -1 if the address could not be created.
*/
static inline
int new_zmq_address(comm_t *comm) {
  // TODO: Get protocol/host from input
  char protocol[50] = "tcp";
  char host[50] = "localhost";
  char address[100];
  comm->msgBufSize = 100;
  if (strcmp(host, "localhost") == 0)
    strncpy(host, "127.0.0.1", 50);
  if ((strcmp(protocol, "inproc") == 0) ||
      (strcmp(protocol, "ipc") == 0)) {
    // TODO: small chance of reusing same number
    int key = 0;
#ifdef _OPENMP
#pragma omp critical (zmqport)
  {
#endif
    if (!(_zmq_rand_seeded)) {
      srand(ptr2seed(comm));
      _zmq_rand_seeded = 1;
    }
#ifdef _OPENMP
  }
#endif
    while (key == 0) key = rand();
    if (strlen(comm->name) == 0)
      sprintf(comm->name, "tempnewZMQ-%d", key);
    sprintf(address, "%s://%s", protocol, comm->name);
  } else {
#ifdef _OPENMP
#pragma omp critical (zmqport)
  {
#endif
     if (_last_port_set == 0) {
      ygglog_debug("model_index = %s", getenv("YGG_MODEL_INDEX"));
      _last_port = 49152 + 1000 * atoi(getenv("YGG_MODEL_INDEX"));
      _last_port_set = 1;
      ygglog_debug("_last_port = %d", _last_port);
    }
   sprintf(address, "%s://%s:*[%d-]", protocol, host, _last_port + 1);
#ifdef _OPENMP
  }
#endif
    /* strcat(address, ":!"); // For random port */
  }
  // Bind
  zsock_t *s = NULL;
  if (comm->flags & COMM_FLAG_CLIENT_RESPONSE) {
    s = create_zsock(ZMQ_ROUTER);
  } else if (comm->flags & COMM_ALLOW_MULTIPLE_COMMS) {
    s = create_zsock(ZMQ_DEALER);
  } else {
    s = create_zsock(ZMQ_PAIR);
  }
  if (s == NULL) {
    ygglog_error("new_zmq_address: Could not initialize empty socket.");
    return -1;
  }
  int port = zsock_bind(s, "%s", address);
  if (port == -1) {
    ygglog_error("new_zmq_address: Could not bind socket to address = %s",
		 address);
    return -1;
  }
  // Add port to address
#ifdef _OPENMP
#pragma omp critical (zmqport)
  {
#endif
  if ((strcmp(protocol, "inproc") != 0) &&
      (strcmp(protocol, "ipc") != 0)) {
    _last_port = port;
    sprintf(address, "%s://%s:%d", protocol, host, port);
  }
#ifdef _OPENMP
  }
#endif
  strncpy(comm->address, address, COMM_ADDRESS_SIZE);
  ygglog_debug("new_zmq_address: Bound socket to %s", comm->address);
  if (strlen(comm->name) == 0)
    sprintf(comm->name, "tempnewZMQ-%d", port);
  comm->handle = (void*)s;
  // Init reply
  int ret = init_zmq_reply(comm);
  return ret;
};

/*!
  @brief Initialize a ZeroMQ communicator.
  @param[in] comm comm_t * Comm structure initialized with init_comm_base.
  @returns int -1 if the comm could not be initialized.
 */
static inline
int init_zmq_comm(comm_t *comm) {
  int ret = -1;
  if (!(comm->flags & COMM_FLAG_VALID))
    return ret;
  comm->msgBufSize = 100;
  zsock_t *s;
  if (comm->flags & (COMM_FLAG_SERVER | COMM_ALLOW_MULTIPLE_COMMS)) {
    s = create_zsock(ZMQ_DEALER);
  } else {
    s = create_zsock(ZMQ_PAIR);
  }
  if (s == NULL) {
    ygglog_error("init_zmq_address: Could not initialize empty socket.");
    return -1;
  }
  ret = zsock_connect(s, "%s", comm->address);
  if (ret == -1) {
    ygglog_error("init_zmq_address: Could not connect socket to address = %s",
  		 comm->address);
    ygg_zsock_destroy(&s);
    return ret;
  }
  ygglog_debug("init_zmq_address: Connected socket to %s", comm->address);
  if (strlen(comm->name) == 0)
    sprintf(comm->name, "tempinitZMQ-%s", comm->address);
  // Asign to void pointer
  comm->handle = (void*)s;
  ret = init_zmq_reply(comm);
  comm->flags = comm->flags | COMM_ALWAYS_SEND_HEADER;
  return ret;
};

/*!
  @brief Perform deallocation for ZMQ communicator.
  @param[in] x comm_t Pointer to communicator to deallocate.
  @returns int 1 if there is and error, 0 otherwise.
*/
static inline
int free_zmq_comm(comm_t *x) {
  int ret = 0;
  if (x == NULL)
    return ret;
  // Drain input
  if ((is_recv(x->direction)) && (x->flags & COMM_FLAG_VALID)) {
    if (_ygg_error_flag == 0) {
      size_t data_len = 100;
      char *data = (char*)malloc(data_len);
      while (zmq_comm_nmsg(x) > 0) {
        ret = zmq_comm_recv(x, &data, data_len, 1);
        if (ret < 0) {
          if (ret == -2) {
	    x->const_flags[0] = x->const_flags[0] | COMM_EOF_RECV;
            break;
          }
        }
      }
      free(data);
    }
  }
  // Free reply
  if (x->reply != NULL) {
    zmq_reply_t *zrep = (zmq_reply_t*)(x->reply);
    // Free reply
    ret = free_zmq_reply(zrep);
    free(x->reply);
    x->reply = NULL;
  }
  if (x->handle != NULL) {
    zsock_t *s = (zsock_t*)(x->handle);
    if (s != NULL) {
      ygglog_debug("Destroying socket: %s", x->address);
      ygg_zsock_destroy(&s);
    }
    x->handle = NULL;
  }
  ygglog_debug("free_zmq_comm: finished");
  return ret;
};

/*!
  @brief Get number of messages in the comm.
  @param[in] comm_t Communicator to check.
  @returns int Number of messages. -1 indicates an error.
 */
static inline
int zmq_comm_nmsg(const comm_t *x) {
  int out = 0;
  if (is_recv(x->direction)) {
    if (x->handle != NULL) {
      zsock_t *s = (zsock_t*)(x->handle);
      zpoller_t *poller = zpoller_new(s, NULL);
      if (poller == NULL) {
	ygglog_error("zmq_comm_nmsg: Could not create poller");
	return -1;
      }
      void *p = zpoller_wait(poller, 1);
      if (p == NULL) {
	if (zpoller_terminated(poller)) {
	  ygglog_error("zmq_comm_nmsg: Poller interrupted");
	  out = -1;
	} else {
	  out = 0;
	}
      } else {
	out = 1;
      }
      zpoller_destroy(&poller);
    }
  } else {
    /* if (x->last_send[0] != 0) { */
    /*   time_t now; */
    /*   time(&now); */
    /*   double elapsed = difftime(now, x->last_send[0]); */
    /*   if (elapsed > _wait_send_t) */
    /* 	out = 0; */
    /*   else */
    /* 	out = 1; */
    /* } */
    zmq_reply_t *zrep = (zmq_reply_t*)(x->reply);
    if (zrep != NULL) {
      ygglog_debug("zmq_comm_nmsg(%s): nmsg = %d, nrep = %d",
		   x->name, zrep->n_msg, zrep->n_rep);
      out = zrep->n_msg - zrep->n_rep;
    }
  }
  return out;
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
static inline
int zmq_comm_send(const comm_t *x, const char *data, const size_t len) {
  ygglog_debug("zmq_comm_send(%s): %d bytes", x->name, len);
  if (comm_base_send(x, data, len) == -1)
    return -1;
  zsock_t *s = (zsock_t*)(x->handle);
  if (s == NULL) {
    ygglog_error("zmq_comm_send(%s): socket handle is NULL", x->name);
    return -1;
  }
  int new_len = 0;
  char *new_data = check_reply_send(x, data, (int)len, &new_len);
  if (new_data == NULL) {
    ygglog_error("zmq_comm_send(%s): Adding reply address failed.", x->name);
    return -1;
  }
  zframe_t *f = zframe_new(new_data, new_len);
  int ret = -1;
  if (f == NULL) {
    ygglog_error("zmq_comm_send(%s): frame handle is NULL", x->name);
  } else {
    ret = zframe_send(&f, s, 0);
    if (ret < 0) {
      ygglog_error("zmq_comm_send(%s): Error in zframe_send", x->name);
      zframe_destroy(&f);
    }
  }
  // Get reply
  if (ret >= 0) {
    ret = do_reply_send(x);
    if (ret < 0) {
      if (ret == -2) {
	ygglog_error("zmq_comm_send(%s): EOF received", x->name);
      } else {
	ygglog_error("zmq_comm_send(%s): Error in do_reply_send", x->name);
      }
    }
  }
  ygglog_debug("zmq_comm_send(%s): returning %d", x->name, ret);
  free(new_data);
  return ret;
};


static inline
zframe_t * zmq_comm_recv_zframe(const comm_t* x) {
  ygglog_debug("zmq_comm_recv_zframe(%s)", x->name);
  zsock_t *s = (zsock_t*)(x->handle);
  if (s == NULL) {
    ygglog_error("zmq_comm_recv_zframe(%s): socket handle is NULL", x->name);
    return NULL;
  }
  clock_t start = clock();
  while ((((double)(clock() - start))/CLOCKS_PER_SEC) < 180) {
    int nmsg = zmq_comm_nmsg(x);
    if (nmsg < 0) return NULL;
    else if (nmsg > 0) break;
    else {
      ygglog_debug("zmq_comm_recv_zframe(%s): no messages, sleep %d", x->name,
		   YGG_SLEEP_TIME);
      usleep(YGG_SLEEP_TIME);
    }
  }
  ygglog_debug("zmq_comm_recv_zframe(%s): receiving", x->name);
  zframe_t *out = NULL;
  if (x->flags & COMM_FLAG_CLIENT_RESPONSE) {
    out = zframe_recv(s);
    if (out == NULL) {
      ygglog_debug("zmq_comm_recv_zframe(%s): did not receive identity", x->name);
      return NULL;
    }
    zframe_destroy(&out);
    out = NULL;
  }
  out = zframe_recv(s);
  if (out == NULL) {
    ygglog_debug("zmq_comm_recv_zframe(%s): did not receive", x->name);
    return NULL;
  }
  return out;
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
  @returns int -1 if message could not be received. Length of the received
  message if message was received.
 */
static inline
int zmq_comm_recv(const comm_t* x, char **data, const size_t len,
		  const int allow_realloc) {
  int ret = -1;
  ygglog_debug("zmq_comm_recv(%s)", x->name);
  zsock_t *s = (zsock_t*)(x->handle);
  if (s == NULL) {
    ygglog_error("zmq_comm_recv(%s): socket handle is NULL", x->name);
    return ret;
  }
  zframe_t *out = zmq_comm_recv_zframe(x);
  if (out == NULL) {
    ygglog_debug("zmq_comm_recv(%s): did not receive", x->name);
    return ret;
  }
  // Check for server signon and respond
  while (strncmp((char*)zframe_data(out), "ZMQ_SERVER_SIGNING_ON::", 23) == 0) {
    ygglog_debug("zmq_comm_recv(%s): Received sign-on", x->name);
    char* client_address = (char*)zframe_data(out) + 23;
    // create a DEALER socket and connect to address
    zsock_t *client_socket = create_zsock(ZMQ_DEALER);
    if (client_socket == NULL) {
      ygglog_error("zmq_comm_recv(%s): Could not initalize the client side of the proxy socket to confirm signon", x->name);
      zframe_destroy(&out);
      return ret;
    }
    zsock_set_sndtimeo(client_socket, _zmq_sleeptime);
    zsock_set_immediate(client_socket, 1);
    zsock_set_linger(client_socket, _zmq_sleeptime);
    if (zsock_connect(client_socket, "%s", client_address) < 0) {
      ygglog_error("zmq_comm_recv(%s): Error when connecting to the client proxy socket to respond to signon: %s", x->name, client_address);
      zframe_destroy(&out);
      ygg_zsock_destroy(&client_socket);
      return ret;
    }
    zframe_t *response = zframe_new(zframe_data(out), zframe_size(out));
    if (response == NULL) {
      ygglog_error("zmq_comm_recv(%s): Error creating response message frame.", x->name);
      zframe_destroy(&out);
      zframe_destroy(&response);
      ygg_zsock_destroy(&client_socket);
      return ret;
    }
    if (zframe_send(&response, client_socket, 0) < 0) {
      ygglog_error("zmq_comm_recv(%s): Error sending response message.", x->name);
      zframe_destroy(&out);
      zframe_destroy(&response);
      ygg_zsock_destroy(&client_socket);
      return ret;
    }
    zframe_destroy(&response);
    ygg_zsock_destroy(&client_socket);
    zframe_destroy(&out);
    out = zmq_comm_recv_zframe(x);
    if (out == NULL) {
      ygglog_debug("zmq_comm_recv(%s): did not receive", x->name);
      return ret;
    }
  }
  // Realloc and copy data
  size_t len_recv = zframe_size(out) + 1;
  // size_t len_recv = (size_t)ret + 1;
  if (len_recv > len) {
    if (allow_realloc) {
      ygglog_debug("zmq_comm_recv(%s): reallocating buffer from %d to %d bytes.",
		   x->name, len, len_recv);
      (*data) = (char*)realloc(*data, len_recv);
      if (*data == NULL) {
	ygglog_error("zmq_comm_recv(%s): failed to realloc buffer.", x->name);
	zframe_destroy(&out);
	return -1;
      }
    } else {
      ygglog_error("zmq_comm_recv(%s): buffer (%d bytes) is not large enough for message (%d bytes)",
		   x->name, len, len_recv);
      zframe_destroy(&out);
      return -((int)(len_recv - 1));
    }
  }
  memcpy(*data, zframe_data(out), len_recv - 1);
  zframe_destroy(&out);
  (*data)[len_recv-1] = '\0';
  ret = (int)len_recv - 1;
  /*
  if (strlen(*data) != ret) {
    ygglog_error("zmq_comm_recv(%s): Size of string (%d) doesn't match expected (%d)",
		 x->name, strlen(*data), ret);
    return -1;
  }
  */
  // Check reply
  ret = check_reply_recv(x, *data, ret);
  if (ret < 0) {
    ygglog_error("zmq_comm_recv(%s): failed to check for reply socket.", x->name);
    return ret;
  }
  ygglog_debug("zmq_comm_recv(%s): returning %d", x->name, ret);
  return ret;
};


// Definitions in the case where ZMQ libraries not installed
#else /*ZMQINSTALLED*/

/*!
  @brief Print error message about ZMQ library not being installed.
 */
static inline
void ygg_zsys_shutdown() {
  ygglog_error("Compiler flag 'ZMQINSTALLED' not defined so ZMQ bindings are disabled.");
};

/*!
  @brief Print error message about ZMQ library not being installed.
 */
static inline
void* ygg_zsys_init() {
  ygglog_error("Compiler flag 'ZMQINSTALLED' not defined so ZMQ bindings are disabled.");
  return NULL;
};

/*!
  @brief Print error message about ZMQ library not being installed.
 */
static inline
void zmq_install_error() {
  ygglog_error("Compiler flag 'ZMQINSTALLED' not defined so ZMQ bindings are disabled.");
};

/*!
  @brief Perform deallocation for ZMQ communicator.
  @param[in] x comm_t Pointer to communicator to deallocate.
  @returns int 1 if there is and error, 0 otherwise.
*/
static inline
int free_zmq_comm(comm_t *x) {
  zmq_install_error();
  return 1;
};

/*!
  @brief Create a new socket.
  @param[in] comm comm_t * Comm structure initialized with new_comm_base.
  @returns int -1 if the address could not be created.
*/
static inline
int new_zmq_address(comm_t *comm) {
  zmq_install_error();
  return -1;
};

/*!
  @brief Initialize a ZeroMQ communicator.
  @param[in] comm comm_t * Comm structure initialized with init_comm_base.
  @returns int -1 if the comm could not be initialized.
 */
static inline
int init_zmq_comm(comm_t *comm) {
  zmq_install_error();
  return -1;
};

/*!
  @brief Get number of messages in the comm.
  @param[in] x comm_t* Communicator to check.
  @returns int Number of messages. -1 indicates an error.
 */
static inline
int zmq_comm_nmsg(const comm_t* x) {
  zmq_install_error();
  return -1;
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
static inline
int zmq_comm_send(const comm_t* x, const char *data, const size_t len) {
  zmq_install_error();
  return -1;
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
  @returns int -1 if message could not be received. Length of the received
  message if message was received.
 */
static inline
int zmq_comm_recv(const comm_t* x, char **data, const size_t len,
		  const int allow_realloc) {
  zmq_install_error();
  return -1;
};

/*!
  @brief Add reply socket information to a send comm.
  @param[in] comm comm_t* Comm that confirmation is for.
  @returns char* Reply socket address.
*/
static inline
char *set_reply_send(const comm_t *comm) {
  zmq_install_error();
  return NULL;
};

/*!
  @brief Add reply socket information to a recv comm.
  @param[in] comm comm_t* Comm that confirmation is for.
  @param[in] address const char* Comm address.
  @returns int Index of the reply socket.
*/
static inline
int set_reply_recv(const comm_t *comm, const char* address) {
  zmq_install_error();
  return -1;
};

#endif /*ZMQINSTALLED*/

#ifdef __cplusplus /* If this is a C++ compiler, end C linkage */
}
#endif

#endif /*YGGZMQCOMM_H_*/
