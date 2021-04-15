model_function <- function(in_buf) {
  fprintf('server(R): %s', in_buf)
  out_buf <- in_buf
  return(out_buf);
}
