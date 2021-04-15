import numpy as np
from yggdrasil.interface.YggInterface import YggInput, YggRpcServer


def get_fibonacci(n):
    r"""Compute the nth number of the Fibonacci sequence.

    Args:
        n (int): Index of the Fibonacci number in the Fibonacci sequence that
            should be returned.

    Returns:
        int: The nth Fibonacci number.

    """
    pprev = 0
    prev = 1
    result = 1
    fib_no = 1
    while fib_no < n:
        result = prev + pprev
        pprev = prev
        prev = result
        fib_no = fib_no + 1
    return result


def main():
    r"""Function to execute server communication and computation in a loop."""

    print('Hello from Python server!')

    # Get parameters
    inp = YggInput("params")
    retval, params = inp.recv()
    if not retval:
        raise RuntimeError('server(P): ERROR receiving parameters')
    print('server(P): Parameters = %s' % params)

    # Create server-side rpc conneciton using model name
    rpc = YggRpcServer("server", "%d", "%d")

    # Continue receiving requests until the connection is closed when all
    # clients have disconnected.
    while True:
        print('server(P): receiving...')
        retval, rpc_in = rpc.recv()
        if not retval:
            print('server(P): end of input')
            break

        # Compute fibonacci number
        n = rpc_in[0]
        print('server(P): Received request for Fibonacci number %d' % n)
        result = get_fibonacci(n)
        print('server(P): Sending response for Fibonacci number %d: %d' % (n, result))

        # Send response back
        flag = rpc.send(np.int32(result))
        if not flag:
            raise RuntimeError('server(P): ERROR sending')

    print('Goodbye from Python server')

    
if __name__ == '__main__':
    main()
