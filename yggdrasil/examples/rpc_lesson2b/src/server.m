
function server()

  model_copy = getenv('YGG_MODEL_COPY');
  fprintf('Hello from Matlab server%s!\n', model_copy);

  % Create server-side rpc conneciton using model name
  rpc = YggInterface('YggRpcServer', 'server', '%d', '%d');

  % Continue receiving requests until the connection is closed when all
  % clients have disconnected.
  while true
    fprintf('server%s(M): receiving...\n', model_copy);
    [retval, rpc_in] = rpc.recv();
    if (~retval);
      fprintf('server%s(M):end of input\n', model_copy);
      break;
    end;

    % Compute fibonacci number
    n = rpc_in{1};
    fprintf('server%s(M): Received request for Fibonacci number %d\n', model_copy, n);
    pprev = 0;
    prev = 1;
    result = 1;
    fib_no = 1;
    while fib_no < n
      result = prev + pprev;
      pprev = prev;
      prev = result;
      fib_no = fib_no + 1;
    end;
    fprintf('server%s(M): Sending response for Fibonacci number %d: %d\n', model_copy, n, result);

    % Send response back
    flag = rpc.send(int32(result));
    if (~flag);
      error(sprintf('server%s(M): ERROR sending', model_copy));
    end;
  end;

  fprintf('Goodbye from Matlab server%s\n', model_copy);
  
end




