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
  character(len=255) :: model_copy

  call get_environment_variable("YGG_MODEL_COPY", model_copy)
  write(*, '("Hello from Fortran server",A1,"!")') model_copy

  ! Create server-side rpc conneciton using model name
  rpc = ygg_rpc_server("server", "%d", "%d")

  ! Initialize variables
  ret = .true.
  fib = -1

  ! Continue receiving requests until the connection is closed when all
  ! clients have disconnected.
  do while (.TRUE.)
     write(*, '("server",A1,"(F): receiving...")') model_copy
     ret = ygg_recv_var(rpc, yggarg(n))
     if (.not.ret) then
        write(*, '("server",A1,"(F): end of input")') model_copy
        exit
     end if

     ! Compute fibonacci number
     write(*, '("server",A1,"(F): Received request for Fibonacci number ",i2)') model_copy, n
     fib = get_fibonacci(n)
     write(*, '("server",A1,"(F): Sending response for Fibonacci number ",i2,": ",i2)') model_copy, n, fib

     ! Send response back
     ret = ygg_send_var(rpc, yggarg(fib))
     if (.not.ret) then
        write(*, '("server",A1,"(F): ERROR sending")') model_copy
        exit_code = -1;
        exit;
     end if
  end do

  write(*, '("Goodbye from Fortran server",A1)') model_copy
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
