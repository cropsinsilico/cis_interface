#include "YggInterface.hpp"
#include <iostream>


int model_function(char *in_buf, uint64_t length_in_buf,
		   char* &out_buf, uint64_t &length_out_buf) {
  // The WITH_GLOBAL_SCOPE macro is required to ensure that the comm persists
  // between function calls
  WITH_GLOBAL_SCOPE(YggRpcClient rpc("server_client", "%s", "%s"));
  std::cout << "client(C++): " << in_buf << " (length = " << length_in_buf << ")" << std::endl;
  int ret = rpc.callRealloc(4, in_buf, length_in_buf, &out_buf, &length_out_buf);
  if (ret < 0) {
    std::cout << "client(C++): RPC CALL ERROR" << std::endl;
    return -1;
  }
  return 0;
}
