function [alon, alat]=ieasegrid(iopt,thelon,thelat,ascale)
%
% function [lon, lat]=ieasegrid(iopt,thelon,thelat,ascale)
%
%	computes the inverse "ease" grid transform
%
%	given the image transformation coordinates (thelon,thelat) and
%	the scale (ascale) the corresponding lon,lat (lon,lat) is computed
%	using the "ease grid" (version 1.0) transformation given in fortran
%	source code supplied by NSIDC
%	iopt is ease type: iopt=11=north, iopt=12=south, iopt=13=cylindrical
%

%	the radius of the earth used in this projection is imbedded into
%	ascale while the pixel dimension in km is imbedded in bscale
%	the base values are: radius earth= 6371.228 km
%			     pixel dimen =25.067525 km
%	then, bscale = base_pixel_dimen
%	      ascale = radius_earth/base_pixel_dimen
%

% vectorized  DGL 7/18/2005
% revised and corrected by dgl 23 Jul 2005
pi2=1.57079633d0;		% pi/2 at standard precision
dtr=pi2/90.0d0;
x1=thelon;
y1=thelat;
temp=zeros(size(thelon));
if (iopt == 11)	% ease grid north
  alon=atan2(x1,-y1)/dtr;
% vectorized code
  alat=zeros(size(alon));
  ind=find(abs(sin(dtr*alon)) > abs(cos(alon*dtr)));
  temp(ind)=(x1(ind)./sin(alon(ind)*dtr))/ascale;
  ind=find(abs(sin(dtr*alon)) <= abs(cos(alon*dtr)));
  temp(ind)=(-y1(ind)./cos(alon(ind)*dtr))/ascale;
  alat(abs(temp)<=1)=90.0d0-2.*asin(temp(abs(temp)<=1))/dtr;
  alat(abs(temp)>1)=90.0*sign(temp(abs(temp)>1));
% original non-vector code
%  if (abs(sin(dtr*alon)) > abs(cos(alon*dtr)))
%    temp=(x1./sin(alon*dtr))/ascale;
%  else
%    temp=(-y1./cos(alon*dtr))/ascale;
%  end;
%  if (abs(temp) <= 1)
%    alat=90.0d0-2.*asin(temp)/dtr;
%  else
%    alat=-90.0d0+2.*asin(1./temp)/dtr;
%    disp(['*** error in ease inverse sine *** ',num2str(temp)]);
%  end;
elseif (iopt == 12)	% ease grid south
  alon=atan2(x1,y1)/dtr;
% vectorized code
  alat=zeros(size(alon));
  ind=(abs(cos(alon*dtr)) > abs(sin(alon*dtr)));
  temp(ind)=(y1(ind)./cos(alon(ind)*dtr))/ascale;
  ind=(abs(cos(alon*dtr)) <= abs(sin(alon*dtr)));
  temp(ind)=(x1(ind)./sin(alon(ind)*dtr))/ascale;
  alat(abs(temp)<=1)=90.0d0-2.*acos(temp(abs(ind)<=1))/dtr;
  alat(abs(temp)>1)=90.0*sign(temp(abs(temp)>1));
% original non-vector code
%  if (abs(cos(alon*dtr)) > abs(sin(alon*dtr)))
%    temp=(y1./cos(alon*dtr))/ascale;
%  else
%    temp=(x1./sin(alon*dtr))/ascale;
%  end;
%  if (abs(temp) <= 1)
%    alat=90.0d0-2.*acos(temp)/dtr;
%  else
%    disp(['*** error in ease inverse cosine *** ',num2str(temp)]);
%    alat=0.0;
%  end;
elseif (iopt == 13)	% ease cylindrical
  alon=((x1./ascale)/cos(30.0*dtr))*90.0d0/pi2;
  temp=(y1.*cos(30.0*dtr))/ascale;
% vectorized code
  alat=zeros(size(alon));
  alat(abs(temp)<=1)=asin(temp(abs(temp)<=1))/dtr;
  alat(abs(temp)>1)=90.0*sign(temp(abs(temp)>1));
% original non-vector code
%  if (abs(temp) <= 1)
%    alat=asin(temp)/dtr;
%  else
%    disp(['*** error in ease inverse sine *** ',num2str(temp)]);
%    alat=sign(90.0,temp);
%  end;
end;
