function [acf,cl,lags] = acf1D(f,x,opt)
%
% [acf,cl,lags] = acf1D(f,x)
%
% calculates the autocovariance function and correlation length of a 
% 1-d surface profile f(x).
%
% Input:    f    - surface heights
%           x    - surface points
%           opt - optional parameter (type 'plot' for plotting the 
%                 normalized autocovariance function)
%
% Output:   acf  - autocovariance function
%           cl   - correlation length
%           lags - lag length vector (useful for plotting the acf)
%
% Last updated: 2010-07-26 (David Bergstrom)
%

format long

N = length(x); % number of sample points
lags = linspace(0,x(N)-x(1),N); % lag lengths

% autocovariance function calculation
c=xcov(f,'coeff'); % the autocovariance function
acf=c(N:2*N-1); % right-sided version

% correlation length calculation
k = 1;
while (acf(k) > 1/exp(1))
    k = k + 1;
end;
cl = 1/2*(x(k-1)+x(k)-2*x(1)); % the correlation length

% optional plotting
if nargin<3 || isempty(opt)
    return;
end;
if nargin==3 
    if ischar(opt)
        if strcmp(opt,'plot');
            plot(lags,acf);
            xlabel('lag length')
            ylabel('acf (normalized)')
            title('Plot of the normalized acf')
        else fprintf('%s is not a valid option. Type \''help acf1D\'' for further details.\n',opt); 
        end;
    else fprintf('Option must be a string. Type \''help acf1D\'' for further details.\n');
    end;
end;