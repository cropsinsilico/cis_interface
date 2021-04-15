function model_function(in_buf, out_buf) result(out)
  character(len=*), intent(in) :: in_buf
  character(len=:), pointer :: out_buf
  logical :: out
  write(*, '("server(Fortran): ",A)') in_buf
  out = .true.
  allocate(character(len=len(in_buf)) :: out_buf)
  out_buf = in_buf
end function model_function
