function [thelon, thelat]=easegrid(iopt,alat,alon,ascale)
%
% function [thelon thelat]=easgrid(iopt,lat,lon,ascale)
%
%	computes the forward "ease" grid transform
%
%	given a lat,lon (alat,alon) and the scale (ascale) the image
%	transformation coordinates (thelon,thelat) are computed
%	using the "ease grid" (version 1.0) transformation given in fortran
%	source code supplied by nsidc.
%
%	the radius of the earth used in this projection is imbedded into
%	ascale while the pixel dimension in km is imbedded in bscale
%	the base values are: radius earth= 6371.228 km
%			     pixel dimen =25.067525 km
%	then, bscale = base_pixel_dimen
%	      ascale = radius_earth/base_pixel_dimen
%
%	iopt is ease type: iopt=11=north, iopt=12=south, iopt=13=cylindrical
%

% modified and corrected by dgl 23 July 2005
pi2=1.57079633d0;
dtr=pi2/90.0d0;

if iopt == 11		% ease grid north
  thelon= ascale.*sin(alon.*dtr).*sin(dtr.*(45.0-0.5.*alat));
  thelat=-ascale.*cos(alon.*dtr).*sin(dtr.*(45.0-0.5.*alat));
elseif iopt == 12	% ease grid south
  thelon=ascale*sin(alon*dtr)*cos(dtr*(45.0-0.5*alat));
  thelat=ascale*cos(alon*dtr)*cos(dtr*(45.0-0.5*alat));
elseif iopt == 13 	% ease cylindrical
  thelon=ascale*pi2*alon*cos(30.0*dtr)/90.0;
  thelat=ascale*sin(alat*dtr)/cos(30.0*dtr);
end;