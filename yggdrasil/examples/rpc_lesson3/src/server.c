#include <stdio.h>

int model_function(char *in_buf, uint64_t length_in_buf,
		   char **out_buf, uint64_t *length_out_buf) {
  printf("server(C): %s\n", in_buf);
  length_out_buf[0] = length_in_buf;
  out_buf[0] = (char*)malloc(length_in_buf);
  memcpy(out_buf[0], in_buf, length_in_buf);
  out_buf[0][length_in_buf] = '\0';
  return 0;
};
