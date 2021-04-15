library(yggdrasil)


get_fibonacci <- function(n) {
  pprev = 0
  prev = 1
  result = 1
  fib_no = 1
  while (fib_no < n) {
    result = prev + pprev
    pprev = prev
    prev = result
    fib_no = fib_no + 1
  }
  return(as.integer(result))
}


main <- function() {

  model_copy = Sys.getenv('YGG_MODEL_COPY')
  fprintf('Hello from R server%s!', model_copy)

  # Create server-side rpc conneciton using model name
  rpc <- YggInterface('YggRpcServer', "server", "%d", "%d")

  # Continue receiving requests until the connection is closed when all
  # clients have disconnected.
  while (1) {
    fprintf('server%s(R): receiving...', model_copy)
    c(retval, rpc_in) %<-% rpc$recv()
    if (!retval) {
      fprintf('server%s(R): end of input', model_copy)
      break
    }

    # Compute fibonacci number
    n = rpc_in[[1]]
    fprintf('server%s(R): Received request for Fibonacci number %d', model_copy, n)
    result = get_fibonacci(n)
    fprintf('server%s(R): Sending response for Fibonacci number %d: %d', model_copy, n, result)

    # Send response back
    flag <- rpc$send(result)
    if (!flag) {
      stop(sprintf('server%s(R): ERROR sending', model_copy))
    }
    
  }

  fprintf('Goodbye from R server%s', model_copy)
}

main()