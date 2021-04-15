
function server()
  
  disp('Hello from Matlab server!');

  % Create server-side rpc conneciton using model name
  rpc = YggInterface('YggRpcServer', 'server', '%d', '%d');

  % Continue receiving requests until the connection is closed when all
  % clients have disconnected.
  while true
    disp('server(M): receiving...');
    [retval, rpc_in] = rpc.recv();
    if (~retval);
      disp('server(M):end of input');
      break;
    end;

    % Compute fibonacci number
    n = rpc_in{1};
    fprintf('server(M): Received request for Fibonacci number %d\n', n);
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
    fprintf('server(M): Sending response for Fibonacci number %d: %d\n', n, result);

    % Send response back
    flag = rpc.send(int32(result));
    if (~flag);
      error('server(M): ERROR sending');
    end;
  end;

  disp('Goodbye from Matlab server');
  
end




