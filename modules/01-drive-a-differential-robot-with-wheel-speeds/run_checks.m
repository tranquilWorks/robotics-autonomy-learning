function run_checks
straight=model(5,5,0.1,0.4,5);
assert(abs(straight.omega)<eps,'Equal wheel speeds should drive straight.');
spin=model(-5,5,0.1,0.4,5);
assert(abs(spin.v)<eps && spin.omega>0,'Opposite wheel speeds should spin in place.');
wide=model(5,8,0.1,0.8,5);
narrow=model(5,8,0.1,0.2,5);
assert(abs(narrow.omega)>abs(wide.omega),'Narrower track should turn faster.');
disp('P01 checks passed.');
end
