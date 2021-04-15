program main
  use fygg

  interface
     function get_fibonacci(n) result(out)
       integer, intent(in) :: n
       integer :: out
     end function get_fibonacci
  end interface

  type(yggcomm) :: rpc
  logical :: ret
  integer :: fib, n
  integer :: exit_code = 0

  write(*, '("Hello from Fortran server!")')

  ! Create server-side rpc conneciton using model name
  rpc = ygg_rpc_server("server", "%d", "%d")

  ! Initialize variables
  ret = .true.
  fib = -1

  ! Continue receiving requests until the connection is closed when all
  ! clients have disconnected.
  do while (.TRUE.)
     write(*, '("server(F): receiving...")')
     ret = ygg_recv_var(rpc, yggarg(n))
     if (.not.ret) then
        write(*, '("server(F): end of input")')
        exit
     end if

     ! Compute fibonacci number
     write(*, '("server(F): Received request for Fibonacci number ",i2)') n
     fib = get_fibonacci(n)
     write(*, '("server(F): Sending response for Fibonacci number ",i2,": ",i2)') n, fib

     ! Send response back
     ret = ygg_send_var(rpc, yggarg(fib))
     if (.not.ret) then
        write(*, '("server(F): ERROR sending")')
        exit_code = -1;
        exit;
     end if
  end do

  write(*, '("Goodbye from Fortran server")')
  if (exit_code.lt.0) then
     stop 1
  end if

end program main

function get_fibonacci(n) result(out)
  integer, intent(in) :: n
  integer :: out
  integer :: pprev, prev, fib_no
  pprev = 0
  prev = 1
  out = 1
  fib_no = 1
  do while (fib_no < n)
     out = prev + pprev
     pprev = prev
     prev = out
     fib_no = fib_no + 1
  end do
end function get_fibonacci
