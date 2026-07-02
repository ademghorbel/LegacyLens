program payroll
  implicit none
  real :: hours, rate, gross, tax, net
  hours = 42.0
  rate = 18.5
  gross = hours * rate
  if (hours > 40.0) gross = gross + (hours - 40.0) * rate * 0.5
  tax = gross * 0.2
  net = gross - tax
  print *, 'Net pay:', net
end program payroll
