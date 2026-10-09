function y = sphericalVario(x,a,b,c)

% Spherical variogram model
% https://scikit-gstat.readthedocs.io/en/latest/reference/models.html

y = zeros(size(x));

y(x<a) = b + c*(1.5*x(x<a)/a - 0.5*x(x<a).^3/a);

y(x>=a) = b + c;

