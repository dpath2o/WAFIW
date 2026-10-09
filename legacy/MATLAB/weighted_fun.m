function err = weighted_fun(x,t2,P2,F,weight)
      
fit =  F(t2-x(1),ones(size(t2))*x(2),ones(size(t2))*x(3))*x(4);
err = fit - P2;

% weight the error according to the |WEIGHT| vector
err_weighted = err.*weight;
err = err_weighted;

end