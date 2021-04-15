#include <iostream>

int model_function(char *in_buf, uint64_t length_in_buf,
		   char* &out_buf, uint64_t &length_out_buf) {
  std::cout << "server" << atoi(getenv("YGG_MODEL_COPY")) << "(C++): " << in_buf << std::endl;
  length_out_buf = length_in_buf;
  out_buf = (char*)realloc(out_buf, length_in_buf);
  memcpy(out_buf, in_buf, length_in_buf);
  out_buf[length_in_buf] = '\0';
  return 0;
};
