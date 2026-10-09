function [s,int] = trend(A,t,dim)
% [s,int] = trend(A) returns the linear trend of A by least squares. If A is a
% vector, s is the slope of the linear fit.  If A is an N-dimensional array, 
% s and int are (N-1)-dimensional matrices corresponding to the slope and 
% intercept along the dimension dim.  
% 
%
% SYNTAX: 
% s = trend(A) 
% s = trend(A,Fs) 
% s = trend(A,t) 
% s = trend(...,dim) 
% s = trend(A,[],dim)
% [s,int] = trend(...)
%
% 
% DESCRIPTION: 
% s = trend(A) returns the (N-1)-dimensional matrix s corresponding to the
% linear trend(s) along dimension 1 of A. Assumes data are evenly spaced
% along dimension 1. 
% 
% s = trend(A,Fs) declares sampling frequency Fs along trending dimension of A.     
% 
% s = trend(A,t) allows for unevenly-spaced data in the trending dimension
% with time vector t. length of t must equal the length of A along its
% trending dimension.  
% 
% s = trend(...,dim) returns the trend along dimension dim of A. 
% 
% s = trend(A,[],dim) assumes data are sampled at 1 Hz (or 1/(unit time) or
% 1/(unit space) or what-have-you). 
%
% [s,int] = trend(...) also returns the intercepts of the slope-intercept
% form. 
% 
% 
% *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *  *
% %           * * * * * EXAMPLES * * * * * 
% % The examples below use the following artificial data. Note that if you
% % complete all of these examples, your answers might be a little bit
% % different because you and I are creating slightly different fake data
% % via the rand function. 
% 
% Fs = 2;                  % sampling rate (per unit time) 
% t = (115:1/Fs:145)';     % time vector sampled at Fs per unit time
% 
%
% % Generate a 1D data set with trend forced to 40 units y per unit time: 
% y = 40*t + 123*rand(size(t)); % forced trend of 40 units y per second
% 
% 
% % Generate a 2D data set  
% Y = y';
% Y(2,:) = y'*3;
% Y(3,:) = 50*rand(size(y'));
%
%
% % Generate a 3D data set with artifical trends at the corners: 
% A = rand(3,4,length(t)); % some random data
% A(1,1,:) = 1*t + 5;      % trend (slope) is one unit y per unit time at location 1,1
% A(3,1,:) = 7;            % no trend at location 3,1
% A(3,4,:) = t/2 - 1;      % trend is one half unit per unit time at 3,4
% A(1,4,:) = -3*t + 3;     % trend is negative at location 1,4
%  
%
% %           * * * 1D ARRAY EXAMPLES * * * 
% 
% plot(t,y,'*') 
%
% trend(y)
% 
%   = 20.0148
% 
% % Wait a minute! Shouldn't y have a trend (slope) of 40? 
% % --Yes. You see, this calculation has assumed that y is sampled at 1 Hz,
% % when in fact Fs is 2 Hz. I suppose you could downsample y like this: 
% 
% trend(y(1:2:end))
%
%   = 39.2609
% 
% % But that would mean discarding perfectly good data. We know Fs, so we can
% % include it: 
% 
% trend(y,Fs)
% 
%   = 40.0296
% 
% % That's better! Or just as easily, you could use the time vector in place 
% % of the sampling rate: 
% 
% trend(y,t)
%
%   = 40.0296
%
% % What if your data are not sampled at perfectly-spaced intervals in time? 
% % Including the corresponding time vector will still work. To show this, let's
% % create some data that are not sampled at perfect intervals: 
% 
% y2 = y([1:10 12:40 45:end]);
% t2 = t([1:10 12:40 45:end]);
% plot(t2,y2,'r^'); hold on;
% axis([0 150 0 6000])
% 
% trend(y2,t2)
% 
%   = 40.1198
% 
% % Now let's use the slope and intercept values in old y = m*x + b form. 
% 
% [m,b] = trend(y2,t2);
% plot(t,m*t+b)
% 
% %           * * * 2D ARRAY EXAMPLES * * * 
% % A 2D matrix b was created above
% figure 
% plot(t,Y,'o')
% legend('Y1','Y2','Y3')
% 
% % Suppose you'd like to get an array of the trends along each row of Y. 
% % Here Y is 3 x 61, and we'll operate along dimension 2: 
% 
% trend(Y,Fs,2)
% 
%   = 40.0296
%    120.0888
%     -.01215
% 
% % That looks about right.  Similarly, you could do 
% 
% trend(Y',Fs)
% 
%   = 40.0296  120.0888   -0.1215
% 
% % Or of course,
% 
% trend(Y',t)
% 
%   = 40.0296  120.0888   -0.1215
% 
% % To get the slopes as well, 
% 
% [mY,bY] = trend(Y,t,2); 
% hold on;
% for n = 1:3
%     plot(t,t*mY(n,:)+bY(n))
% end
%
% 
% %           * * * 3D ARRAY EXAMPLES * * * 
% % This function was designed specifically for 3D data sets such 
% % as gridded fields that change over time, e.g. climatological 
% % reanalysis data (wind, pressure, sea surface temps, etc). 
% % Reanalysis data sets are too big to distribute as example data 
% % alongside a file on FEX, so above we created some fake data
% % that evolves through time.  Dimensions 1 and 2 of A can be thought
% % of as corresponding to x and y coordinates or latitudes and longitudes.
% % Dimension 3 of A corresponds to time.  Most of the grid boxes in A
% % do not exhibit significant trends, but the corners of the data
% % do have trends.  To show this, let's see A evolve through time: 
% 
% figure
% for n = 1:length(t)
%     imagesc(squeeze(A(:,:,n)))
%     colorbar
%     caxis([-400 150])
%     title(['time = ',sprintf('%.1f',t(n)),' seconds'])
%     pause(.05)
% end
%
% % We see that the upper left hand corner trends positive, the lower right
% % hand corner trends positive at about half the rate of the upper left
% % hand corner, and the upper right trends negative.  The lower left remains
% % constant through time.  
% 
% trendmap = trend(A,t,3)
% 
%     trendmap =
% 
%         1.0000   -0.0035    0.0056   -3.0000
%         0.0003   -0.0059   -0.0002   -0.0030
%        -0.0000    0.0024   -0.0006    0.5000
% 
%
% % We can depict trendmap graphically: 
% 
% figure
% imagesc(trendmap)
% colorbar
% colormap(summer) 
% 
% % To get the slope intercepts, 
% 
% [~,intercepts] = trend(A,t,3) 
% 
%     intercepts =
% 
%         5.0000    0.4882    0.7868    3.0000
%         0.9211    1.0509    0.5046    1.4350
%         7.0000    0.4426    0.3497   -1.0000
% 
% % And those corner intercepts are exactly what we defined. 
% 
% %           * * * ND ARRAYS * * * 
% Following the forms described above, this function will return slopes and
% intercepts for any ND array. Hope this comes in handy. 
% 
% * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
% Version history: 
% Version 1: April 25, 2014
% Version 2: April 28, 2014 now works for any N-dimensional inputs and
%            optionally returns intercepts.  
%
% * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
% Chad A. Greene
% Institute for Geophysics
% The University of Texas at Austin
% April 2014
% 
% Thanks to Matt J. for writing much of this code. 
% * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
% 
% See also: polyfit. 
% Input checking: 
assert(~isscalar(A),'Input data A cannot be a scalar.'); 
sizeA = size(A); 
 
if exist('dim','var')
    assert(ndims(A)>=dim,'dim argument exceeds dimensions of A'); 
else
    dim = 1; 
end
dimLength = sizeA(dim); 
if exist('t','var')
    if isscalar(t)
        t = 0:1/t:(dimLength-1)/t; % for the case where t is declared as sampling frequency.
        if nargout == 2
            disp('Warning: independent variable vector starts at zero. This may affect intercept value.')
            disp('If you want full confidence in the intercept value, use time vector as input instead of scalar sampling frequency.') 
        end
    end
  
    if isempty(t)
        t = 0:dimLength-1; 
    end
    
else
    t = 0:dimLength-1;     
end
t = t(:); 
order=[dim, setdiff(1:ndims(A),dim)];
sizeA(dim)=1;
sizeA=sizeA(order);
data2D = reshape(permute(A,order),dimLength,[]);
coefficients = ([t ones(size(t))]\data2D); 
s = squeeze(ipermute(reshape(coefficients(1,:),sizeA),order));
if nargout==2
    int = squeeze(ipermute(reshape(coefficients(2,:),sizeA),order));
end
end
