! use omp_lib
function model_function(in_buf, out_buf) result(ret)
  character(len=*), intent(in) :: in_buf
  type(yggchar_r) :: out_buf
  logical :: ret
  type(yggcomm) :: rpc
  character(len=255) :: nthreads_str
  integer :: nthreads, i, j, error_code, flag
  type(yggchar_r) :: out_temp
  error_code = 0
  flag = 0

  ! Initialize yggdrasil outside the threaded section
  ret = ygg_init()
  if (.not.ret) then
     write(*, '("client(F): ERROR initializing yggdrasil")')
  end if

  ! Get the number of threads from an environment variable set in the yaml
  call get_environment_variable("NTHREAD", nthreads_str)
  read(nthreads_str,*) nthreads
  call omp_set_num_threads(nthreads)
  
  !$OMP PARALLEL DO PRIVATE(ret,flag,out_temp,i,j,rpc) SHARED(error_code,out_buf,in_buf,nthreads)
  do i=1,nthreads
     !$OMP CRITICAL
     flag = error_code
     !$OMP END CRITICAL

     if (flag.eq.0) then
        ! The WITH_GLOBAL_SCOPE macro is required to ensure that the
        ! comm persists between function calls
        !$OMP CRITICAL
        WITH_GLOBAL_SCOPE(rpc = ygg_rpc_client("server_client"))
        write(*, '("client(F:",i2,"): ",A," (length = ",I3,")")') i, in_buf, len(in_buf)
        out_temp%x => null()
        ret = ygg_rpc_call_realloc(rpc, yggarg(in_buf), yggarg(out_temp))
        !$OMP END CRITICAL
        if (.not.ret) then
           write(*, '("client(F:",i2,"): RPC CALL ERROR")') i
           !$OMP CRITICAL
           error_code = -1
           !$OMP END CRITICAL
        end if

        if (i.eq.1) then
           !$OMP CRITICAL
           allocate(out_buf%x(size(out_temp%x)))
           out_buf%x = out_temp%x;
           !$OMP END CRITICAL
        end if
     end if
  end do
  !$OMP END PARALLEL DO
  if (error_code.ne.0) stop 1
end function model_function
