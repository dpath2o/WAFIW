function N = weighted_histcounts(X,W,edges)

% Calculate counts of X in histogram bins defined by edges, weighted by W

% Create an empty vector to hold the values
numBins = numel(edges) - 1;
N = zeros(numBins, 1);

% Calculate the weighted counts for each bin
for i = 1:numBins
    idx = X >= edges(i) & X < edges(i+1);
    N(i) = sum(W(idx));
end

end

