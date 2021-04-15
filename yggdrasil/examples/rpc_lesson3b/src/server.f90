function model_function(in_buf, out_buf) result(out)
  character(len=*), intent(in) :: in_buf
  character(len=:), pointer :: out_buf
  logical :: out
  character(len=255) :: copy_str
  integer :: copy
  call get_environment_variable("YGG_MODEL_COPY", copy_str)
  read(copy_str,*) copy
  write(*, '("server",I1,"(Fortran): ",A)') copy, in_buf
  out = .true.
  allocate(character(len=len(in_buf)) :: out_buf)
  out_buf = in_buf
end function model_function
