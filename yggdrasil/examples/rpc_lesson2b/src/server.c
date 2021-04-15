#include "YggInterface.h"
#include <stdio.h>


int get_fibonacci(int n) {
  int pprev = 0, prev = 1, result = 1, fib_no = 1;
  while (fib_no < n) {
    result = prev + pprev;
    pprev = prev;
    prev = result;
    fib_no = fib_no + 1;
  }
  return result;
};


int main(int argc, char *argv[]) {
  
  int exit_code = 0;
  char* model_copy = getenv("YGG_MODEL_COPY");
  printf("Hello from C server%s!\n", model_copy);

  // Create server-side rpc conneciton using model name
  yggRpc_t rpc = yggRpcServer("server", "%d", "%d");

  // Continue receiving requests until the connection is closed when all
  // clients have disconnected.
  int flag, n, result;
  while (1) {
    printf("server%s(C): receiving...\n", model_copy);
    flag = rpcRecv(rpc, &n);
    if (flag < 0) {
      printf("server%s(C): end of input\n", model_copy);
      break;
    }

    // Compute fibonacci number
    printf("server%s(C): Received request for Fibonacci number %d\n",
	   model_copy, n);
    result = get_fibonacci(n);
    printf("server%s(C): Sending response for Fibonacci number %d: %d\n",
	   model_copy, n, result);

    // Send response back
    flag = rpcSend(rpc, result);
    if (flag < 0) {
      printf("server%s(C): ERROR sending\n", model_copy);
      exit_code = -1;
      break;
    }
  }

  printf("Goodbye from C server%s\n", model_copy);
  return exit_code;
};
