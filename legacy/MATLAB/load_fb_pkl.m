function [x_cord,y_cord,tim,freeB,freeB_smooth,freeB_std,sig_0,rm_error,pik_p,sea_i_con,le_sdt] = load_fb_pkl(filename,export)

% Load freeboard pkl file from Cryo-TEMPO processor
% export = 1 % Export data to .txt

% Ensure numpy installed on python env connected to Matlab
% pyenv(Version="C:\Users\jla129\AppData\Local\Programs\Python\Python310\python.exe")

fid = py.open(filename, 'rb');

data = py.pickle.load(fid);
data = cell(data);

x_cord = double(data{1});
y_cord = double(data{2});
tim = double(data{3});
freeB = double(data{4});
freeB_smooth = double(data{5});
freeB_std = double(data{6});
sig_0 = double(data{7});
rm_error = double(data{8});
pik_p = double(data{9});
sea_i_con = double(data{10});
le_sdt = double(data{11});

if export == 0
else
    header = {'x_cord','y_cord','tim','freeB','freeB_smooth','freeB_std','sig_0','rm_error','pik_p','sea_i_con','le_sdt'};
    data = [x_cord',y_cord',tim',freeB',freeB_smooth',freeB_std',sig_0',rm_error',pik_p',sea_i_con',le_sdt'];
    
    outname = strsplit(filename,'.');
    writecell(header,[outname{1} '.txt'],'delimiter',',')
    writematrix(data,[outname{1} '.txt'],'delimiter',',','WriteMode','append')
end

end