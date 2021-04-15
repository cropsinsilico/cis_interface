#include "YggInterface.hpp"
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
  printf("Hello from C++ server!\n");

  // Create server-side rpc conneciton using model name
  YggRpcServer rpc("server", "%d", "%d");

  // Continue receiving requests until the connection is closed when all
  // clients have disconnected.
  int flag, n, result;
  while (1) {
    printf("server(C++): receiving...\n");
    flag = rpc.recv(1, &n);
    if (flag < 0) {
      printf("server(C++): end of input\n");
      break;
    }

    // Compute fibonacci number
    printf("server(C++): Received request for Fibonacci number %d\n", n);
    result = get_fibonacci(n);
    printf("server(C++): Sending response for Fibonacci number %d: %d\n",
	   n, result);

    // Send response back
    flag = rpc.send(1, result);
    if (flag < 0) {
      printf("server(C++): ERROR sending\n");
      exit_code = -1;
      break;
    }
  }

  printf("Goodbye from C++ server\n");
  return exit_code;
};
