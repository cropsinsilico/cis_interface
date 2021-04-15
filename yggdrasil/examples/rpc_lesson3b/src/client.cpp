#include <omp.h>
#include "YggInterface.hpp"
#include <stdio.h>


int model_function(char* in_buf, uint64_t length_in_buf,
		   char* &out_buf, uint64_t &length_out_buf) {
  // Initialize yggdrasil outside the threaded section
  ygg_init();
  
  // Get the number of threads from an environment variable set in the yaml
  int nthreads = atoi(getenv("NTHREAD"));
  
  int error_code = 0;
#ifdef _OPENMP
  omp_set_num_threads(nthreads);
#pragma omp parallel for shared(error_code)
#endif
  for (int i = 0; i < nthreads; ++i){
    int flag;
#ifdef _OPENMP
#pragma omp critical
    {
#endif
      flag = error_code;
#ifdef _OPENMP
    }
#endif
    if (flag == 0) {
      char* out_temp = NULL;
      uint64_t length_out_temp = 0;
      char** out_buf_temp = &out_temp;
      uint64_t* length_out_buf_temp = &length_out_temp;
      if (i == 0) {
	out_buf_temp = &out_buf;
	length_out_buf_temp = &length_out_buf;
      }
      
      // The WITH_GLOBAL_SCOPE macro is required to ensure that the
      // comm persists between function calls
      WITH_GLOBAL_SCOPE(YggRpcClient rpc("server_client", "%s", "%s"));
      std::cout << "client(C++:" << i << "): Sending " << in_buf
		<< " (length = " << length_in_buf << ")" << std::endl;
      int ret = rpc.callRealloc(4, in_buf, length_in_buf,
				out_buf_temp, length_out_buf_temp);
      std::cout << "client(C++:" << i << "): Received " << *out_buf_temp
		<< " (length = " << *length_out_buf_temp << ")" << std::endl;
      if (ret < 0) {
	std::cout << "client(C++:" << i << "): RPC CALL ERROR" << std::endl;
#ifdef _OPENMP
#pragma omp critical
	{
#endif
	  error_code = -1;
#ifdef _OPENMP
	}
#endif
      }
      if (i != 0) {
	free(out_temp);
      }
    }
  }
  return error_code;
}
