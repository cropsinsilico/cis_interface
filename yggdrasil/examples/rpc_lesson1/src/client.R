library(yggdrasil)


main <- function(iterations) {

  fprintf('Hello from R client: iterations = %d', iterations)

  # Set up connections matching yaml
  # RPC client-side connection will be $(server_name)_$(client_name)
  rpc <- YggInterface('YggRpcClient', "server_client", "%d", "%d")
  log <- YggInterface('YggOutput', "output_log", 'fib(%-2d) = %-2d\n')

  # Iterate over Fibonacci sequence
  for (i in 1:iterations) {
        
    # Call the server and receive response
    fprintf('client(R): Calling fib(%d)', i)
    c(ret, result) %<-% rpc$call(i)
    if (!ret) {
      stop('client(R): RPC CALL ERROR')
    }
    fib <- result[[1]]
    fprintf('client(R): Response fib(%d) = %d', i, fib)

    # Log result by sending it to the log connection
    ret <- log$send(i, fib)
    if (!ret) {
      stop('client(R): SEND ERROR')
    }
  }

  print('Goodbye from R client')
}


args = commandArgs(trailingOnly=TRUE)
main(strtoi(args[[1]]))
