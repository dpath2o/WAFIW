function tc = colormapToTruecolor(map,ZData,Zmin,Zmax)
% map is a n-by-3 colormap matrix
% ZData is a k-by-w matrix of ZData (or CData, I suppose)
% Zmin is the value of Z associated with C=0
% Zmax is the value of Z associated with C=1
% tc is a kxwx3 Truecolor array based on map and ZData values.
% map = [map; 1 1 1];

ZData(ZData < Zmin) = Zmin;
ZData(ZData > Zmax) = Zmax;
ZData(isnan(ZData)) = nanmin(ZData(:));

tcIdx = round(rescale(ZData,1,height(map)));
tc = reshape(map(tcIdx,:),[size(ZData),3]);
end