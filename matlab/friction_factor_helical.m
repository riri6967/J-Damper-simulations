function [f, regime, Re_crit] = friction_factor_helical(Re, delta, model)
%FRICTION_FACTOR_HELICAL Darcy friction factor for flow in a helical/curved pipe.
%   [f, regime, Re_crit] = FRICTION_FACTOR_HELICAL(Re, delta) returns the
%   Darcy friction factor for Reynolds number Re (vector allowed) and
%   curvature ratio delta = r/R.
%   model = 'ito' (default) or 'white' selects the laminar correlation.
%
%   Laminar  : Ito (1959)   f_c/f_s = 21.5 De / (1.56 + log10 De)^5.73, 13.5<De<2000
%              White (1929) f_c/f_s = 1/(1 - (1 - (11.6/De)^0.45)^(1/0.45)), De>11.6
%   Turbulent: Ito (1959)   f_c = 0.304 Re^-0.25 + 0.029 sqrt(delta)
%   Transition: Schmidt (1967) Re_crit = 2300 (1 + 8.6 delta^0.45)
%   regime is 0 for laminar and 1 for turbulent.
%   Check the constants against the original papers before final use.

if nargin < 3, model = 'ito'; end
Re = max(Re, 1e-9);
De = Re .* sqrt(delta);
Re_crit = 2300 * (1 + 8.6 * delta^0.45);

f_s = 64 ./ Re;
ratio = ones(size(Re));
switch lower(model)
    case 'ito'
        m = De > 13.5;
        ratio(m) = 21.5 * De(m) ./ (1.56 + log10(De(m))).^5.73;
    case 'white'
        m = De > 11.6;
        ratio(m) = 1 ./ (1 - (1 - (11.6 ./ De(m)).^0.45).^(1/0.45));
    otherwise
        error('Unknown model "%s"', model);
end
ratio = max(ratio, 1);
f = f_s .* ratio;

regime = double(Re > Re_crit);
turb = regime == 1;
f(turb) = 0.304 * Re(turb).^(-0.25) + 0.029 * sqrt(delta);
end
