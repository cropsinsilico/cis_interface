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

  fprintf('Hello from R server!')

  # Create server-side rpc conneciton using model name
  rpc <- YggInterface('YggRpcServer', "server", "%d", "%d")

  # Continue receiving requests until the connection is closed when all
  # clients have disconnected.
  while (1) {
    fprintf('server(R): receiving...')
    c(retval, rpc_in) %<-% rpc$recv()
    if (!retval) {
      fprintf('server(R): end of input')
      break
    }

    # Compute fibonacci number
    n = rpc_in[[1]]
    fprintf('server(R): Received request for Fibonacci number %d', n)
    result = get_fibonacci(n)
    fprintf('server(R): Sending response for Fibonacci number %d: %d', n, result)

    # Send response back
    flag <- rpc$send(result)
    if (!flag) {
      stop('server(R): ERROR sending')
    }
    
  }

  print('Goodbye from R server')
}

main()